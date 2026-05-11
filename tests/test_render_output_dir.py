"""Tests for --output-dir option in render_course.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_RENDER_COURSE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render_course.py"
spec = importlib.util.spec_from_file_location("render_course", _RENDER_COURSE_PATH)
render_course = importlib.util.module_from_spec(spec)
sys.modules["render_course"] = render_course
spec.loader.exec_module(render_course)


class TestOutputDir:
    def test_writes_to_custom_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        content_dir = tmp_path / "content" / "test-course"
        content_dir.mkdir(parents=True)
        (content_dir / "00-overview.md").write_text("# Test\n", encoding="utf-8")
        (content_dir / "99-podcast").mkdir()
        (content_dir / "99-podcast" / "metadata.json").write_text('{"language":"en"}', encoding="utf-8")

        template_src = Path(__file__).resolve().parents[1] / "scripts" / "templates" / "course.html"
        template_dst = tmp_path / "scripts" / "templates"
        template_dst.mkdir(parents=True)
        template_dst.joinpath("course.html").write_text(template_src.read_text(encoding="utf-8"), encoding="utf-8")

        # copy_assets() also needs course_assets/ next to the template
        assets_src = template_src.parent / "course_assets"
        if assets_src.is_dir():
            assets_dst = template_dst / "course_assets"
            assets_dst.mkdir(parents=True, exist_ok=True)
            for f in assets_src.iterdir():
                if f.is_file():
                    assets_dst.joinpath(f.name).write_bytes(f.read_bytes())

        custom_dir = tmp_path / "dist"
        monkeypatch.chdir(tmp_path)
        rc = render_course.main(["test-course", "--project-root", str(tmp_path), "--output-dir", str(custom_dir)])
        assert rc == 0
        assert (custom_dir / "index.html").is_file()
        # Original content dir should not have index.html
        assert not (content_dir / "index.html").exists()
