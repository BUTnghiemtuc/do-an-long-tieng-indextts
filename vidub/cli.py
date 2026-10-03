"""Dòng lệnh.

  vidub run clip.mp4 -o runs/clip                 # chạy cả pipeline
  vidub run runs/clip --from translate            # chạy lại từ bước dịch
  vidub regen runs/clip --segment 12 --text "..."  # sửa và tạo lại một câu
  vidub show runs/clip                            # bảng câu thoại + cảnh báo
  vidub rtf runs/clip                             # thời gian từng bước, RTF
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import load_config
from .pipeline import Context, rtf_report, run_pipeline, select_steps, step_names
from .project import PROJECT_FILE, Project

REGEN_STEPS = ["synthesize", "align", "mix"]


def open_or_create(target: str, out: str | None, cfg: dict) -> Project:
    path = Path(target)
    if path.is_dir() and (path / PROJECT_FILE).exists():
        return Project.load(path)
    if path.name == PROJECT_FILE:
        return Project.load(path.parent)
    if not path.is_file():
        raise SystemExit(f"Không tìm thấy video hoặc thư mục dự án: {target}")
    project_dir = Path(out) if out else Path("runs") / path.stem
    if (project_dir / PROJECT_FILE).exists():
        return Project.load(project_dir)
    return Project.create(project_dir, path, src_lang=cfg["src_lang"], tgt_lang=cfg["tgt_lang"])


def progress_printer(step: str, frac: float, msg: str) -> None:
    print(f"  [{step:<10}] {frac * 100:5.1f}%  {msg}", file=sys.stderr)


def cmd_run(args) -> None:
    cfg = load_config(args.config, args.set)
    project = open_or_create(args.target, args.output, cfg)
    steps = select_steps(args.steps, args.from_step, args.to_step)
    ctx = Context(cfg=cfg, force=args.force, progress=progress_printer)
    project = run_pipeline(project, ctx, steps)
    print(f"Dự án: {project.dir / PROJECT_FILE}")
    for k, v in project.outputs.items():
        print(f"  {k}: {project.abs(v)}")


def cmd_regen(args) -> None:
    cfg = load_config(args.config, args.set)
    project = Project.load(args.project)
    seg = project.segment(args.segment)
    if args.text is not None:
        seg.vi_text = args.text
        seg.vi_locked = True
    if args.speaker is not None:
        seg.speaker = args.speaker
    seg.tts_key = None          # buộc sinh lại câu này
    project.save()
    run_pipeline(project, Context(cfg=cfg, progress=progress_printer), REGEN_STEPS)


def cmd_show(args) -> None:
    project = Project.load(args.project)
    for s in project.segments:
        ratio = f"{s.duration_ratio:.2f}" if s.duration_ratio else "  - "
        warn = f"  ! {'; '.join(s.warnings)}" if s.warnings else ""
        print(f"{s.id:4d} {s.start:7.2f}-{s.end:7.2f} {project.speaker_name(s.speaker):<12} "
              f"{ratio} {s.status:<11} {s.src_text}\n{'':41}-> {s.vi_text}{warn}")


def cmd_rtf(args) -> None:
    print(json.dumps(rtf_report(Project.load(args.project)), indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="vidub", description="Lồng tiếng phim tự động sang tiếng Việt")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_cfg(sp):
        sp.add_argument("-c", "--config", action="append", default=[], help="file YAML ghi đè (lặp được)")
        sp.add_argument("--set", action="append", default=[], metavar="KHOA=GIATRI",
                        help="ghi đè một khoá, vd --set synthesize.backend=mock")

    r = sub.add_parser("run", help="chạy pipeline cho một video hoặc dự án có sẵn")
    r.add_argument("target", help="video đầu vào hoặc thư mục dự án")
    r.add_argument("-o", "--output", help="thư mục dự án (mặc định runs/<tên clip>)")
    r.add_argument("--steps", nargs="+", choices=step_names(), help="chỉ chạy các bước này")
    r.add_argument("--from", dest="from_step", choices=step_names())
    r.add_argument("--to", dest="to_step", choices=step_names())
    r.add_argument("--force", action="store_true", help="bỏ qua cache")
    add_cfg(r)
    r.set_defaults(fn=cmd_run)

    g = sub.add_parser("regen", help="sửa và tạo lại một câu")
    g.add_argument("project")
    g.add_argument("--segment", type=int, required=True)
    g.add_argument("--text", help="bản dịch mới")
    g.add_argument("--speaker", help="đổi người nói (vd SPEAKER_01)")
    add_cfg(g)
    g.set_defaults(fn=cmd_regen)

    s = sub.add_parser("show", help="in bảng câu thoại")
    s.add_argument("project")
    s.set_defaults(fn=cmd_show)

    t = sub.add_parser("rtf", help="thời gian xử lý và RTF")
    t.add_argument("project")
    t.set_defaults(fn=cmd_rtf)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    args.fn(args)


if __name__ == "__main__":
    main()
