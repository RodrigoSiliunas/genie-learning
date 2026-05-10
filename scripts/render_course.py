"""Render a generated Genie Learning course as a single interactive HTML file.

Reads `content/<owner>-<name>/` produced by /genie-learn and writes
`content/<owner>-<name>/index.html` — a self-contained Vue 3 + Tailwind page
that lets a learner browse the overview, tutorial, glossary, modules, quizzes,
flashcards (derived from glossary + multiple-choice quizzes), and podcast.

Usage:
    python scripts/render_course.py <owner-name>

No third-party dependencies — only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Chrome i18n strings
# ---------------------------------------------------------------------------

CHROME_STRINGS: dict[str, dict[str, str]] = {
    "pt-BR": {
        "overview": "Visão geral",
        "tutorial": "Tutorial",
        "modules": "Módulos",
        "glossary": "Glossário",
        "quizzes": "Simulados",
        "flashcards": "Flashcards",
        "podcast": "Podcast",
        "next": "Próximo",
        "previous": "Anterior",
        "reveal_answer": "Revelar gabarito",
        "explanation": "Explicação",
        "reference_answer": "Resposta de referência",
        "correct": "Correto",
        "incorrect": "Incorreto",
        "knew_it": "Sabia",
        "didnt_know": "Não sabia",
        "search_terms": "Buscar termo...",
        "show_only_unknown": "Só não sabidos",
        "show_all": "Todos",
        "audio_coming_soon": "Áudio em breve",
        "audio_hint": "Coloque um arquivo .mp3, .wav ou .m4a em 99-podcast/ e re-renderize.",
        "general_quiz": "Simulado geral",
        "module_quiz": "Quiz do módulo",
        "select_quiz": "Selecione um simulado acima.",
        "select_module": "Selecione um módulo",
        "back_to_modules": "Voltar aos módulos",
        "your_answer": "Sua resposta...",
        "your_progress": "Seu progresso",
        "answered": "respondidas",
        "no_flashcards": "Nenhum flashcard disponível.",
        "no_results": "Nenhum resultado.",
        "term_label": "Termo",
        "question_label": "Pergunta",
        "front": "Frente",
        "back": "Verso",
        "click_to_flip": "Clique para virar",
        "known_marker": "marcados",
        "mc_label": "Múltipla escolha",
        "short_label": "Resposta curta",
        "trace_label": "Trace o fluxo",
        "listen_label": "Ouvir",
        "menu": "Menu",
        "source_repo": "Repositório fonte",
        "hero_eyebrow": "Curso gerado por Genie Learning",
        "hero_subtitle": "Navegue pelos módulos, faça os simulados e revise os flashcards no seu ritmo. Tudo offline.",
        "start_tutorial": "Começar o tutorial",
        "modules_subtitle": "Cada módulo é uma aula focada. Selecione um para começar.",
        "glossary_subtitle": "Termos específicos do projeto, com referências para o código.",
        "quizzes_subtitle": "Simulados ancorados no conteúdo do curso. Seu progresso é salvo localmente.",
        "flashcards_subtitle": "Cards derivados do glossário e dos simulados. Marque o que você já sabe.",
        "podcast_subtitle": "Roteiro pronto para TTS. O player aparece automaticamente quando o áudio existir.",
        "footer_built": "Gerado por",
        "not_available": "Conteúdo não disponível.",
        "progress_hint": "Seu progresso fica salvo neste navegador (localStorage).",
    },
    "en": {
        "overview": "Overview",
        "tutorial": "Tutorial",
        "modules": "Modules",
        "glossary": "Glossary",
        "quizzes": "Quizzes",
        "flashcards": "Flashcards",
        "podcast": "Podcast",
        "next": "Next",
        "previous": "Previous",
        "reveal_answer": "Reveal answer",
        "explanation": "Explanation",
        "reference_answer": "Reference answer",
        "correct": "Correct",
        "incorrect": "Incorrect",
        "knew_it": "I knew it",
        "didnt_know": "Didn't know",
        "search_terms": "Search terms...",
        "show_only_unknown": "Only unknown",
        "show_all": "All",
        "audio_coming_soon": "Audio coming soon",
        "audio_hint": "Drop an .mp3, .wav, or .m4a in 99-podcast/ and re-render.",
        "general_quiz": "General quiz",
        "module_quiz": "Module quiz",
        "select_quiz": "Select a quiz above.",
        "select_module": "Select a module",
        "back_to_modules": "Back to modules",
        "your_answer": "Your answer...",
        "your_progress": "Your progress",
        "answered": "answered",
        "no_flashcards": "No flashcards available.",
        "no_results": "No results.",
        "term_label": "Term",
        "question_label": "Question",
        "front": "Front",
        "back": "Back",
        "click_to_flip": "Click to flip",
        "known_marker": "marked",
        "mc_label": "Multiple choice",
        "short_label": "Short answer",
        "trace_label": "Trace the flow",
        "listen_label": "Listen",
        "menu": "Menu",
        "source_repo": "Source repo",
        "hero_eyebrow": "Course generated by Genie Learning",
        "hero_subtitle": "Browse the modules, take the quizzes, and review the flashcards at your own pace. Fully offline.",
        "start_tutorial": "Start the tutorial",
        "modules_subtitle": "Each module is a focused lesson. Pick one to start.",
        "glossary_subtitle": "Project-specific terms, with code references.",
        "quizzes_subtitle": "Quizzes grounded in the course content. Progress is saved locally.",
        "flashcards_subtitle": "Cards derived from the glossary and quizzes. Mark what you already know.",
        "podcast_subtitle": "Script ready for TTS. The player appears automatically when audio exists.",
        "footer_built": "Built by",
        "not_available": "Content not available.",
        "progress_hint": "Your progress is saved in this browser (localStorage).",
    },
    "es": {
        "overview": "Visión general", "tutorial": "Tutorial", "modules": "Módulos",
        "glossary": "Glosario", "quizzes": "Cuestionarios", "flashcards": "Tarjetas",
        "podcast": "Podcast", "next": "Siguiente", "previous": "Anterior",
        "reveal_answer": "Mostrar respuesta", "explanation": "Explicación", "reference_answer": "Respuesta de referencia",
        "correct": "Correcto", "incorrect": "Incorrecto",
        "knew_it": "Lo sabía", "didnt_know": "No lo sabía",
        "search_terms": "Buscar término...", "show_only_unknown": "Solo desconocidos", "show_all": "Todos",
        "audio_coming_soon": "Audio próximamente", "audio_hint": "Coloca un .mp3, .wav o .m4a en 99-podcast/ y vuelve a renderizar.",
        "general_quiz": "Cuestionario general", "module_quiz": "Cuestionario del módulo",
        "select_quiz": "Selecciona un cuestionario arriba.", "select_module": "Selecciona un módulo",
        "back_to_modules": "Volver a los módulos", "your_answer": "Tu respuesta...",
        "your_progress": "Tu progreso", "answered": "respondidas",
        "no_flashcards": "No hay tarjetas disponibles.", "no_results": "Sin resultados.",
        "term_label": "Término", "question_label": "Pregunta", "front": "Frente", "back": "Reverso",
        "click_to_flip": "Clic para voltear", "known_marker": "marcadas",
        "mc_label": "Opción múltiple", "short_label": "Respuesta corta", "trace_label": "Sigue el flujo",
        "listen_label": "Escuchar", "menu": "Menú", "source_repo": "Repositorio fuente",
        "hero_eyebrow": "Curso generado por Genie Learning",
        "hero_subtitle": "Explora los módulos, haz los cuestionarios y repasa las tarjetas a tu ritmo. Todo offline.",
        "start_tutorial": "Empezar el tutorial",
        "modules_subtitle": "Cada módulo es una lección enfocada. Elige uno para empezar.",
        "glossary_subtitle": "Términos específicos del proyecto, con referencias al código.",
        "quizzes_subtitle": "Cuestionarios anclados en el contenido del curso. Tu progreso se guarda localmente.",
        "flashcards_subtitle": "Tarjetas derivadas del glosario y los cuestionarios. Marca lo que ya sabes.",
        "podcast_subtitle": "Guion listo para TTS. El reproductor aparece automáticamente cuando hay audio.",
        "footer_built": "Construido por", "not_available": "Contenido no disponible.",
        "progress_hint": "Tu progreso se guarda en este navegador (localStorage).",
    },
    "fr": {
        "overview": "Vue d'ensemble", "tutorial": "Tutoriel", "modules": "Modules",
        "glossary": "Glossaire", "quizzes": "Quiz", "flashcards": "Cartes",
        "podcast": "Podcast", "next": "Suivant", "previous": "Précédent",
        "reveal_answer": "Révéler la réponse", "explanation": "Explication", "reference_answer": "Réponse de référence",
        "correct": "Correct", "incorrect": "Incorrect",
        "knew_it": "Je savais", "didnt_know": "Je ne savais pas",
        "search_terms": "Rechercher un terme...", "show_only_unknown": "Inconnus seulement", "show_all": "Tous",
        "audio_coming_soon": "Audio à venir", "audio_hint": "Déposez un .mp3, .wav ou .m4a dans 99-podcast/ et relancez le rendu.",
        "general_quiz": "Quiz général", "module_quiz": "Quiz du module",
        "select_quiz": "Sélectionnez un quiz ci-dessus.", "select_module": "Sélectionnez un module",
        "back_to_modules": "Retour aux modules", "your_answer": "Votre réponse...",
        "your_progress": "Votre progression", "answered": "répondues",
        "no_flashcards": "Aucune carte disponible.", "no_results": "Aucun résultat.",
        "term_label": "Terme", "question_label": "Question", "front": "Recto", "back": "Verso",
        "click_to_flip": "Cliquer pour retourner", "known_marker": "marquées",
        "mc_label": "Choix multiple", "short_label": "Réponse courte", "trace_label": "Tracez le flux",
        "listen_label": "Écouter", "menu": "Menu", "source_repo": "Dépôt source",
        "hero_eyebrow": "Cours généré par Genie Learning",
        "hero_subtitle": "Parcourez les modules, faites les quiz et révisez les cartes à votre rythme. Hors ligne.",
        "start_tutorial": "Commencer le tutoriel",
        "modules_subtitle": "Chaque module est une leçon ciblée. Choisissez-en un.",
        "glossary_subtitle": "Termes spécifiques au projet, avec références au code.",
        "quizzes_subtitle": "Quiz ancrés dans le contenu du cours. Votre progression est sauvegardée localement.",
        "flashcards_subtitle": "Cartes dérivées du glossaire et des quiz. Marquez ce que vous savez.",
        "podcast_subtitle": "Script prêt pour la TTS. Le lecteur apparaît automatiquement si l'audio existe.",
        "footer_built": "Construit par", "not_available": "Contenu indisponible.",
        "progress_hint": "Votre progression est sauvegardée dans ce navigateur (localStorage).",
    },
    "ja": {
        "overview": "概要", "tutorial": "チュートリアル", "modules": "モジュール",
        "glossary": "用語集", "quizzes": "クイズ", "flashcards": "フラッシュカード",
        "podcast": "ポッドキャスト", "next": "次へ", "previous": "前へ",
        "reveal_answer": "答えを表示", "explanation": "解説", "reference_answer": "参考解答",
        "correct": "正解", "incorrect": "不正解",
        "knew_it": "知ってた", "didnt_know": "知らなかった",
        "search_terms": "用語を検索...", "show_only_unknown": "未習得のみ", "show_all": "すべて",
        "audio_coming_soon": "音声準備中", "audio_hint": "99-podcast/ に .mp3 / .wav / .m4a を置いて再レンダーしてください。",
        "general_quiz": "総合クイズ", "module_quiz": "モジュールクイズ",
        "select_quiz": "クイズを選択してください。", "select_module": "モジュールを選択",
        "back_to_modules": "モジュール一覧へ戻る", "your_answer": "あなたの答え...",
        "your_progress": "進捗", "answered": "回答済み",
        "no_flashcards": "カードがありません。", "no_results": "結果なし。",
        "term_label": "用語", "question_label": "問題", "front": "表", "back": "裏",
        "click_to_flip": "クリックで反転", "known_marker": "習得",
        "mc_label": "選択式", "short_label": "短答", "trace_label": "流れをたどる",
        "listen_label": "聴く", "menu": "メニュー", "source_repo": "ソースリポジトリ",
        "hero_eyebrow": "Genie Learning が生成したコース",
        "hero_subtitle": "モジュールを読み、クイズで確認し、フラッシュカードで復習しましょう。完全オフラインで動作します。",
        "start_tutorial": "チュートリアルを開始",
        "modules_subtitle": "各モジュールは一つのテーマに集中したレッスンです。",
        "glossary_subtitle": "プロジェクト固有の用語とコードへの参照。",
        "quizzes_subtitle": "コース内容に基づくクイズ。進捗はローカルに保存されます。",
        "flashcards_subtitle": "用語集とクイズから生成されたカード。覚えたものをマークしましょう。",
        "podcast_subtitle": "TTS 用の台本。音声ファイルがあると自動でプレーヤーが表示されます。",
        "footer_built": "作成", "not_available": "利用できません。",
        "progress_hint": "進捗はこのブラウザ (localStorage) に保存されます。",
    },
}

# Question-kind detection patterns (multilingual). Order: longer first.
KIND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("mc", re.compile(r"^\*\*\s*(?:Múltipla escolha|Multiple choice|Opción múltiple|Choix multiple|選択式|多肢選択)\s*[:：]\s*\*\*\s*", re.IGNORECASE)),
    ("trace", re.compile(r"^\*\*\s*(?:Trace o fluxo|Trace the flow|Sigue el flujo|Tracez le flux|流れをたどる)\s*[:：]\s*\*\*\s*", re.IGNORECASE)),
    ("short", re.compile(r"^\*\*\s*(?:Resposta curta|Short answer|Respuesta corta|Réponse courte|短答)\s*[:：]\s*\*\*\s*", re.IGNORECASE)),
]

QUESTIONS_HEADING_RE = re.compile(r"^##\s+(?:Perguntas|Questions|Preguntas|質問)\s*$", re.MULTILINE | re.IGNORECASE)
ANSWERS_HEADING_RE = re.compile(r"^##\s+(?:Gabarito|Answer key|Respuestas|Réponses|解答)\s*$", re.MULTILINE | re.IGNORECASE)
NUMBERED_ITEM_RE = re.compile(r"^(\d+)\.\s+", re.MULTILINE)
MC_OPTION_RE = re.compile(r"^\s*-\s+([A-Z])\.\s+(.+)$")
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
GLOSSARY_LETTER_RE = re.compile(r"^##\s+(\S+?)\s*$", re.MULTILINE)
GLOSSARY_TERM_RE = re.compile(r"^###\s+\*\*(.+?)\*\*\s*$", re.MULTILINE)
# Two formats to handle for MC answer keys:
#   - Bolded:  `**B**` or `**B.**`, optionally preceded by `Correct answer:` etc. Use search().
#   - Plain:   `B.` at the very start of the answer text. Use match().
# Try bolded first (it's the canonical format); fall back to plain when no bold marker is present.
ANSWER_LETTER_RE_BOLD = re.compile(r"\*\*([A-Z])\.?\*\*", re.IGNORECASE)
ANSWER_LETTER_RE_PLAIN = re.compile(r"^([A-Z])\.\s+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Discovery + parsing
# ---------------------------------------------------------------------------

def read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").strip("﻿")


def parse_first_h1(raw: str | None) -> str | None:
    if not raw:
        return None
    m = H1_RE.search(raw)
    return m.group(1).strip() if m else None


def parse_glossary(raw: str | None) -> list[dict[str, Any]]:
    """Parse `20-glossary.md` into [{letter, terms: [{term, definition, anchor}]}]."""
    if not raw:
        return []
    # Strip the H1 header (and a possible blockquote intro) by jumping to the first ## .
    body_start = raw.find("\n##")
    body = raw[body_start:] if body_start >= 0 else raw

    # Split by ## headings.
    sections: list[tuple[str, str]] = []
    current_letter: str | None = None
    current_chunk: list[str] = []
    for line in body.splitlines():
        m = GLOSSARY_LETTER_RE.match(line)
        if m:
            if current_letter is not None:
                sections.append((current_letter, "\n".join(current_chunk)))
            current_letter = m.group(1).strip()
            current_chunk = []
        else:
            current_chunk.append(line)
    if current_letter is not None:
        sections.append((current_letter, "\n".join(current_chunk)))

    glossary: list[dict[str, Any]] = []
    for letter, chunk in sections:
        # Skip non-letter sections (defensive).
        if len(letter) > 3:
            continue
        terms: list[dict[str, Any]] = []
        # Split chunk by ### **Term** headings.
        positions: list[tuple[int, str]] = []
        for m in GLOSSARY_TERM_RE.finditer(chunk):
            positions.append((m.start(), m.group(1).strip()))
        positions.append((len(chunk), ""))
        for i in range(len(positions) - 1):
            start, term = positions[i]
            end, _ = positions[i + 1]
            term_block = chunk[start:end]
            # Drop the heading line itself from the definition.
            heading_end = term_block.find("\n")
            definition = term_block[heading_end + 1:].strip() if heading_end >= 0 else ""
            anchor = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
            terms.append({"term": term, "definition": definition, "anchor": anchor})
        if terms:
            glossary.append({"letter": letter, "terms": terms})
    return glossary


def _split_numbered(block: str) -> list[tuple[int, str]]:
    """Split a block on numbered items (e.g. '1.', '2.'). Returns [(num, text), ...]."""
    matches = list(NUMBERED_ITEM_RE.finditer(block))
    if not matches:
        return []
    items: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        items.append((num, block[start:end].strip()))
    return items


def _detect_kind(first_line: str) -> tuple[str, str]:
    """Return (kind, prompt-after-prefix). Falls back to ('short', original)."""
    for kind, pattern in KIND_PATTERNS:
        m = pattern.match(first_line)
        if m:
            return kind, first_line[m.end():].strip()
    return "short", first_line.strip()


def parse_quiz(raw: str | None, quiz_id: str) -> dict[str, Any] | None:
    if not raw:
        return None
    title = parse_first_h1(raw) or quiz_id

    q_match = QUESTIONS_HEADING_RE.search(raw)
    a_match = ANSWERS_HEADING_RE.search(raw)
    if not q_match:
        return {"id": quiz_id, "title": title, "questions": []}

    q_start = q_match.end()
    q_end = a_match.start() if a_match else len(raw)
    a_start = a_match.end() if a_match else len(raw)

    questions_block = raw[q_start:q_end]
    answers_block = raw[a_start:]

    answers_by_num: dict[int, str] = {n: text for n, text in _split_numbered(answers_block)}

    questions: list[dict[str, Any]] = []
    for num, text in _split_numbered(questions_block):
        # Separate the prompt (and optional MC options) from the rest.
        lines = text.splitlines()
        if not lines:
            continue
        first_line = lines[0].strip()
        kind, prompt_head = _detect_kind(first_line)

        # Collect prompt continuation lines (anything that is NOT a `- A.` option) as part of the prompt.
        # MC options are detected line by line.
        prompt_extra: list[str] = []
        options: list[dict[str, str]] = []
        for line in lines[1:]:
            opt_m = MC_OPTION_RE.match(line)
            if opt_m and kind == "mc":
                options.append({"key": opt_m.group(1), "text": opt_m.group(2).strip()})
            else:
                # In short/trace mode treat everything as prompt continuation.
                prompt_extra.append(line)

        prompt_full = (prompt_head + ("\n" + "\n".join(prompt_extra).strip() if any(s.strip() for s in prompt_extra) else "")).strip()

        question: dict[str, Any] = {"kind": kind, "prompt": prompt_full}

        ans_text = answers_by_num.get(num, "").strip()
        if kind == "mc":
            question["options"] = options
            am = ANSWER_LETTER_RE_BOLD.search(ans_text[:200])
            if am is None:
                am = ANSWER_LETTER_RE_PLAIN.match(ans_text)
            if am:
                question["answer_key"] = am.group(1).upper()
                # Drop everything up to and including the marker, plus any trailing punctuation/whitespace,
                # leaving only the explanation prose.
                question["explanation"] = ans_text[am.end():].lstrip(" \t.,;:")
            else:
                question["answer_key"] = None
                question["explanation"] = ans_text
        else:
            question["answer"] = ans_text

        questions.append(question)

    return {"id": quiz_id, "title": title, "questions": questions}


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "module"


def derive_flashcards(glossary: list[dict[str, Any]], quizzes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for letter in glossary:
        for term in letter["terms"]:
            # Take only the first paragraph of the definition for the card back — keeps it scannable.
            definition = term["definition"]
            first_para = definition.split("\n\n", 1)[0].strip()
            cards.append({
                "front": term["term"],
                "back": first_para or definition,
                "source": "glossary",
                "anchor": term["anchor"],
            })
    for quiz in quizzes:
        for q in quiz["questions"]:
            if q.get("kind") != "mc" or not q.get("options") or not q.get("answer_key"):
                continue
            answer_opt = next((o for o in q["options"] if o["key"] == q["answer_key"]), None)
            if not answer_opt:
                continue
            back = f"**{q['answer_key']}.** {answer_opt['text']}"
            if q.get("explanation"):
                back += f"\n\n{q['explanation']}"
            cards.append({
                "front": q["prompt"],
                "back": back,
                "source": "quiz",
                "quiz_id": quiz["id"],
            })
    return cards


def discover_modules(content_dir: Path, inventory_modules: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Scan `30-modules/` and merge metadata from the cartographer inventory if available."""
    modules_dir = content_dir / "30-modules"
    if not modules_dir.is_dir():
        return []
    files = sorted(modules_dir.glob("*.md"))
    inv_by_name: dict[str, dict[str, Any]] = {}
    if inventory_modules:
        inv_by_name = {m.get("name", ""): m for m in inventory_modules}

    modules: list[dict[str, Any]] = []
    for f in files:
        raw = read_text(f) or ""
        # File pattern is `NN-<slug>.md` — extract slug after the dash.
        stem = f.stem
        m = re.match(r"^(\d+)-(.+)$", stem)
        slug = m.group(2) if m else stem
        title = parse_first_h1(raw) or slug
        purpose = inv_by_name.get(slug, {}).get("purpose", "") if inv_by_name else ""
        modules.append({
            "slug": stem,
            "name": slug,
            "title_display": title,
            "purpose": purpose,
            "raw": raw,
        })
    return modules


def discover_quizzes(content_dir: Path) -> list[dict[str, Any]]:
    quizzes_dir = content_dir / "40-quizzes"
    if not quizzes_dir.is_dir():
        return []
    quizzes: list[dict[str, Any]] = []
    for f in sorted(quizzes_dir.glob("*.md")):
        raw = read_text(f)
        parsed = parse_quiz(raw, f.stem)
        if parsed:
            quizzes.append(parsed)
    return quizzes


def discover_audio(podcast_dir: Path, owner_name: str) -> str | None:
    if not podcast_dir.is_dir():
        return None
    for ext in ("mp3", "wav", "m4a", "ogg"):
        for f in sorted(podcast_dir.glob(f"*.{ext}")):
            # Return path relative to index.html (which lives at content/<owner>/).
            return f"99-podcast/{f.name}"
    return None


def load_podcast_metadata(podcast_dir: Path) -> dict[str, Any] | None:
    meta_path = podcast_dir / "metadata.json"
    if not meta_path.is_file():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Build + write
# ---------------------------------------------------------------------------

def build_course_data(content_dir: Path, owner_name: str) -> dict[str, Any]:
    podcast_dir = content_dir / "99-podcast"
    metadata = load_podcast_metadata(podcast_dir) or {}
    language = metadata.get("language") or "pt-BR"
    chrome = CHROME_STRINGS.get(language) or CHROME_STRINGS["en"]

    overview_raw = read_text(content_dir / "00-overview.md")
    if overview_raw is None:
        raise SystemExit(f"missing required file: {content_dir / '00-overview.md'}")
    tutorial_raw = read_text(content_dir / "10-tutorial.md")
    glossary_raw = read_text(content_dir / "20-glossary.md")
    podcast_script_raw = read_text(podcast_dir / "script.md")

    inventory_modules = metadata.get("modules") if isinstance(metadata.get("modules"), list) else None
    modules = discover_modules(content_dir, inventory_modules)
    quizzes = discover_quizzes(content_dir)
    glossary = parse_glossary(glossary_raw)
    flashcards = derive_flashcards(glossary, quizzes)
    audio_file = discover_audio(podcast_dir, owner_name)

    title_display = parse_first_h1(overview_raw) or owner_name

    repo_url = None
    if "/" in owner_name:
        # owner_name is `<owner>-<name>` — best-effort guess. We don't store the URL anywhere
        # canonical; leave as None and the UI hides the link.
        pass

    return {
        "schema_version": 1,
        "owner_name": owner_name,
        "language": language,
        "title_display": title_display,
        "repo_url": repo_url,
        "chrome": chrome,
        "overview": {"raw": overview_raw},
        "tutorial": {"raw": tutorial_raw} if tutorial_raw else None,
        "glossary": glossary,
        "modules": modules,
        "quizzes": quizzes,
        "flashcards": flashcards,
        "podcast": {
            "script_raw": podcast_script_raw,
            "audio_file": audio_file,
            "metadata": metadata,
        },
    }


def render(template_path: Path, course_data: dict[str, Any], output_path: Path) -> None:
    template = template_path.read_text(encoding="utf-8")
    placeholder = "/* GENIE_DATA */ null"
    if placeholder not in template:
        raise SystemExit(f"template missing placeholder `{placeholder}`")
    payload = json.dumps(course_data, ensure_ascii=False, separators=(",", ":"))
    # Defang `</script>` sequences inside content so the inline JSON does not break the script tag.
    payload = payload.replace("</script", "<\\/script")
    payload = payload.replace("</style", "<\\/style")
    output_path.write_text(template.replace(placeholder, payload, 1), encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render a Genie Learning course as a single HTML file.")
    parser.add_argument("owner_name", help="Course directory name under content/ (e.g. expressjs-express).")
    parser.add_argument("--project-root", default=None, help="Project root (default: parent of scripts/).")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root) if args.project_root else Path(__file__).resolve().parent.parent
    content_dir = project_root / "content" / args.owner_name
    template_path = project_root / "scripts" / "templates" / "course.html"
    output_path = content_dir / "index.html"

    if not content_dir.is_dir():
        print(f"error: course directory not found: {content_dir}", file=sys.stderr)
        print(f"hint: run /genie-learn first to generate content/{args.owner_name}/", file=sys.stderr)
        return 2
    if not template_path.is_file():
        print(f"error: template not found: {template_path}", file=sys.stderr)
        return 2

    course_data = build_course_data(content_dir, args.owner_name)
    render(template_path, course_data, output_path)

    size_kb = output_path.stat().st_size / 1024
    n_modules = len(course_data["modules"])
    n_quizzes = len(course_data["quizzes"])
    n_cards = len(course_data["flashcards"])
    n_terms = sum(len(letter["terms"]) for letter in course_data["glossary"])
    audio_status = "yes" if course_data["podcast"]["audio_file"] else "no"

    print(f"Wrote {output_path} ({size_kb:.1f} KB)")
    print(f"Modules: {n_modules} | Quizzes: {n_quizzes} | Glossary terms: {n_terms} | Flashcards: {n_cards} | Audio: {audio_status}")
    print(f"Open with: file:///{output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
