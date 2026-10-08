"""API web: tạo job, đọc/sửa dự án JSON, tạo lại câu, trả file.

Mọi API job đều cần đăng nhập; người dùng thường chỉ thấy job của mình, quản trị viên thấy hết.
Xác thực ở auth.py, trang quản trị ở admin.py, CSRF + header bảo mật ở security.py.

Chạy:  uvicorn server.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vidub.pipeline import rtf_report
from vidub.project import Project

from . import admin, auth, db
from .auth import current_user
from .jobs import BUSY_STATES, enqueue, job_dir, list_job_dirs, new_job_id, read_status, write_status
from .security import client_ip, security_middleware

DISCLAIMER = "Giọng nói trong video được tạo bởi AI, chỉ dùng cho mục đích nghiên cứu."
REGEN_STEPS = ["synthesize", "align", "mix"]
RENDER_STEPS = ["translate", "synthesize", "align", "mix"]
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".wav", ".mp3", ".m4a", ".flac"}
SRC_LANGS = {"en", "zh", "ja", "ko"}
JOB_ID_RE = re.compile(r"^[\w-]{1,64}$")

log = logging.getLogger("vidub.server")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if auth.user_count() == 0:
        log.warning("Chưa có tài khoản nào. Mở /#/setup và nhập mã khởi tạo: %s", auth.setup_token())
        print(f"\n  vidub: mã khởi tạo tài khoản quản trị = {auth.setup_token()}\n", flush=True)
    yield


app = FastAPI(title="vidub", version="0.2.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(admin.router)


@app.middleware("http")
async def upload_size_guard(request: Request, call_next):
    """Chặn sớm upload quá lớn dựa vào Content-Length, trước khi server nhận hết file."""
    if request.method == "POST" and request.url.path == "/api/jobs":
        limit = (db.setting("max_upload_mb") + 2) * 2 ** 20  # +2 MB cho phụ đề và phần đầu multipart
        try:
            too_big = int(request.headers.get("content-length", "0")) > limit
        except ValueError:
            too_big = False
        if too_big:
            return JSONResponse({"detail": f"File vượt quá {db.setting('max_upload_mb')} MB"}, status_code=413)
    return await call_next(request)


app.middleware("http")(security_middleware)


# ---------------------------------------------------------------- quyền truy cập job
def job_owner(job_id: str) -> int | None:
    with db.connect() as con:
        r = con.execute("SELECT owner_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return r["owner_id"] if r else None


def can_access(job_id: str, user: dict) -> bool:
    return user["role"] == "admin" or job_owner(job_id) == user["id"]


def owned_job(job_id: str, user: dict = Depends(current_user)) -> str:
    """Dependency: job tồn tại và người dùng có quyền. Không có quyền cũng trả 404 để không lộ job."""
    if not JOB_ID_RE.match(job_id) or not can_access(job_id, user):
        raise HTTPException(404, "Không có job này")
    try:
        if not (job_dir(job_id) / "project" / "project.json").exists():
            raise HTTPException(404, "Không có job này")
    except ValueError:
        raise HTTPException(404, "Không có job này")
    return job_id


def safe_clip_id(filename: str | None) -> str:
    stem = Path(filename or "clip").stem
    return re.sub(r"[^\w\-. ]", "_", stem)[:80].strip(" .") or "clip"


# ---------------------------------------------------------------- tiện ích
def load_project(job_id: str) -> Project:
    try:
        return Project.load(job_dir(job_id) / "project")
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Không có job này")


def editable_project(job_id: str) -> Project:
    if read_status(job_id).get("state") in BUSY_STATES:
        raise HTTPException(409, "Job đang chạy, chờ xong rồi sửa")
    return load_project(job_id)


def job_view(job_id: str) -> dict:
    project = load_project(job_id)
    data = project.model_dump(mode="json")
    data.pop("turns", None)
    for s in data["segments"]:
        s.pop("words", None)
    return {"id": job_id, "status": read_status(job_id), "project": data, "rtf": rtf_report(project)}


# ---------------------------------------------------------------- job
@app.get("/api/meta")
def meta():
    return {"disclaimer": DISCLAIMER}


def copy_limited(src, dst: Path, limit: int) -> int:
    """Chép file upload, dừng khi vượt `limit` byte. Trả về số byte đã chép."""
    n = 0
    with dst.open("wb") as f:
        while chunk := src.read(1 << 20):
            n += len(chunk)
            if n > limit:
                raise HTTPException(413, f"File vượt quá {limit // 2 ** 20} MB")
            f.write(chunk)
    return n


@app.post("/api/jobs")
async def create_job(request: Request, video: UploadFile = File(...), src_lang: str = Form("en"),
                     subtitles: UploadFile | None = File(None), user: dict = Depends(current_user)):
    settings = db.get_settings()
    if src_lang not in SRC_LANGS:
        raise HTTPException(400, "Ngôn ngữ gốc không được hỗ trợ")
    suffix = Path(video.filename or "clip.mp4").suffix.lower() or ".mp4"
    if suffix not in VIDEO_EXT:
        raise HTTPException(400, f"Không nhận định dạng {suffix}. Chỉ nhận: {', '.join(sorted(VIDEO_EXT))}")
    if subtitles is not None and subtitles.filename and not subtitles.filename.lower().endswith(".srt"):
        raise HTTPException(400, "Phụ đề phải là file .srt")
    if user["role"] != "admin":
        with db.connect() as con:
            mine = [r["id"] for r in con.execute("SELECT id FROM jobs WHERE owner_id = ?", (user["id"],))]
        active = sum(read_status(j).get("state") in BUSY_STATES + ("created",) for j in mine)
        if active >= settings["max_active_jobs"]:
            raise HTTPException(429, f"Bạn đang có {active} job chưa xong (tối đa {settings['max_active_jobs']}). Chờ xong rồi tải tiếp.")

    job_id = new_job_id()
    jdir = job_dir(job_id)
    (jdir / "input").mkdir(parents=True)
    src = jdir / "input" / f"source{suffix}"
    try:
        size = copy_limited(video.file, src, settings["max_upload_mb"] * 2 ** 20)
        if subtitles is not None and subtitles.filename:
            size += copy_limited(subtitles.file, src.with_suffix(".srt"), 5 * 2 ** 20)
    except HTTPException:
        shutil.rmtree(jdir, ignore_errors=True)
        raise
    filename = Path(video.filename or "clip").name[:200]
    Project.create(jdir / "project", src, clip_id=safe_clip_id(video.filename), src_lang=src_lang)
    write_status(jdir, state="created", filename=filename)
    with db.connect() as con:
        con.execute("INSERT INTO jobs(id, owner_id, filename, size_bytes, created_at) VALUES(?,?,?,?,?)",
                    (job_id, user["id"], filename, size, time.time()))
    db.audit("job_create", user=user, target=job_id, ip=client_ip(request), detail={"filename": filename, "bytes": size})
    enqueue(job_id, None)
    return {"id": job_id}


@app.get("/api/jobs")
def list_jobs(user: dict = Depends(current_user)):
    with db.connect() as con:
        mine = {r["id"]: dict(r) for r in con.execute("SELECT * FROM jobs WHERE owner_id = ?", (user["id"],))}
    out = []
    for d in list_job_dirs():
        if d.name in mine:
            st = read_status(d.name)
            out.append({"id": d.name, "filename": mine[d.name]["filename"] or st.get("filename"), "state": st.get("state")})
    return out


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str = Depends(owned_job)):
    return job_view(job_id)


@app.delete("/api/jobs/{job_id}")
def delete_job(request: Request, job_id: str = Depends(owned_job), user: dict = Depends(current_user)):
    if read_status(job_id).get("state") in BUSY_STATES:
        raise HTTPException(409, "Job đang chạy, chờ xong rồi xoá")
    shutil.rmtree(job_dir(job_id), ignore_errors=True)
    with db.connect() as con:
        con.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    db.audit("job_delete", user=user, target=job_id, ip=client_ip(request))
    return {"ok": True}


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str = Depends(owned_job)):
    """SSE: đẩy trạng thái mỗi khi status.json đổi, dừng khi job xong hoặc lỗi."""

    async def stream():
        last = None
        for _ in range(60 * 60 * 6):
            st = read_status(job_id)
            if st != last:
                last = st
                yield f"data: {json.dumps(st, ensure_ascii=False)}\n\n"
            if st.get("state") not in BUSY_STATES + ("created",):
                break
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/jobs/{job_id}/render")
def render(job_id: str = Depends(owned_job)):
    """Áp dụng các sửa đổi: dịch câu chưa dịch, sinh lại câu đã đổi, trộn lại."""
    editable_project(job_id)
    enqueue(job_id, RENDER_STEPS)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/rerun")
def rerun(job_id: str = Depends(owned_job), from_step: str = "extract", force: bool = False):
    from vidub.pipeline import select_steps

    editable_project(job_id)
    try:
        steps = select_steps(from_step=from_step)
    except ValueError as e:
        raise HTTPException(400, str(e))
    enqueue(job_id, steps, force)
    return {"ok": True}


# ---------------------------------------------------------------- người nói
class SpeakerPatch(BaseModel):
    name: str | None = Field(None, max_length=80)
    notes: str | None = Field(None, max_length=1000)
    timbre_from_segment: int | None = None   # lấy câu này làm giọng mẫu


@app.patch("/api/jobs/{job_id}/speakers/{spk}")
def patch_speaker(spk: str, body: SpeakerPatch, job_id: str = Depends(owned_job)):
    project = editable_project(job_id)
    if spk not in project.speakers:
        raise HTTPException(404, "Không có người nói này")
    speaker = project.speakers[spk]
    if body.name is not None:
        speaker.name = body.name.strip() or spk
    if body.notes is not None:
        speaker.notes = body.notes
        # Ghi chú đổi -> xưng hô có thể đổi: dịch lại các câu chưa sửa tay của người này.
        for s in project.segments:
            if s.speaker == spk and not s.vi_locked:
                s.src_key = None
    if body.timbre_from_segment is not None:
        try:
            seg = project.segment(body.timbre_from_segment)
        except KeyError:
            raise HTTPException(404, "Không có câu này")
        if not seg.style_prompt:
            raise HTTPException(400, "Câu này chưa có audio gốc (chạy bước synthesize trước)")
        dst = project.file("prompts", f"{spk}_timbre.wav")
        shutil.copyfile(project.abs(seg.style_prompt), dst)
        speaker.timbre_prompt = project.rel(dst)
    project.save()
    return job_view(job_id)


# ---------------------------------------------------------------- câu thoại
class SegmentPatch(BaseModel):
    vi_text: str | None = Field(None, max_length=2000)
    speaker: str | None = Field(None, max_length=80)
    unlock: bool = False                     # bỏ khoá, cho phép LLM dịch lại câu này


@app.patch("/api/jobs/{job_id}/segments/{seg_id}")
def patch_segment(seg_id: int, body: SegmentPatch, job_id: str = Depends(owned_job)):
    project = editable_project(job_id)
    try:
        seg = project.segment(seg_id)
    except KeyError:
        raise HTTPException(404, "Không có câu này")
    if body.vi_text is not None and body.vi_text.strip() != seg.vi_text:
        seg.vi_text = body.vi_text.strip()
        seg.vi_locked = True
    if body.speaker is not None:
        if body.speaker not in project.speakers:
            raise HTTPException(400, "Người nói không tồn tại")
        seg.speaker = body.speaker
    if body.unlock:
        seg.vi_locked = False
        seg.src_key = None
    project.save()
    return job_view(job_id)


@app.post("/api/jobs/{job_id}/segments/{seg_id}/regenerate")
def regenerate_segment(seg_id: int, job_id: str = Depends(owned_job)):
    project = editable_project(job_id)
    try:
        project.segment(seg_id).tts_key = None
    except KeyError:
        raise HTTPException(404, "Không có câu này")
    project.save()
    enqueue(job_id, REGEN_STEPS)
    return {"ok": True}


# ---------------------------------------------------------------- file
@app.get("/api/jobs/{job_id}/source")
def get_source(job_id: str = Depends(owned_job)):
    project = load_project(job_id)
    return FileResponse(project.abs(project.source))


@app.get("/api/jobs/{job_id}/files/{path:path}")
def get_file(path: str, job_id: str = Depends(owned_job)):
    root = (job_dir(job_id) / "project").resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(job_dir(job_id)) or not target.is_file():
        raise HTTPException(404, "Không có file")
    return FileResponse(target)


# Giao diện React (web/, build ra web/dist). Chưa build thì hiện trang hướng dẫn build.
web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
static_dir = web_dist if (web_dist / "index.html").exists() else Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
