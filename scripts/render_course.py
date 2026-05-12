#!/usr/bin/env python3
"""Render a generated Genie Learning course as an interactive HTML bundle.

Reads `content/<owner>-<name>/` produced by /genie-learn and writes a 3-file
bundle next to the Markdown sources:

    content/<owner>-<name>/
    ├── index.html        — Vue 3 + Tailwind shell with the course payload inlined as base64
    ├── assets/style.css  — copied from scripts/templates/course_assets/style.css
    └── assets/app.js     — copied from scripts/templates/course_assets/app.js

Asset files are referenced from index.html with a cache-busting `?v=<hash>` query
string derived deterministically from the asset bytes (SHA1, first 10 hex chars).
Identical re-runs produce byte-identical output; any edit to an asset rotates the
hash and forces the browser to refetch.

The course payload stays inlined in `index.html` (not split into `data.json`) so
the page works under `file://` without CORS errors.

Usage:
    python scripts/render_course.py <owner-name>

No third-party dependencies — only the Python standard library.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ASSET_FILES: tuple[str, ...] = ("style.css", "app.js")
ASSET_VERSION_PLACEHOLDER = "__GENIE_ASSET_VERSION__"
DATA_PLACEHOLDER = "/* GENIE_DATA */"
VERSION = "1.1.0"
GRADER_KEY_PLACEHOLDER = "/* GENIE_GRADER_KEY */"

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
        "again": "Errei",
        "hard": "Difícil",
        "good": "Acertei",
        "easy": "Fácil",
        "last_review_today": "Última revisão: hoje",
        "last_review_yesterday": "Última revisão: ontem",
        "last_review_days_ago": "Última revisão: há {n} dias",
        "last_review_never": "Sem revisões ainda",
        "filter_due": "Para revisar",
        "filter_new": "Novos",
        "filter_learning": "Aprendendo",
        "filter_mature": "Maduros",
        "lbl_due": "pendentes",
        "lbl_new": "novos",
        "lbl_total": "total",
        "empty_due": "🎉 Você está em dia. Próxima revisão em ~{n} horas.",
        "see_new": "Ver novos",
        "search_terms": "Buscar termo...",
        "show_only_unknown": "Só não sabidos",
        "confidence_label": "Confiança",
        "confidence_hint_low": "(chute)",
        "confidence_hint_high": "(certeza)",
        "calibration_label": "Calibração:",
        "calibration_tooltip": "Quanto % você acerta em cada nível de confiança que declarou.",
        "why_label": "Em uma frase, por que essa é a resposta correta?",
        "why_placeholder": "Sua hipótese antes de ver o gabarito...",
        "why_reveal": "Revelar explicação",
        "why_skip": "Pular",
        "your_why": "Sua hipótese:",
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
        "self_explain_label": "Explicação própria",
        "self_explain_prompt": "Em 3 frases, explique este módulo para alguém que nunca usou o projeto.",
        "self_explain_hint": "Escrever ajuda a fixar — Chi 1989 mostra ganho mesmo sem feedback.",
        "self_explain_saved": "Salvo ✓",
        "save_explanation": "Salvar",
        "saved": "salvo",
        "notebook": "Caderno",
        "notebook_subtitle": "Revise o que escreveu para preparar para a próxima aula.",
        "notebook_empty": "Você ainda não escreveu nenhuma explicação. Comece em qualquer módulo.",
        "last_edited": "Última edição",
        "edit": "Editar",
        "pretest_label": "Pretest",
        "pretest_hint": "Tente responder antes de ler. Errar também ajuda a aprender.",
        "pretest_placeholder": "Sua hipótese...",
        "pretest_your_attempt": "Sua tentativa",
        "pretest_reveal": "Revelar lição",
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
        "again": "Again",
        "hard": "Hard",
        "good": "Good",
        "easy": "Easy",
        "last_review_today": "Last reviewed: today",
        "last_review_yesterday": "Last reviewed: yesterday",
        "last_review_days_ago": "Last reviewed: {n} days ago",
        "last_review_never": "No reviews yet",
        "filter_due": "Due",
        "filter_new": "New",
        "filter_learning": "Learning",
        "filter_mature": "Mature",
        "lbl_due": "due",
        "lbl_new": "new",
        "lbl_total": "total",
        "empty_due": "🎉 You're all caught up. Next review in ~{n} hours.",
        "see_new": "See new",
        "search_terms": "Search terms...",
        "show_only_unknown": "Only unknown",
        "confidence_label": "Confidence",
        "confidence_hint_low": "(guess)",
        "confidence_hint_high": "(certain)",
        "calibration_label": "Calibration:",
        "calibration_tooltip": "What % you got right at each confidence level you stated.",
        "why_label": "In one sentence, why is this the right answer?",
        "why_placeholder": "Your take before seeing the explanation...",
        "why_reveal": "Reveal explanation",
        "why_skip": "Skip",
        "your_why": "Your take:",
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
        "self_explain_label": "Self-explanation",
        "self_explain_prompt": "In 3 sentences, explain this module to someone who has never used the project.",
        "self_explain_hint": "Writing helps retention — Chi 1989 research shows gains even without feedback.",
        "self_explain_saved": "Saved ✓",
        "save_explanation": "Save",
        "saved": "saved",
        "notebook": "Notebook",
        "notebook_subtitle": "Review what you wrote to prepare for the next lesson.",
        "notebook_empty": "You haven't written any explanations yet. Start in any module.",
        "last_edited": "Last edited",
        "edit": "Edit",
        "pretest_label": "Pretest",
        "pretest_hint": "Try answering before reading. Wrong guesses still help learning.",
        "pretest_placeholder": "Your hypothesis...",
        "pretest_your_attempt": "Your attempt",
        "pretest_reveal": "Reveal lesson",
    },
    "es": {
        "overview": "Visión general", "tutorial": "Tutorial", "modules": "Módulos",
        "glossary": "Glosario", "quizzes": "Cuestionarios", "flashcards": "Tarjetas",
        "podcast": "Podcast", "next": "Siguiente", "previous": "Anterior",
        "reveal_answer": "Mostrar respuesta", "explanation": "Explicación", "reference_answer": "Respuesta de referencia",
        "correct": "Correcto", "incorrect": "Incorrecto",
        "knew_it": "Lo sabía", "didnt_know": "No lo sabía",
        "again": "Olvidé", "hard": "Difícil", "good": "Bien", "easy": "Fácil",
        "last_review_today": "Última revisión: hoy",
        "last_review_yesterday": "Última revisión: ayer",
        "last_review_days_ago": "Última revisión: hace {n} días",
        "last_review_never": "Sin revisiones aún",
        "filter_due": "Para revisar", "filter_new": "Nuevos", "filter_learning": "Aprendiendo", "filter_mature": "Maduros",
        "lbl_due": "pendientes", "lbl_new": "nuevos", "lbl_total": "total",
        "empty_due": "🎉 Estás al día. Próxima revisión en ~{n} horas.",
        "see_new": "Ver nuevos",
        "search_terms": "Buscar término...", "show_only_unknown": "Solo desconocidos",
        "confidence_label": "Confianza", "confidence_hint_low": "(adivinanza)", "confidence_hint_high": "(seguro)",
        "calibration_label": "Calibración:", "calibration_tooltip": "Qué % aciertas en cada nivel de confianza que declaraste.",
        "why_label": "En una frase, ¿por qué esta es la respuesta correcta?",
        "why_placeholder": "Tu hipótesis antes de ver la solución...",
        "why_reveal": "Mostrar explicación", "why_skip": "Saltar", "your_why": "Tu hipótesis:",
        "show_all": "Todos",
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
        "self_explain_label": "Autoexplicación",
        "self_explain_prompt": "En 3 frases, explica este módulo a alguien que nunca ha usado el proyecto.",
        "self_explain_hint": "Escribir ayuda a fijar — investigación de Chi 1989 muestra ganancias sin feedback.",
        "self_explain_saved": "Guardado ✓",
        "save_explanation": "Guardar",
        "saved": "guardado",
        "notebook": "Cuaderno",
        "notebook_subtitle": "Revisa lo que escribiste para prepararte para la próxima lección.",
        "notebook_empty": "Aún no has escrito explicaciones. Empieza en cualquier módulo.",
        "last_edited": "Última edición",
        "edit": "Editar",
        "pretest_label": "Pretest",
        "pretest_hint": "Intenta responder antes de leer. Equivocarse también ayuda.",
        "pretest_placeholder": "Tu hipótesis...",
        "pretest_your_attempt": "Tu intento",
        "pretest_reveal": "Mostrar lección",
    },
    "fr": {
        "overview": "Vue d'ensemble", "tutorial": "Tutoriel", "modules": "Modules",
        "glossary": "Glossaire", "quizzes": "Quiz", "flashcards": "Cartes",
        "podcast": "Podcast", "next": "Suivant", "previous": "Précédent",
        "reveal_answer": "Révéler la réponse", "explanation": "Explication", "reference_answer": "Réponse de référence",
        "correct": "Correct", "incorrect": "Incorrect",
        "knew_it": "Je savais", "didnt_know": "Je ne savais pas",
        "again": "Raté", "hard": "Difficile", "good": "Bien", "easy": "Facile",
        "last_review_today": "Dernière révision : aujourd'hui",
        "last_review_yesterday": "Dernière révision : hier",
        "last_review_days_ago": "Dernière révision : il y a {n} jours",
        "last_review_never": "Aucune révision encore",
        "filter_due": "À réviser", "filter_new": "Nouveaux", "filter_learning": "En cours", "filter_mature": "Maîtrisé",
        "lbl_due": "à réviser", "lbl_new": "nouveaux", "lbl_total": "total",
        "empty_due": "🎉 Tout est à jour. Prochaine révision dans ~{n} heures.",
        "see_new": "Voir nouveaux",
        "search_terms": "Rechercher un terme...", "show_only_unknown": "Inconnus seulement",
        "confidence_label": "Confiance", "confidence_hint_low": "(deviné)", "confidence_hint_high": "(certain)",
        "calibration_label": "Calibration :", "calibration_tooltip": "Le % de réussite à chaque niveau de confiance déclaré.",
        "why_label": "En une phrase, pourquoi est-ce la bonne réponse ?",
        "why_placeholder": "Votre hypothèse avant de voir l'explication...",
        "why_reveal": "Révéler l'explication", "why_skip": "Passer", "your_why": "Votre hypothèse :",
        "show_all": "Tous",
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
        "self_explain_label": "Explication personnelle",
        "self_explain_prompt": "En 3 phrases, expliquez ce module à quelqu'un qui n'a jamais utilisé le projet.",
        "self_explain_hint": "Écrire aide à fixer — la recherche de Chi 1989 montre des gains même sans feedback.",
        "self_explain_saved": "Enregistré ✓",
        "save_explanation": "Enregistrer",
        "saved": "enregistré",
        "notebook": "Carnet",
        "notebook_subtitle": "Révisez ce que vous avez écrit pour la prochaine leçon.",
        "notebook_empty": "Vous n'avez encore écrit aucune explication. Commencez par n'importe quel module.",
        "last_edited": "Dernière modification",
        "edit": "Modifier",
        "pretest_label": "Pretest",
        "pretest_hint": "Essayez de répondre avant de lire. Se tromper aide aussi à apprendre.",
        "pretest_placeholder": "Votre hypothèse...",
        "pretest_your_attempt": "Votre tentative",
        "pretest_reveal": "Révéler la leçon",
    },
    "ja": {
        "overview": "概要", "tutorial": "チュートリアル", "modules": "モジュール",
        "glossary": "用語集", "quizzes": "クイズ", "flashcards": "フラッシュカード",
        "podcast": "ポッドキャスト", "next": "次へ", "previous": "前へ",
        "reveal_answer": "答えを表示", "explanation": "解説", "reference_answer": "参考解答",
        "correct": "正解", "incorrect": "不正解",
        "knew_it": "知ってた", "didnt_know": "知らなかった",
        "again": "もう一度", "hard": "難しい", "good": "できた", "easy": "簡単",
        "last_review_today": "最終復習: 今日",
        "last_review_yesterday": "最終復習: 昨日",
        "last_review_days_ago": "最終復習: {n}日前",
        "last_review_never": "まだ復習なし",
        "filter_due": "復習対象", "filter_new": "新規", "filter_learning": "学習中", "filter_mature": "習得済み",
        "lbl_due": "復習", "lbl_new": "新規", "lbl_total": "合計",
        "empty_due": "🎉 すべて完了。次の復習は約{n}時間後。",
        "see_new": "新規を見る",
        "search_terms": "用語を検索...", "show_only_unknown": "未習得のみ",
        "confidence_label": "確信度", "confidence_hint_low": "（推測）", "confidence_hint_high": "（確信）",
        "calibration_label": "確信度の校正:", "calibration_tooltip": "宣言した確信度レベルごとの正答率。",
        "why_label": "なぜこれが正解なのか、一文で答えてください。",
        "why_placeholder": "解説を見る前のあなたの推測...",
        "why_reveal": "解説を表示", "why_skip": "スキップ", "your_why": "あなたの推測:",
        "show_all": "すべて",
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
        "self_explain_label": "自己説明",
        "self_explain_prompt": "3つの文で、このプロジェクトを使ったことのない人にこのモジュールを説明してください。",
        "self_explain_hint": "書くことが定着を助けます — Chi 1989 の研究はフィードバックなしでも効果があることを示しています。",
        "self_explain_saved": "保存しました ✓",
        "save_explanation": "保存",
        "saved": "保存済み",
        "notebook": "ノート",
        "notebook_subtitle": "次のレッスンに備えて、書いたものを見直しましょう。",
        "notebook_empty": "まだ説明を書いていません。任意のモジュールから始めてください。",
        "last_edited": "最終編集",
        "edit": "編集",
        "pretest_label": "事前テスト",
        "pretest_hint": "読む前に答えてみてください。間違えても学習に役立ちます。",
        "pretest_placeholder": "あなたの推測...",
        "pretest_your_attempt": "あなたの回答",
        "pretest_reveal": "レッスンを表示",
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
PRETEST_BLOCK_RE = re.compile(r'^##\s+Pretest\s*\n(.*?)\n---\s*\n', re.MULTILINE | re.DOTALL)
PRETEST_QUESTION_RE = re.compile(r'^\s*(\d+)\.\s+(.+?)(?=\n\s*\d+\.|\n---|\Z)', re.MULTILINE | re.DOTALL)
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


def strip_first_h1(raw: str | None) -> str | None:
    """Drop the leading `# ...` line (and a single trailing blank line) from `raw`.

    The renderer surfaces the H1 as `title_display` separately in the page header;
    leaving it inside the rendered prose duplicates the title visually.
    """
    if not raw:
        return raw
    m = re.match(r"\s*#\s+[^\n]*\n+", raw)
    return raw[m.end():] if m else raw


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


REPO_LINES_PER_FILE = 100


def build_grader_context(
    content_dir: Path,
    repos_dir: Path | None,
    quizzes: list[dict],
    modules: list[dict],
    overview_raw: str | None,
    tutorial_raw: str | None,
) -> dict[str, Any]:
    """Index context (course material + cloned repo snippets) for each short/trace question.

    Returns ``{question_id: {context, answer_key, module_ref, quiz_title}}``.
    """
    module_by_slug: dict[str, dict] = {m["name"]: m for m in modules}
    repo_cache: dict[str, str | None] = {}
    ref_pat = re.compile(r'`([a-zA-Z0-9_\-./]+(?:\.\w+)+)`')

    def _fetch_source(path_ref: str) -> str | None:
        if path_ref in repo_cache:
            return repo_cache[path_ref]
        if repos_dir is None:
            repo_cache[path_ref] = None
            return None
        name = Path(path_ref).name
        candidates = sorted(repos_dir.rglob(name)) or sorted(repos_dir.rglob(path_ref))
        for p in candidates:
            try:
                text = p.read_text("utf-8", errors="replace")
                lines = text.splitlines()
                head = lines[:REPO_LINES_PER_FILE]
                tail = lines[-30:] if len(lines) > REPO_LINES_PER_FILE + 30 else []
                content = "\n".join(head)
                if tail:
                    content += "\n\n# ... (trecho final do arquivo) ...\n" + "\n".join(tail)
                repo_cache[path_ref] = content
                return content
            except Exception:
                continue
        repo_cache[path_ref] = None
        return None

    def _extract_refs(md: str) -> list[str]:
        return list(set(ref_pat.findall(md)))

    ctx: dict[str, Any] = {}
    for quiz in quizzes:
        qid = quiz["id"]
        # Guess module slug from quiz id: "01-middleware-quiz" -> "middleware"
        m = re.match(r"^\d+-([a-z][a-z0-9-]*)", qid)
        slug = m.group(1) if m and m.group(1) in module_by_slug else None

        for qi, q in enumerate(quiz["questions"]):
            if q.get("kind") not in ("short", "trace"):
                continue
            parts: list[str] = []
            if slug and slug in module_by_slug:
                mod = module_by_slug[slug]
                parts.append(f"## Module: {mod['title_display']}")
                parts.append((mod.get("raw") or "")[:2000])
                refs = _extract_refs(mod.get("raw") or "")
                snippets = [_fetch_source(r) for r in refs if _fetch_source(r)]
                if snippets:
                    parts.append("## Repository source code (relevant excerpts)")
                    parts.extend(snippets)
            else:
                # General quiz — use overview + tutorial
                ov = strip_first_h1(overview_raw)
                if ov:
                    parts.append("## Overview")
                    parts.append(ov[:1500])
                tut = strip_first_h1(tutorial_raw)
                if tut:
                    parts.append("## Tutorial")
                    parts.append(tut[:1500])

            question_id = f"{qid}:{qi}"
            ctx[question_id] = {
                "context": "\n\n".join(parts),
                "answer_key": q.get("answer", ""),
                "module_ref": slug or "general",
                "quiz_title": quiz.get("title", qid),
            }
    return ctx


def extract_pretest(raw: str) -> tuple[dict | None, str]:
    """Returns ({questions: [...]} or None, raw_without_pretest_block)."""
    m = PRETEST_BLOCK_RE.search(raw)
    if not m:
        return None, raw
    inner = m.group(1)
    questions = [q.group(2).strip() for q in PRETEST_QUESTION_RE.finditer(inner)]
    if not questions or len(questions) > 2:
        return None, raw
    stripped = raw[:m.start()] + raw[m.end():]
    return {"questions": questions}, stripped


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
        pretest, raw_stripped = extract_pretest(strip_first_h1(raw))
        modules.append({
            "slug": stem,
            "name": slug,
            "title_display": title,
            "purpose": purpose,
            "raw": raw_stripped,
            "pretest": pretest,
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
    repo_url = metadata.get("repo_url") if isinstance(metadata.get("repo_url"), str) else None

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

    return {
        "schema_version": 1,
        "owner_name": owner_name,
        "language": language,
        "title_display": title_display,
        "repo_url": repo_url,
        "chrome": chrome,
        "overview": {"raw": strip_first_h1(overview_raw)},
        "tutorial": {"raw": strip_first_h1(tutorial_raw)} if tutorial_raw else None,
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


def copy_assets(template_dir: Path, output_dir: Path) -> str:
    """Copy `course_assets/*` next to `index.html` and return a cache-busting version string.

    The version is the first 10 hex chars of the SHA1 of the concatenated asset bytes —
    deterministic per content (idempotent re-runs do not invalidate the browser cache),
    sensitive to any edit (CSS or JS change rotates the hash).
    """
    src_dir = template_dir / "course_assets"
    dst_dir = output_dir / "assets"
    dst_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1()
    for name in ASSET_FILES:
        src_path = src_dir / name
        if not src_path.is_file():
            raise SystemExit(f"template asset missing: {src_path}")
        data = src_path.read_bytes()
        digest.update(data)
        (dst_dir / name).write_bytes(data)
    return digest.hexdigest()[:10]


def render(template_path: Path, course_data: dict[str, Any], output_path: Path, project_root: Path) -> None:
    template = template_path.read_text(encoding="utf-8")
    for placeholder in (DATA_PLACEHOLDER, ASSET_VERSION_PLACEHOLDER, GRADER_KEY_PLACEHOLDER):
        if placeholder not in template:
            hints = {
                DATA_PLACEHOLDER: "regenerate the template or add `/* GENIE_DATA */` to course.html",
                ASSET_VERSION_PLACEHOLDER: "add `__GENIE_ASSET_VERSION__` to course.html asset links",
                GRADER_KEY_PLACEHOLDER: "add `/* GENIE_GRADER_KEY */` to course.html (or use an older template without grading)",
            }
            hint = hints.get(placeholder, "check that the template is up to date")
            raise SystemExit(f"template missing placeholder `{placeholder}` — {hint}")
    asset_version = copy_assets(template_path.parent, output_path.parent)

    # Build grader context (RAG index + repo snippets)
    content_dir = output_path.parent
    owner_name = course_data["owner_name"]
    repos_dir = project_root / "repos" / owner_name
    if not repos_dir.is_dir():
        repos_dir = None
    grader_context = build_grader_context(
        content_dir=content_dir,
        repos_dir=repos_dir,
        quizzes=course_data["quizzes"],
        modules=course_data["modules"],
        overview_raw=course_data["overview"]["raw"] if course_data.get("overview") else None,
        tutorial_raw=course_data["tutorial"]["raw"] if course_data.get("tutorial") else None,
    )
    grader_path = output_path.parent / "assets" / "grader_context.json"
    grader_path.write_text(json.dumps(grader_context, ensure_ascii=False), encoding="utf-8")

    payload = json.dumps(course_data, ensure_ascii=False, separators=(",", ":"))
    b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    api_key = os.environ.get("GEMINI_API_KEY", "")
    rendered = template.replace(DATA_PLACEHOLDER, b64, 1)
    rendered = rendered.replace(ASSET_VERSION_PLACEHOLDER, asset_version)
    rendered = rendered.replace(GRADER_KEY_PLACEHOLDER, api_key)
    output_path.write_text(rendered, encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render a Genie Learning course as index.html + assets/ bundle.")
    parser.add_argument("owner_name", nargs="?", help="Course directory name under content/ (e.g. expressjs-express).")
    parser.add_argument("--project-root", default=None, help="Project root (default: parent of scripts/).")
    parser.add_argument("--output-dir", default=None, help="Directory to write index.html (and assets/) into (default: content/<owner_name>/).")
    parser.add_argument("--check", action="store_true", help="Validate the course without writing HTML or assets.")
    parser.add_argument("--list-courses", action="store_true", help="List available courses in content/.")
    parser.add_argument("--quiet", action="store_true", help="Suppress informational stdout (errors still go to stderr).")
    parser.add_argument("--version", action="store_true", help="Print version and exit.")
    args = parser.parse_args(argv)

    if args.version:
        print(VERSION)
        return 0

    project_root = Path(args.project_root) if args.project_root else Path(__file__).resolve().parent.parent
    content_base = project_root / "content"

    if args.list_courses:
        if not content_base.is_dir():
            print("No courses found — content/ directory does not exist.", file=sys.stderr)
            return 1
        courses = sorted(d.name for d in content_base.iterdir() if d.is_dir())
        if not courses:
            print("No courses found in content/.", file=sys.stderr)
            return 1
        print(f"Courses ({len(courses)}):")
        for name in courses:
            overview = content_base / name / "00-overview.md"
            title = ""
            if overview.is_file():
                m = H1_RE.search(overview.read_text(encoding="utf-8"))
                if m:
                    title = f"  — {m.group(1).strip()}"
            print(f"  {name}{title}")
        return 0

    content_dir = content_base / args.owner_name
    template_path = project_root / "scripts" / "templates" / "course.html"
    output_path = (Path(args.output_dir) if args.output_dir else content_dir) / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not content_dir.is_dir():
        print(f"error: course directory not found: {content_dir}", file=sys.stderr)
        print(f"hint: run /genie-learn first to generate content/{args.owner_name}/", file=sys.stderr)
        if not content_dir.parent.is_dir():
            print(f"note: the content/ directory itself does not exist at {content_dir.parent}", file=sys.stderr)
            print(f"      create it with: mkdir -p content/{args.owner_name}", file=sys.stderr)
        return 2
    if not template_path.is_file():
        print(f"error: template not found: {template_path}", file=sys.stderr)
        return 2

    course_data = build_course_data(content_dir, args.owner_name)

    if args.check:
        n_modules = len(course_data["modules"])
        n_quizzes = len(course_data["quizzes"])
        n_cards = len(course_data["flashcards"])
        n_terms = sum(len(letter["terms"]) for letter in course_data["glossary"])
        audio_status = "yes" if course_data["podcast"]["audio_file"] else "no"
        info = print if not args.quiet else (lambda *a, **kw: None)
        info(f"check: course '{args.owner_name}' is valid")
        info(f"Modules: {n_modules} | Quizzes: {n_quizzes} | Glossary terms: {n_terms} | Flashcards: {n_cards} | Audio: {audio_status}")

        warnings = 0
        for q in course_data["quizzes"]:
            if len(q["questions"]) == 0:
                info(f"  warning: quiz '{q['id']}' has 0 questions (missing or malformed ## Perguntas/## Questions heading?)")
                warnings += 1
        if warnings:
            info(f"  ({warnings} warning(s) — course will still render, missing quizzes will be skipped)")
        return 0

    render(template_path, course_data, output_path, project_root)

    if not args.quiet:
        size_kb = output_path.stat().st_size / 1024
        assets_dir = output_path.parent / "assets"
        assets_size_kb = sum(p.stat().st_size for p in assets_dir.iterdir() if p.is_file()) / 1024
        n_modules = len(course_data["modules"])
        n_quizzes = len(course_data["quizzes"])
        n_cards = len(course_data["flashcards"])
        n_terms = sum(len(letter["terms"]) for letter in course_data["glossary"])
        audio_status = "yes" if course_data["podcast"]["audio_file"] else "no"

        print(f"Wrote {output_path} ({size_kb:.1f} KB) + assets/ ({assets_size_kb:.1f} KB)")
        print(f"Modules: {n_modules} | Quizzes: {n_quizzes} | Glossary terms: {n_terms} | Flashcards: {n_cards} | Audio: {audio_status}")
        print(f"Open with: file:///{output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
