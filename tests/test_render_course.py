"""Unit tests for scripts/render_course.py quiz regex case-insensitivity."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_RENDER_COURSE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render_course.py"
spec = importlib.util.spec_from_file_location("render_course", _RENDER_COURSE_PATH)
render_course = importlib.util.module_from_spec(spec)
sys.modules["render_course"] = render_course
spec.loader.exec_module(render_course)


class TestParseQuizCaseInsensitive:
    def test_lowercase_questions_heading(self) -> None:
        raw = "# Quiz\n\n## questions\n\n1. **Short answer:** What?\n\n## answer key\n\n1. Because.\n"
        quiz = render_course.parse_quiz(raw, "q")
        assert quiz is not None
        assert len(quiz["questions"]) == 1
        assert quiz["questions"][0]["answer"] == "Because."

    def test_mixed_case_heading(self) -> None:
        raw = "# Quiz\n\n## QUESTIONS\n\n1. **Short answer:** Hmm?\n\n## ANSWER KEY\n\n1. Yes.\n"
        quiz = render_course.parse_quiz(raw, "q")
        assert quiz is not None
        assert len(quiz["questions"]) == 1
        assert quiz["questions"][0]["answer"] == "Yes."
