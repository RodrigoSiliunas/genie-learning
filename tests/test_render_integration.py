"""Integration tests for scripts/render_course.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_RENDER_COURSE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render_course.py"
spec = importlib.util.spec_from_file_location("render_course", _RENDER_COURSE_PATH)
render_course = importlib.util.module_from_spec(spec)
sys.modules["render_course"] = render_course
spec.loader.exec_module(render_course)


class TestCheckMode:
    def test_check_mode_valid_course(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        # Build a minimal valid course
        content_dir = tmp_path / "content" / "test-course"
        content_dir.mkdir(parents=True)
        (content_dir / "00-overview.md").write_text("# Test Course\n", encoding="utf-8")
        (content_dir / "10-tutorial.md").write_text("# Tutorial\n", encoding="utf-8")
        (content_dir / "20-glossary.md").write_text("# Glossary\n", encoding="utf-8")
        (content_dir / "30-modules").mkdir()
        (content_dir / "30-modules" / "01-mod.md").write_text("# Module\n", encoding="utf-8")
        (content_dir / "40-quizzes").mkdir()
        (content_dir / "40-quizzes" / "00-general.md").write_text(
            "# Quiz\n\n## Questions\n\n1. **Short answer:** Q\n\n## Answer key\n\n1. A\n",
            encoding="utf-8",
        )
        (content_dir / "99-podcast").mkdir()
        (content_dir / "99-podcast" / "metadata.json").write_text('{"language":"en"}', encoding="utf-8")

        # Copy template into the temp project root
        template_src = Path(__file__).resolve().parents[1] / "scripts" / "templates" / "course.html"
        template_dst = tmp_path / "scripts" / "templates"
        template_dst.mkdir(parents=True)
        template_dst.joinpath("course.html").write_text(template_src.read_text(encoding="utf-8"), encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        rc = render_course.main(["test-course", "--check", "--project-root", str(tmp_path)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "check: course 'test-course' is valid" in captured.out
        assert "Modules: 1" in captured.out
        # Ensure no HTML was written
        assert not (content_dir / "index.html").exists()

    def test_check_mode_missing_overview(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        content_dir = tmp_path / "content" / "bad-course"
        content_dir.mkdir(parents=True)
        (content_dir / "99-podcast").mkdir()
        (content_dir / "99-podcast" / "metadata.json").write_text('{"language":"en"}', encoding="utf-8")

        template_src = Path(__file__).resolve().parents[1] / "scripts" / "templates" / "course.html"
        template_dst = tmp_path / "scripts" / "templates"
        template_dst.mkdir(parents=True)
        template_dst.joinpath("course.html").write_text(template_src.read_text(encoding="utf-8"), encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            render_course.main(["bad-course", "--check", "--project-root", str(tmp_path)])
        assert exc_info.value.code != 0
        assert "00-overview.md" in str(exc_info.value)
