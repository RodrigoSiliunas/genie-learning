"""Unit tests for scripts/gemini_podcast.py (stdlib-only Gemini TTS)."""

from __future__ import annotations

import importlib.util
import os
import struct
import sys
from pathlib import Path

import pytest

# Load gemini_podcast as a module.
_PODCAST_PATH = Path(__file__).resolve().parents[1] / "scripts" / "gemini_podcast.py"
spec = importlib.util.spec_from_file_location("gemini_podcast", _PODCAST_PATH)
gemini_podcast = importlib.util.module_from_spec(spec)
sys.modules["gemini_podcast"] = gemini_podcast
spec.loader.exec_module(gemini_podcast)


class TestLoadEnvFile:
    def test_loads_key_value_pairs(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
        # Ensure keys are not already present
        os.environ.pop("FOO", None)
        os.environ.pop("BAZ", None)
        gemini_podcast.load_env_file(env)
        assert os.environ.get("FOO") == "bar"
        assert os.environ.get("BAZ") == "qux"
        os.environ.pop("FOO", None)
        os.environ.pop("BAZ", None)

    def test_skips_comments_and_empty_lines(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("# comment\n\nKEY=value\n", encoding="utf-8")
        os.environ.pop("KEY", None)
        gemini_podcast.load_env_file(env)
        assert os.environ.get("KEY") == "value"
        os.environ.pop("KEY", None)

    def test_missing_file_is_noop(self, tmp_path: Path) -> None:
        gemini_podcast.load_env_file(tmp_path / "nope.env")


class TestGetApiKey:
    def test_returns_none_when_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gemini_podcast, "PROJECT_ROOT", tmp_path)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert gemini_podcast.get_api_key() is None

    def test_returns_none_for_placeholder(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gemini_podcast, "PROJECT_ROOT", tmp_path)
        env = tmp_path / ".env"
        env.write_text("GEMINI_API_KEY=your_gemini_api_key_here\n", encoding="utf-8")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert gemini_podcast.get_api_key() is None

    def test_returns_real_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gemini_podcast, "PROJECT_ROOT", tmp_path)
        env = tmp_path / ".env"
        env.write_text("GEMINI_API_KEY=real-key-123\n", encoding="utf-8")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert gemini_podcast.get_api_key() == "real-key-123"


class TestFindExistingAudio:
    def test_finds_wav(self, tmp_path: Path) -> None:
        d = tmp_path / "99-podcast"
        d.mkdir()
        f = d / "podcast.wav"
        f.write_text("RIFF", encoding="utf-8")
        assert gemini_podcast.find_existing_audio(d) == f

    def test_prefers_alphabetical_order(self, tmp_path: Path) -> None:
        d = tmp_path / "99-podcast"
        d.mkdir()
        (d / "z.ogg").write_text("ogg", encoding="utf-8")
        (d / "a.mp3").write_text("mp3", encoding="utf-8")
        assert gemini_podcast.find_existing_audio(d).name == "a.mp3"

    def test_none_when_empty(self, tmp_path: Path) -> None:
        d = tmp_path / "99-podcast"
        d.mkdir()
        assert gemini_podcast.find_existing_audio(d) is None


class TestResolvePodcastDir:
    def test_owner_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gemini_podcast, "PROJECT_ROOT", tmp_path)
        result = gemini_podcast.resolve_podcast_dir("foo-bar")
        assert result == tmp_path / "content" / "foo-bar" / "99-podcast"

    def test_content_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gemini_podcast, "PROJECT_ROOT", tmp_path)
        result = gemini_podcast.resolve_podcast_dir("content/foo-bar/")
        assert result == tmp_path / "content" / "foo-bar" / "99-podcast"


class TestDetectLanguage:
    def test_from_metadata(self, tmp_path: Path) -> None:
        d = tmp_path / "99-podcast"
        d.mkdir()
        (d / "metadata.json").write_text('{"language": "en"}', encoding="utf-8")
        assert gemini_podcast.detect_language(d) == "en"

    def test_fallback_pt_br(self, tmp_path: Path) -> None:
        d = tmp_path / "99-podcast"
        d.mkdir()
        assert gemini_podcast.detect_language(d) == "pt-BR"

    def test_fallback_on_bad_json(self, tmp_path: Path) -> None:
        d = tmp_path / "99-podcast"
        d.mkdir()
        (d / "metadata.json").write_text("not json", encoding="utf-8")
        assert gemini_podcast.detect_language(d) == "pt-BR"


class TestParseScript:
    def test_extracts_turns(self) -> None:
        text = "**Host A:** Hello\n**Host B:** Hi there\n**Host A:** How are you?"
        turns = gemini_podcast.parse_script(text)
        assert turns == [
            ("Host A", "Hello"),
            ("Host B", "Hi there"),
            ("Host A", "How are you?"),
        ]

    def test_skips_headings_and_notes(self) -> None:
        text = "# Podcast\n\n**Host A:** Welcome\n\n---\n\n**Host B:** Thanks"
        turns = gemini_podcast.parse_script(text)
        assert turns == [("Host A", "Welcome"), ("Host B", "Thanks")]

    def test_empty_result(self) -> None:
        assert gemini_podcast.parse_script("no speakers here") == []


class TestBuildPrompt:
    def test_formats_conversation(self) -> None:
        turns = [("Host A", "Hello"), ("Host B", "Hi")]
        prompt = gemini_podcast.build_prompt(turns, "en")
        assert prompt.startswith("TTS the following conversation between Host A and Host B in English:")
        assert "Host A: Hello" in prompt
        assert "Host B: Hi" in prompt

    def test_uses_language_name(self) -> None:
        turns = [("Host A", "Oi")]
        prompt = gemini_podcast.build_prompt(turns, "pt-BR")
        assert "Brazilian Portuguese" in prompt


class TestParseSampleRate:
    def test_extracts_rate(self) -> None:
        assert gemini_podcast.parse_sample_rate("audio/L16;codec=pcm;rate=24000") == 24000

    def test_fallback_to_24000(self) -> None:
        assert gemini_podcast.parse_sample_rate("audio/wav") == 24000


class TestMakeWav:
    def test_produces_valid_header(self) -> None:
        pcm = b"\x00\x01" * 1000
        wav = gemini_podcast.make_wav(pcm, sample_rate=44100, channels=2, bits_per_sample=16)
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"
        assert wav[12:16] == b"fmt "
        # fmt chunk size
        assert struct.unpack("<I", wav[16:20])[0] == 16
        # audio format = PCM
        assert struct.unpack("<H", wav[20:22])[0] == 1
        # channels
        assert struct.unpack("<H", wav[22:24])[0] == 2
        # sample rate
        assert struct.unpack("<I", wav[24:28])[0] == 44100
        # bits per sample
        assert struct.unpack("<H", wav[34:36])[0] == 16
        assert wav[36:40] == b"data"
        assert struct.unpack("<I", wav[40:44])[0] == len(pcm)

    def test_data_follows_header(self) -> None:
        pcm = b"\xAB\xCD" * 500
        wav = gemini_podcast.make_wav(pcm)
        assert wav[44:] == pcm
