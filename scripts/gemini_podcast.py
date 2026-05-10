"""Gemini TTS podcast generator.

Reads `content/<owner>-<name>/99-podcast/script.md`, calls the Gemini multi-speaker
TTS API, and writes `content/<owner>-<name>/99-podcast/podcast.wav`.

Self-skips silently when:
  - GEMINI_API_KEY is unset / placeholder in `.env` → exit 0 with `[skip]` message.
  - An audio file already exists at `99-podcast/podcast.{wav,mp3,m4a,ogg}` → exit 0.

Required env: GEMINI_API_KEY (in `.env` at project root).
Optional env: GEMINI_TTS_MODEL (default: gemini-2.5-flash-preview-tts).

Voices: Host A → Kore, Host B → Puck (Google's stock multi-speaker pair).
Output: 24kHz mono PCM wrapped in a WAV container.

Usage:
    python scripts/gemini_podcast.py <owner-name>
    python scripts/gemini_podcast.py content/<owner-name>/   # accepted for back-compat

No third-party dependencies — only the Python standard library.
Docs: https://ai.google.dev/gemini-api/docs/speech-generation
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import struct
import sys
from pathlib import Path
from urllib import error, request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAFE_PLACEHOLDER_API_KEY = "your_gemini_api_key_here"
DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"

# Older versions of `.env.example` shipped a model name that no longer exists in the API.
# Remap silently (with a one-line note) so users with stale `.env` files don't hit 404.
LEGACY_MODEL_REMAPS = {
    "gemini-2.5-flash-tts": "gemini-2.5-flash-preview-tts",
}

HOST_A_VOICE = "Kore"
HOST_B_VOICE = "Puck"

AUDIO_EXTENSIONS = ("wav", "mp3", "m4a", "ogg")

LANGUAGE_NAMES = {
    "pt-BR": "Brazilian Portuguese",
    "pt": "Portuguese",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "ja": "Japanese",
}

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

TURN_RE = re.compile(r"^\*\*(Host [A-Z]):\*\*\s+(.+?)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Config + filesystem
# ---------------------------------------------------------------------------

def load_env_file(path: Path) -> None:
    """Populate os.environ from a .env file (stdlib parser, no python-dotenv)."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_api_key() -> str | None:
    """Return the Gemini API key, or None if absent / placeholder."""
    load_env_file(PROJECT_ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or key == SAFE_PLACEHOLDER_API_KEY:
        return None
    return key


def find_existing_audio(podcast_dir: Path) -> Path | None:
    """Return path to an existing audio file in the podcast dir, or None."""
    if not podcast_dir.is_dir():
        return None
    for ext in AUDIO_EXTENSIONS:
        for f in sorted(podcast_dir.glob(f"*.{ext}")):
            return f
    return None


def resolve_podcast_dir(arg: str) -> Path:
    """Accept owner-name OR `content/<owner>/` path. Return absolute 99-podcast dir."""
    if "/" in arg or "\\" in arg:
        return (PROJECT_ROOT / arg).resolve() / "99-podcast"
    return (PROJECT_ROOT / "content" / arg).resolve() / "99-podcast"


def detect_language(podcast_dir: Path) -> str:
    """Read language from metadata.json (fallback pt-BR)."""
    meta_path = podcast_dir / "metadata.json"
    if not meta_path.is_file():
        return "pt-BR"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return str(meta.get("language") or "pt-BR")
    except (json.JSONDecodeError, OSError):
        return "pt-BR"


# ---------------------------------------------------------------------------
# Script parsing + prompt building
# ---------------------------------------------------------------------------

def parse_script(text: str) -> list[tuple[str, str]]:
    """Extract speaker turns from a podcast script.md.

    Returns [(speaker, line), ...]. Skips headings, segment markers, and notes.
    """
    turns: list[tuple[str, str]] = []
    for match in TURN_RE.finditer(text):
        speaker = match.group(1).strip()
        line = re.sub(r"\s+", " ", match.group(2).strip())
        if line:
            turns.append((speaker, line))
    return turns


def build_prompt(turns: list[tuple[str, str]], language: str) -> str:
    """Build the multi-speaker prompt in the canonical Google format."""
    lang_name = LANGUAGE_NAMES.get(language, language)
    header = f"TTS the following conversation between Host A and Host B in {lang_name}:"
    body = "\n".join(f"{speaker}: {line}" for speaker, line in turns)
    return f"{header}\n{body}"


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------

def call_gemini_tts(api_key: str, model: str, prompt: str) -> tuple[bytes, str]:
    """POST to Gemini and return (pcm_bytes, mime_type).

    Concatenates audio across multiple inlineData parts when present.
    """
    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "multiSpeakerVoiceConfig": {
                    "speakerVoiceConfigs": [
                        {
                            "speaker": "Host A",
                            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": HOST_A_VOICE}},
                        },
                        {
                            "speaker": "Host B",
                            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": HOST_B_VOICE}},
                        },
                    ]
                }
            },
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        # Long timeout: Gemini multi-speaker TTS for ~50+ turn scripts can take 3-5 minutes.
        with request.urlopen(req, timeout=600) as resp:
            response_body = resp.read()
    except error.HTTPError as e:
        details = e.read().decode("utf-8", errors="replace").replace(api_key, "<redacted>")
        if e.code in (401, 403):
            print(f"Gemini API authentication failed (HTTP {e.code}). Check GEMINI_API_KEY in .env.", file=sys.stderr)
            print(details[:500], file=sys.stderr)
            sys.exit(2)
        if e.code == 429:
            print("Gemini quota or rate limit exceeded (HTTP 429).", file=sys.stderr)
            print(details[:500], file=sys.stderr)
            sys.exit(1)
        print(f"Gemini API error (HTTP {e.code}):", file=sys.stderr)
        print(details[:1000], file=sys.stderr)
        sys.exit(1)
    except (error.URLError, TimeoutError) as e:
        print(f"Network error calling Gemini API: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(response_body)
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        preview = response_body.decode("utf-8", errors="replace")[:500]
        print(f"Unexpected Gemini response shape: {e}", file=sys.stderr)
        print(preview, file=sys.stderr)
        sys.exit(1)

    audio_parts = [p for p in parts if isinstance(p, dict) and "inlineData" in p]
    if not audio_parts:
        print("Gemini response contains no audio parts.", file=sys.stderr)
        sys.exit(1)

    pcm = b"".join(base64.b64decode(p["inlineData"]["data"]) for p in audio_parts)
    mime = audio_parts[0]["inlineData"].get("mimeType", "audio/L16;codec=pcm;rate=24000")
    return pcm, mime


# ---------------------------------------------------------------------------
# Audio packaging
# ---------------------------------------------------------------------------

def parse_sample_rate(mime: str) -> int:
    """Extract sample rate from a mimeType like `audio/L16;codec=pcm;rate=24000`."""
    m = re.search(r"rate=(\d+)", mime)
    return int(m.group(1)) if m else 24000


def make_wav(pcm: bytes, sample_rate: int = 24000, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """Wrap raw PCM in a RIFF/WAVE container header."""
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits_per_sample)
        + b"data"
        + struct.pack("<I", data_size)
        + pcm
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Generate podcast audio via Gemini TTS multi-speaker.")
    parser.add_argument("target", help="Course owner-name (e.g. 'sindresorhus-is-plain-obj') or content/<owner>/ path.")
    args = parser.parse_args(argv)

    podcast_dir = resolve_podcast_dir(args.target)
    if not podcast_dir.is_dir():
        print(f"Podcast dir not found: {podcast_dir}", file=sys.stderr)
        print("hint: run /genie-learn first to populate content/.", file=sys.stderr)
        return 2

    # Idempotency: skip if any audio file is already present.
    existing = find_existing_audio(podcast_dir)
    if existing is not None:
        try:
            rel = existing.relative_to(PROJECT_ROOT)
        except ValueError:
            rel = existing
        print(f"[skip] audio already exists at {rel} (delete it to regenerate)")
        return 0

    # Verify API key is available.
    api_key = get_api_key()
    if api_key is None:
        print("[skip] no GEMINI_API_KEY set in .env (or placeholder). Audio generation skipped.")
        return 0

    # Read script and parse turns.
    script_path = podcast_dir / "script.md"
    if not script_path.is_file():
        print(f"Podcast script not found: {script_path}", file=sys.stderr)
        return 2
    script_text = script_path.read_text(encoding="utf-8")
    turns = parse_script(script_text)
    if len(turns) < 4:
        print(f"Podcast script has too few speaker turns ({len(turns)}). Need at least 4.", file=sys.stderr)
        return 2

    # Build prompt + call Gemini.
    language = detect_language(podcast_dir)
    prompt = build_prompt(turns, language)
    model = os.environ.get("GEMINI_TTS_MODEL", "").strip() or DEFAULT_TTS_MODEL
    if model in LEGACY_MODEL_REMAPS:
        new_model = LEGACY_MODEL_REMAPS[model]
        print(f"[gemini] note: GEMINI_TTS_MODEL='{model}' is deprecated; remapping to '{new_model}'. Update your .env to silence this.")
        model = new_model

    print(f"[gemini] {len(turns)} turns | model={model} | language={language} | voices=Kore+Puck")
    print("[gemini] calling Gemini TTS API (30s-5min depending on script length)...")
    pcm_bytes, mime = call_gemini_tts(api_key, model, prompt)

    # Wrap and write WAV.
    sample_rate = parse_sample_rate(mime)
    wav_bytes = make_wav(pcm_bytes, sample_rate=sample_rate, channels=1, bits_per_sample=16)
    output_path = podcast_dir / "podcast.wav"
    output_path.write_bytes(wav_bytes)

    # Summary.
    size_mb = len(wav_bytes) / (1024 * 1024)
    duration_s = len(pcm_bytes) / (sample_rate * 2)  # 16-bit mono → 2 bytes/sample
    minutes = int(duration_s // 60)
    seconds = int(duration_s % 60)
    try:
        rel = output_path.relative_to(PROJECT_ROOT)
    except ValueError:
        rel = output_path
    print(f"Wrote {rel} ({size_mb:.1f} MB, ~{minutes}m {seconds}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
