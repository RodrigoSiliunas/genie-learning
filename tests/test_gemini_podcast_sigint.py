"""Tests for KeyboardInterrupt handling in gemini_podcast.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PODCAST_PATH = Path(__file__).resolve().parents[1] / "scripts" / "gemini_podcast.py"
spec = importlib.util.spec_from_file_location("gemini_podcast", _PODCAST_PATH)
gemini_podcast = importlib.util.module_from_spec(spec)
sys.modules["gemini_podcast"] = gemini_podcast
spec.loader.exec_module(gemini_podcast)


class TestSigintHandling:
    def test_sigint_during_api_call_returns_130(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        podcast_dir = tmp_path / "content" / "test" / "99-podcast"
        podcast_dir.mkdir(parents=True)
        (podcast_dir / "script.md").write_text(
            "**Host A:** Hello\n**Host B:** Hi\n**Host A:** How are you?\n**Host B:** Great!\n**Host A:** Let's begin.\n",
            encoding="utf-8",
        )
        (podcast_dir / "metadata.json").write_text('{"language":"en"}', encoding="utf-8")

        monkeypatch.setattr(gemini_podcast, "PROJECT_ROOT", tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr(gemini_podcast, "get_api_key", lambda: "fake-key")

        with patch.object(gemini_podcast, "call_gemini_tts", side_effect=KeyboardInterrupt):
            rc = gemini_podcast.main(["test"])
        assert rc == 130
        # No partial file should be left behind
        assert not (podcast_dir / "podcast.wav").exists()
