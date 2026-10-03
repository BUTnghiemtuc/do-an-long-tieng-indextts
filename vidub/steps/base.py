from __future__ import annotations

from ..pipeline import Context
from ..project import Project


class BaseStep:
    name = "base"
    # Các khoá trong project.tracks / project.outputs mà bước này tạo ra.
    produces_tracks: tuple[str, ...] = ()

    def fingerprint(self, project: Project, ctx: Context) -> dict | None:
        return None

    def outputs_exist(self, project: Project) -> bool:
        return all(
            k in project.tracks and project.abs(project.tracks[k]).exists() for k in self.produces_tracks
        )

    def run(self, project: Project, ctx: Context) -> Project:
        raise NotImplementedError
