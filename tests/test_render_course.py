"""Unit tests for scripts/render_course.py (stdlib-only renderer)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load render_course as a module so tests run without a pip-install step.
_RENDER_COURSE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render_course.py"
spec = importlib.util.spec_from_file_location("render_course", _RENDER_COURSE_PATH)
render_course = importlib.util.module_from_spec(spec)
sys.modules["render_course"] = render_course
spec.loader.exec_module(render_course)


class TestReadText:
    def test_reads_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.md"
        f.write_text("hello", encoding="utf-8")
        assert render_course.read_text(f) == "hello"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert render_course.read_text(tmp_path / "nope.md") is None

    def test_strips_bom(self, tmp_path: Path) -> None:
        f = tmp_path / "bom.md"
        f.write_text("\ufeffhello", encoding="utf-8")
        assert render_course.read_text(f) == "hello"


class TestParseFirstH1:
    def test_finds_h1(self) -> None:
        assert render_course.parse_first_h1("# Hello world\n\nfoo") == "Hello world"

    def test_returns_none_when_missing(self) -> None:
        assert render_course.parse_first_h1("## H2\nfoo") is None

    def test_returns_none_for_none_input(self) -> None:
        assert render_course.parse_first_h1(None) is None


class TestParseGlossary:
    def test_parses_letters_and_terms(self) -> None:
        raw = """# Glossário

## A

### **API**
Application Programming Interface.

### **AST**
Abstract Syntax Tree.

## B

### **Bash**
Unix shell.
"""
        glossary = render_course.parse_glossary(raw)
        assert len(glossary) == 2
        assert glossary[0]["letter"] == "A"
        assert len(glossary[0]["terms"]) == 2
        assert glossary[0]["terms"][0]["term"] == "API"
        assert glossary[0]["terms"][0]["definition"] == "Application Programming Interface."
        assert glossary[0]["terms"][0]["anchor"] == "api"
        assert glossary[1]["letter"] == "B"

    def test_skips_non_letter_sections(self) -> None:
        raw = """# G

## Symbols

### **=>**
Arrow operator.

## C

### **CSS**
Cascading Style Sheets.
"""
        glossary = render_course.parse_glossary(raw)
        assert len(glossary) == 1
        assert glossary[0]["letter"] == "C"

    def test_empty_glossary(self) -> None:
        assert render_course.parse_glossary("") == []
        assert render_course.parse_glossary(None) == []


class TestSplitNumbered:
    def test_splits_items(self) -> None:
        block = "1. First\n2. Second\n3. Third"
        items = render_course._split_numbered(block)
        assert items == [(1, "First"), (2, "Second"), (3, "Third")]

    def test_empty_block(self) -> None:
        assert render_course._split_numbered("") == []
        assert render_course._split_numbered("no numbers here") == []


class TestDetectKind:
    def test_detects_mc(self) -> None:
        kind, prompt = render_course._detect_kind("**Múltipla escolha:** What is 2+2?")
        assert kind == "mc"
        assert prompt == "What is 2+2?"

    def test_detects_trace(self) -> None:
        kind, prompt = render_course._detect_kind("**Trace the flow:** Follow the data")
        assert kind == "trace"
        assert prompt == "Follow the data"

    def test_detects_short(self) -> None:
        kind, prompt = render_course._detect_kind("**Short answer:** Explain")
        assert kind == "short"
        assert prompt == "Explain"

    def test_fallback_to_short(self) -> None:
        kind, prompt = render_course._detect_kind("Plain question text")
        assert kind == "short"
        assert prompt == "Plain question text"


class TestParseQuiz:
    def test_parse_mc_quiz(self) -> None:
        raw = """# General Quiz

## Questions

1. **Multiple choice:** What is the capital of France?
   - A. London
   - B. Paris
   - C. Berlin

2. **Short answer:** Name one French dish.

## Answer key

1. **B.** Paris is the capital.
2. **Croissant**
"""
        quiz = render_course.parse_quiz(raw, "general")
        assert quiz is not None
        assert quiz["id"] == "general"
        assert quiz["title"] == "General Quiz"
        assert len(quiz["questions"]) == 2

        q1 = quiz["questions"][0]
        assert q1["kind"] == "mc"
        assert q1["answer_key"] == "B"
        assert "Paris is the capital." in q1["explanation"]
        assert len(q1["options"]) == 3

        q2 = quiz["questions"][1]
        assert q2["kind"] == "short"
        assert q2["answer"] == "**Croissant**"

    def test_plain_answer_letter_fallback(self) -> None:
        raw = """# Quiz

## Questions

1. **Multiple choice:** Pick one.
   - A. Alpha
   - B. Beta

## Answer key

1. A. Alpha is correct.
"""
        quiz = render_course.parse_quiz(raw, "q")
        assert quiz["questions"][0]["answer_key"] == "A"

    def test_no_questions_heading(self) -> None:
        raw = "# Empty\n\nJust some text."
        quiz = render_course.parse_quiz(raw, "empty")
        assert quiz is not None
        assert quiz["questions"] == []

    def test_empty_input(self) -> None:
        assert render_course.parse_quiz(None, "x") is None
        assert render_course.parse_quiz("", "x") is None


class TestDeriveFlashcards:
    def test_from_glossary(self) -> None:
        glossary = [
            {
                "letter": "A",
                "terms": [
                    {"term": "API", "definition": "Application Programming Interface.", "anchor": "api"},
                ],
            }
        ]
        cards = render_course.derive_flashcards(glossary, [])
        assert len(cards) == 1
        assert cards[0]["front"] == "API"
        assert cards[0]["back"] == "Application Programming Interface."
        assert cards[0]["source"] == "glossary"

    def test_from_quizzes(self) -> None:
        glossary = []
        quizzes = [
            {
                "id": "q1",
                "questions": [
                    {
                        "kind": "mc",
                        "prompt": "What is 2+2?",
                        "options": [{"key": "A", "text": "4"}, {"key": "B", "text": "5"}],
                        "answer_key": "A",
                        "explanation": "Basic math.",
                    }
                ],
            }
        ]
        cards = render_course.derive_flashcards(glossary, quizzes)
        assert len(cards) == 1
        assert cards[0]["front"] == "What is 2+2?"
        assert "4" in cards[0]["back"]
        assert "Basic math." in cards[0]["back"]
        assert cards[0]["source"] == "quiz"

    def test_multiline_definition_takes_first_para(self) -> None:
        glossary = [
            {
                "letter": "A",
                "terms": [
                    {"term": "Foo", "definition": "First paragraph.\n\nSecond paragraph.", "anchor": "foo"},
                ],
            }
        ]
        cards = render_course.derive_flashcards(glossary, [])
        assert cards[0]["back"] == "First paragraph."


class TestSlugify:
    def test_basic(self) -> None:
        assert render_course.slugify("Hello World") == "hello-world"

    def test_special_chars(self) -> None:
        assert render_course.slugify("C++ & Python!!!") == "c-python"

    def test_empty_fallback(self) -> None:
        assert render_course.slugify("!!!") == "module"
