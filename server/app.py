"""API web: tạo job, đọc/sửa dự án JSON, tạo lại câu, trả file.

Chạy:  uvicorn server.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from vidub.pipeline import rtf_report
from vidub.project import Project

from .jobs import BUSY_STATES, DATA_DIR, enqueue, job_dir, new_job_id, read_status, write_status

DISCLAIMER = "Giọng nói trong video được tạo bởi AI, chỉ dùng cho mục đích nghiên cứu."
REGEN_STEPS = ["synthesize", "align", "mix"]
RENDER_STEPS = ["translate", "synthesize", "align", "mix"]

app = FastAPI(title="vidub", version="0.1.0")


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


@app.post("/api/jobs")
async def create_job(video: UploadFile = File(...), src_lang: str = Form("en"),
                     subtitles: UploadFile | None = File(None)):
    job_id = new_job_id()
    jdir = job_dir(job_id)
    (jdir / "input").mkdir(parents=True)
    suffix = Path(video.filename or "clip.mp4").suffix or ".mp4"
    src = jdir / "input" / f"source{suffix}"
    with src.open("wb") as f:
        shutil.copyfileobj(video.file, f)
    if subtitles is not None and subtitles.filename:
        with src.with_suffix(".srt").open("wb") as f:
            shutil.copyfileobj(subtitles.file, f)
    clip_id = Path(video.filename or "clip").stem
    Project.create(jdir / "project", src, clip_id=clip_id, src_lang=src_lang)
    write_status(jdir, state="created", filename=video.filename)
    enqueue(job_id, None)
    return {"id": job_id}


@app.get("/api/jobs")
def list_jobs():
    if not DATA_DIR.exists():
        return []
    out = []
    for d in sorted(DATA_DIR.iterdir(), reverse=True):
        if (d / "project" / "project.json").exists():
            st = read_status(d.name)
            out.append({"id": d.name, "filename": st.get("filename"), "state": st.get("state")})
    return out


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return job_view(job_id)


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    """SSE: đẩy trạng thái mỗi khi status.json đổi, dừng khi job xong hoặc lỗi."""
    job_dir(job_id)

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
def render(job_id: str):
    """Áp dụng các sửa đổi: dịch câu chưa dịch, sinh lại câu đã đổi, trộn lại."""
    editable_project(job_id)
    enqueue(job_id, RENDER_STEPS)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/rerun")
def rerun(job_id: str, from_step: str = "extract", force: bool = False):
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
    name: str | None = None
    notes: str | None = None
    timbre_from_segment: int | None = None   # lấy câu này làm giọng mẫu


@app.patch("/api/jobs/{job_id}/speakers/{spk}")
def patch_speaker(job_id: str, spk: str, body: SpeakerPatch):
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
        seg = project.segment(body.timbre_from_segment)
        if not seg.style_prompt:
            raise HTTPException(400, "Câu này chưa có audio gốc (chạy bước synthesize trước)")
        dst = project.file("prompts", f"{spk}_timbre.wav")
        shutil.copyfile(project.abs(seg.style_prompt), dst)
        speaker.timbre_prompt = project.rel(dst)
    project.save()
    return job_view(job_id)


# ---------------------------------------------------------------- câu thoại
class SegmentPatch(BaseModel):
    vi_text: str | None = None
    speaker: str | None = None
    unlock: bool = False                     # bỏ khoá, cho phép LLM dịch lại câu này


@app.patch("/api/jobs/{job_id}/segments/{seg_id}")
def patch_segment(job_id: str, seg_id: int, body: SegmentPatch):
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
def regenerate_segment(job_id: str, seg_id: int):
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
def get_source(job_id: str):
    project = load_project(job_id)
    return FileResponse(project.abs(project.source))


@app.get("/api/jobs/{job_id}/files/{path:path}")
def get_file(job_id: str, path: str):
    root = (job_dir(job_id) / "project").resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(job_dir(job_id)) or not target.is_file():
        raise HTTPException(404, "Không có file")
    return FileResponse(target)


static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
