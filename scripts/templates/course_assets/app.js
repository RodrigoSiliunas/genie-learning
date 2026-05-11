const STORAGE_KEY = 'genie:' + (window.__COURSE_DATA.owner_name || 'course');

function loadState() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
}
function saveState(s) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
}

/* SM-2 lite helpers */
const DAY_MS = 86_400_000;
function defaultSched() { return { ef: 2.5, interval: 0, reps: 0, due: Date.now(), lastReview: null, lapses: 0 }; }
function previewInterval(grade, s) {
  if (grade === 'again') return 10 * 60 * 1000;
  if (grade === 'hard')  return s.reps < 1 ? DAY_MS : Math.round(s.interval * 1.2);
  if (grade === 'easy')  return s.reps < 1 ? 4 * DAY_MS : Math.round(s.interval * s.ef * 1.3);
  /* good */
  if (s.reps < 1) return DAY_MS;
  if (s.reps < 2) return 3 * DAY_MS;
  return Math.round(s.interval * s.ef);
}
function rateCard(grade, s) {
  s = { ...s };
  // Mirror previewInterval: branches read PRE-increment s.reps so first review hits the seed interval.
  if (grade === 'again') {
    s.reps = 0;
    s.interval = 10 * 60 * 1000;
    s.ef = Math.max(1.3, s.ef - 0.20);
    s.lapses += 1;
  } else if (grade === 'hard') {
    s.interval = s.reps < 1 ? DAY_MS : Math.round(s.interval * 1.2);
    s.ef = Math.max(1.3, s.ef - 0.15);
    s.reps += 1;
  } else if (grade === 'easy') {
    s.interval = s.reps < 1 ? 4 * DAY_MS : Math.round(s.interval * s.ef * 1.3);
    s.ef = Math.min(2.7, s.ef + 0.15);
    s.reps += 1;
  } else { // good
    s.interval = s.reps < 1 ? DAY_MS : (s.reps < 2 ? 3 * DAY_MS : Math.round(s.interval * s.ef));
    s.reps += 1;
  }
  s.due = Date.now() + s.interval;
  s.lastReview = Date.now();
  return s;
}

const { createApp, ref, computed, watch, onMounted } = Vue;

const app = createApp({
  setup() {
    const data = ref(window.__COURSE_DATA);
    const persisted = loadState();

    const view = ref(persisted.view || 'overview');
    const drawerOpen = ref(false);
    const tweaksOpen = ref(false);

    const theme = ref(persisted.theme || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
    const accent = ref(persisted.accent || 'moss');

    const activeModule = ref(null);
    const glossaryQuery = ref('');

    const activeQuizId = ref(persisted.activeQuizId || (data.value.quizzes[0] && data.value.quizzes[0].id) || null);
    const mcAnswers = ref(persisted.mcAnswers || {});         // { quizId: { qi: 'B' } }
    const shortAnswers = ref(persisted.shortAnswers || {});   // { 'quizId:qi': text }
    const shortRevealed = ref(persisted.shortRevealed || {}); // { 'quizId:qi': true }

    const flashIndex = ref(persisted.flashIndex || 0);
    const flashFilter = ref(persisted.flashFilter || 'all');
    const flashSourceFilter = ref(persisted.flashSourceFilter || 'all');
    const flipped = ref(false);
    /* schedule state — migrate from legacy knownMap if needed */
    let schedule = persisted.schedule || {};
    if (!persisted.schedule && persisted.knownMap) {
      const now = Date.now();
      for (const h in persisted.knownMap) {
        schedule[h] = { ef: 2.5, interval: 3*DAY_MS, reps: 2, due: now + 3*DAY_MS, lastReview: null, lapses: 0 };
      }
    }
    const scheduleRef = ref(schedule);
    const knownMap = computed(() => {
      const m = {};
      for (const h in scheduleRef.value) { if (scheduleRef.value[h].reps >= 2) m[h] = true; }
      return m;
    });

    /* ---------- Grading (AI short-answer evaluation) ---------- */
    const grading = ref(persisted.grading || {});             // { 'quizId:qi': HTML string }
    const gradingLoading = ref({});
    const graderContext = ref(null);

    /* ---------- i18n ---------- */
    const t = (key) => (data.value.chrome && data.value.chrome[key]) || key;

    /* ---------- Markdown rendering ---------- */
    const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    if (window.marked) {
      window.marked.use({
        breaks: false, gfm: true,
        renderer: {
          link({href, title, text}) {
            return `<a href="${href}" ${title ? `title="${title}"` : ''} target="_blank" rel="noopener">${text}</a>`;
          },
          code(text, lang) {
            const language = (lang || '').trim().toLowerCase() || 'plaintext';
            // Authors sometimes wrap a real markdown table or list inside ```markdown ... ```
            // intending it to render as content, not as syntax-highlighted source. Unwrap it.
            // (Anyone who wants to actually display markdown source can use ```text or no fence.)
            if (language === 'markdown' || language === 'md') {
              return window.marked.parse(text);
            }
            const grammar = window.Prism && window.Prism.languages && window.Prism.languages[language];
            const body = grammar
              ? window.Prism.highlight(text, grammar, language)
              : escapeHtml(text);
            const cls = `language-${language}`;
            return `<pre class="${cls}" data-language="${language}"><code class="${cls}">${body}</code></pre>`;
          },
          table(header, body) {
            const bodyHtml = body ? `<tbody>${body}</tbody>` : '';
            return `<div class="table-wrap"><table><thead>${header}</thead>${bodyHtml}</table></div>`;
          }
        }
      });
    }
    const renderMd = (md) => md ? window.marked.parse(md) : '';
    const renderMdInline = (md) => {
      if (!md) return '';
      const html = window.marked.parseInline(md);
      return html;
    };

    /* ---------- Computed ---------- */
    const titleDisplay = computed(() => data.value.title_display || '');

    const shortRepo = computed(() => {
      if (!data.value.repo_url) return '';
      try {
        const u = new URL(data.value.repo_url);
        return u.pathname.replace(/^\//, '');
      } catch { return data.value.repo_url; }
    });

    const readTime = (md) => {
      if (!md) return '';
      const words = md.trim().split(/\s+/).length;
      const min = Math.max(1, Math.round(words / 200));
      return `${min} min`;
    };

    const glossaryCount = computed(() =>
      data.value.glossary.reduce((acc, g) => acc + g.terms.length, 0)
    );

    const navItems = computed(() => [
      { id: 'overview',   label: t('overview') },
      { id: 'tutorial',   label: t('tutorial') },
      { id: 'modules',    label: t('modules'),    count: data.value.modules.length },
      { id: 'glossary',   label: t('glossary'),   count: glossaryCount.value },
      { id: 'quizzes',    label: t('quizzes'),    count: data.value.quizzes.length },
      { id: 'flashcards', label: t('flashcards'), count: data.value.flashcards.length },
      { id: 'podcast',    label: t('podcast') },
    ]);

    const filteredGlossary = computed(() => {
      const q = glossaryQuery.value.trim().toLowerCase();
      if (!q) return data.value.glossary;
      return data.value.glossary.map(group => ({
        letter: group.letter,
        terms: group.terms.filter(term =>
          term.term.toLowerCase().includes(q) ||
          term.definition.toLowerCase().includes(q)
        )
      })).filter(group => group.terms.length > 0);
    });

    const activeModuleIndex = computed(() =>
      activeModule.value ? data.value.modules.findIndex(m => m.slug === activeModule.value.slug) : -1
    );
    const openModule = (m) => { activeModule.value = m; window.scrollTo({top: 0, behavior: 'smooth'}); };

    const activeQuiz = computed(() => data.value.quizzes.find(q => q.id === activeQuizId.value));
    const shortKey = (qid, qi) => `${qid}:${qi}`;
    const quizAnswered = (qid, qi) => !!(mcAnswers.value[qid] && mcAnswers.value[qid][qi]);

    const scrollToQuestion = (qi) => {
      // Scroll the answered question card into view after a brief delay for Vue re-render
      setTimeout(() => {
        const cards = document.querySelectorAll('.view-enter .card');
        const target = cards[qi];
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 50);
    };

    const quizProgress = (q) => {
      let answered = 0;
      let trace = 0;
      q.questions.forEach((qq, qi) => {
        if (qq.kind === 'mc') {
          if (mcAnswers.value[q.id] && mcAnswers.value[q.id][qi]) answered++;
        } else if (qq.kind === 'short') {
          if (shortRevealed.value[shortKey(q.id, qi)]) answered++;
        } else {
          answered++; // trace always "answered"
          trace++;
        }
      });
      return { answered, trace, total: q.questions.length };
    };

    const answerMc = (qid, qi, key) => {
      if (!mcAnswers.value[qid]) mcAnswers.value[qid] = {};
      if (mcAnswers.value[qid][qi]) return;
      mcAnswers.value[qid] = { ...mcAnswers.value[qid], [qi]: key };
      scrollToQuestion(qi);
    };

    const revealShort = (qid, qi) => {
      shortRevealed.value = { ...shortRevealed.value, [shortKey(qid, qi)]: true };
      scrollToQuestion(qi);
    };

    const optionClass = (qid, qi, q, opt) => {
      const userAns = mcAnswers.value[qid] && mcAnswers.value[qid][qi];
      if (!userAns) return '';
      if (opt.key === q.answer_key) return 'is-correct';
      if (opt.key === userAns) return 'is-wrong';
      return 'opacity-60';
    };

    /* ---------- Module card tints ---------- */
    const moduleTintStyle = (idx) => {
      const slot = idx % 6;
      return {
        background: `var(--tint-${slot})`,
        '--tint-ink': `var(--tint-ink-${slot})`,
        borderColor: 'transparent'
      };
    };

    /* ---------- Flashcards ---------- */
    const flashHash = (f) => f.source + ':' + (f.anchor || f.front);
    const flashOrder = ref(persisted.flashOrder || null); // null = original order, array = shuffled indices

    const visibleFlashcards = computed(() => {
      let cards = data.value.flashcards;
      // Known/unknown filter
      if (flashFilter.value === 'unknown') {
        cards = cards.filter(f => !knownMap.value[flashHash(f)]);
      }
      // Source filter
      if (flashSourceFilter.value !== 'all') {
        cards = cards.filter(f => f.source === flashSourceFilter.value);
      }
      // Apply shuffled order if active and consistent with current filter length
      if (flashOrder.value && flashOrder.value.length === cards.length) {
        cards = flashOrder.value.map(i => cards[i]);
      }
      return cards;
    });
    const currentFlash = computed(() => visibleFlashcards.value[Math.min(flashIndex.value, visibleFlashcards.value.length - 1)] || data.value.flashcards[0]);
    const knownCount = computed(() => data.value.flashcards.filter(f => knownMap.value[flashHash(f)]).length);
    const scheduleFor = (f) => scheduleRef.value[flashHash(f)] || defaultSched();
    const lastReviewLabel = computed(() => {
      const f = currentFlash.value;
      if (!f) return '';
      const s = scheduleFor(f);
      if (!s.lastReview) return t('last_review_never');
      const diff = Date.now() - s.lastReview;
      if (diff < DAY_MS) return t('last_review_today');
      const days = Math.floor(diff / DAY_MS);
      if (days === 1) return t('last_review_yesterday');
      return t('last_review_days_ago').replace('{n}', days);
    });

    const prevFlash = () => {
      if (!visibleFlashcards.value.length) return;
      flipped.value = false;
      flashIndex.value = (flashIndex.value - 1 + visibleFlashcards.value.length) % visibleFlashcards.value.length;
    };
    const nextFlash = () => {
      if (!visibleFlashcards.value.length) return;
      flipped.value = false;
      flashIndex.value = (flashIndex.value + 1) % visibleFlashcards.value.length;
    };
    const rateFlash = (grade) => {
      const f = currentFlash.value;
      if (!f) return;
      const h = flashHash(f);
      const s = scheduleFor(f);
      scheduleRef.value = { ...scheduleRef.value, [h]: rateCard(grade, s) };
      nextFlash();
    };

    const shuffleFlashcards = () => {
      const indices = Array.from({ length: data.value.flashcards.length }, (_, i) => i);
      // Fisher-Yates shuffle
      for (let i = indices.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [indices[i], indices[j]] = [indices[j], indices[i]];
      }
      flashOrder.value = indices;
      flashIndex.value = 0;
      flipped.value = false;
    };

    const resetOrder = () => {
      flashOrder.value = null;
      flashIndex.value = 0;
      flipped.value = false;
    };

    /* ---------- Short-answer AI grading ---------- */
    const gradeShort = async (qid, qi) => {
      const key = `${qid}:${qi}`;
      if (gradingLoading.value[key] || grading.value[key]) return;

      const question = activeQuiz.value?.questions[qi];
      const answer = shortAnswers.value[key];
      if (!question || !answer?.trim()) return;

      const ctx = graderContext.value?.[key];
      if (!ctx) {
        grading.value = { ...grading.value, [key]: '<div class="flex items-start gap-3"><span class="text-[1.4rem] leading-none mt-0.5">⚠️</span><div><strong>Contexto não disponível</strong><p class="mt-1.5 text-[14px] leading-relaxed" style="color:var(--ink-soft)">O arquivo <code>assets/grader_context.json</code> não foi encontrado. Re-renderize o curso para gerá-lo.</p></div></div>' };
        return;
      }

      gradingLoading.value = { ...gradingLoading.value, [key]: true };

      const prompt = `Você é um assistente de correção de provas. Responda APENAS com um JSON neste formato, sem markdown, sem texto extra:
{"status": "CORRETO" | "PARCIALMENTE_CORRETO" | "INCORRETO", "justificativa": "breve explicação de 1-2 frases"}

CONTEXTO DO CURSO (use ESTE contexto como fonte primária):
${ctx.context}

REGRAS:
1. Avalie a resposta do aluno com base APENAS no contexto fornecido acima.
2. Se o contexto for insuficiente para avaliar, use seu conhecimento técnico geral sobre a tecnologia — mas indique claramente com "(baseado em conhecimento geral)" na justificativa.
3. CORRETO = resposta captura o conceito central
4. PARCIALMENTE_CORRETO = resposta toca no assunto mas falta precisão ou detalhe
5. INCORRETO = resposta errada, contradiz o contexto, ou não responde a pergunta

Pergunta: ${question.prompt}
Resposta de referência: ${ctx.answer_key}

Resposta do aluno: ${answer}

Avalie:`;

      const model = 'gemma-3-27b-it';
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${window.__GRADER_KEY}`;

      try {
        let resp = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { temperature: 0.15, maxOutputTokens: 300 }
          })
        });

        if (!resp.ok && model === 'gemma-3-27b-it') {
          // Fallback to gemini-2.0-flash
          const fbUrl = url.replace('gemma-3-27b-it', 'gemini-2.0-flash');
          resp = await fetch(fbUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contents: [{ parts: [{ text: prompt }] }],
              generationConfig: { temperature: 0.15, maxOutputTokens: 300 }
            })
          });
        }

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        const data = await resp.json();
        const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';

        let result;
        try {
          const cleaned = text.replace(/```(?:json)?\n?/g, '').trim();
          result = JSON.parse(cleaned);
        } catch {
          result = { status: 'PARCIALMENTE_CORRETO', justificativa: text.slice(0, 200) };
        }

        const status = result.status || 'PARCIALMENTE_CORRETO';
        const icon = status === 'CORRETO' ? '✅'
                   : status === 'PARCIALMENTE_CORRETO' ? '⚠️' : '❌';

        grading.value = {
          ...grading.value,
          [key]: `<div class="flex items-start gap-3">
            <span class="text-[1.4rem] leading-none mt-0.5">${icon}</span>
            <div>
              <strong style="font-size:1rem">${status.replace(/_/g, ' ')}</strong>
              <p class="mt-1.5 text-[14px] leading-relaxed" style="color:var(--ink-soft)">${result.justificativa || ''}</p>
            </div>
          </div>`
        };
      } catch (err) {
        grading.value = {
          ...grading.value,
          [key]: `<div class="flex items-start gap-3">
            <span class="text-[1.4rem] leading-none mt-0.5">⚠️</span>
            <div>
              <strong>Erro na correção</strong>
              <p class="mt-1.5 text-[14px] leading-relaxed" style="color:var(--ink-soft)">${err.message || 'Falha ao conectar com a API Gemini.'}</p>
              <p class="mt-1 text-[12px]" style="color:var(--muted)">Verifique se GEMINI_API_KEY está configurada e re-renderize o curso.</p>
            </div>
          </div>`
        };
      } finally {
        gradingLoading.value = { ...gradingLoading.value, [key]: false };
      }
    };

    const gradingStyle = (key) => {
      const html = grading.value[key] || '';
      if (html.includes('CORRETO')) return { background: 'var(--correct-bg)', borderColor: 'var(--correct)' };
      if (html.includes('INCORRETO')) return { background: 'var(--wrong-bg)', borderColor: 'var(--wrong)' };
      return { background: '#fef9e7', borderColor: '#f5d75e' }; // amber
    };

    /* ---------- Nav ---------- */
    const goto = (id) => {
      if (view.value !== id) {
        view.value = id;
        activeModule.value = null;
        window.scrollTo({top: 0, behavior: 'smooth'});
      }
    };

    /* ---------- Export/import progress ---------- */
    const exportProgress = () => {
      const state = loadState();
      const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${STORAGE_KEY}-progress.json`;
      a.click();
      URL.revokeObjectURL(url);
    };

    const importProgress = () => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.json';
      input.onchange = () => {
        const file = input.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const state = JSON.parse(e.target.result);
            saveState(state);
            // Reload current session state from the imported data
            const reloaded = loadState();
            if (reloaded.view) view.value = reloaded.view;
            if (reloaded.theme) theme.value = reloaded.theme;
            if (reloaded.accent) accent.value = reloaded.accent;
            if (reloaded.activeQuizId) activeQuizId.value = reloaded.activeQuizId;
            if (reloaded.mcAnswers) mcAnswers.value = reloaded.mcAnswers;
            if (reloaded.shortAnswers) shortAnswers.value = reloaded.shortAnswers;
            if (reloaded.shortRevealed) shortRevealed.value = reloaded.shortRevealed;
            if (reloaded.flashIndex != null) flashIndex.value = reloaded.flashIndex;
            if (reloaded.flashFilter) flashFilter.value = reloaded.flashFilter;
            if (reloaded.flashSourceFilter) flashSourceFilter.value = reloaded.flashSourceFilter;
            if (reloaded.flashOrder !== undefined) flashOrder.value = reloaded.flashOrder;
            // Prefer the new schedule format; migrate from legacy knownMap if only that exists.
            if (reloaded.schedule) {
              scheduleRef.value = reloaded.schedule;
            } else if (reloaded.knownMap) {
              const migrated = {};
              const now = Date.now();
              for (const h in reloaded.knownMap) {
                migrated[h] = { ef: 2.5, interval: 3*DAY_MS, reps: 2, due: now + 3*DAY_MS, lastReview: null, lapses: 0 };
              }
              scheduleRef.value = migrated;
            }
            if (reloaded.grading) grading.value = reloaded.grading;
            // Flash a brief confirmation
            const banner = document.createElement('div');
            banner.textContent = '✓ Progresso importado com sucesso';
            banner.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--accent);color:var(--accent-ink);padding:12px 24px;border-radius:12px;font-size:14px;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.15);transition:opacity 0.3s';
            document.body.appendChild(banner);
            setTimeout(() => { banner.style.opacity = '0'; setTimeout(() => banner.remove(), 300); }, 2000);
          } catch {
            alert('Falha ao importar progresso: arquivo JSON inválido.');
          }
        };
        reader.readAsText(file);
      };
      input.click();
    };

    /* ---------- Apply tweaks to <html> ---------- */
    const applyTweaks = () => {
      const root = document.documentElement;
      root.setAttribute('data-theme', theme.value);
      root.setAttribute('data-accent', accent.value);
    };

    /* ---------- Persistence ---------- */
    const persist = () => {
      saveState({
        view: view.value,
        theme: theme.value,
        accent: accent.value,
        activeQuizId: activeQuizId.value,
        mcAnswers: mcAnswers.value,
        shortAnswers: shortAnswers.value,
        shortRevealed: shortRevealed.value,
        flashIndex: flashIndex.value,
        flashFilter: flashFilter.value,
        flashSourceFilter: flashSourceFilter.value,
        flashOrder: flashOrder.value,
        schedule: scheduleRef.value,
        knownMap: knownMap.value,
        grading: grading.value
      });
    };

    watch([view, theme, accent, activeQuizId, flashIndex, flashFilter,
           mcAnswers, shortAnswers, shortRevealed, scheduleRef, grading], () => { persist(); }, { deep: true });
    watch([theme, accent], applyTweaks, { immediate: true });
    watch(flashFilter, () => { flashIndex.value = 0; flipped.value = false; });
    watch(flashSourceFilter, () => { flashIndex.value = 0; flipped.value = false; });
    watch(view, () => { flipped.value = false; });
    watch(activeQuizId, () => {
      // Scroll to the quiz section on quiz switch
      setTimeout(() => {
        const el = document.querySelector('.view-enter');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    });

    onMounted(() => {
      applyTweaks();
      // Load grader context (RAG index for short-answer AI evaluation)
      fetch('assets/grader_context.json')
        .then(r => r.json())
        .then(ctx => { graderContext.value = ctx; })
        .catch(() => {});
      // keyboard: left/right for flashcards & modules
      window.addEventListener('keydown', (e) => {
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
        if (view.value === 'flashcards') {
          if (e.key === 'ArrowRight') nextFlash();
          if (e.key === 'ArrowLeft') prevFlash();
          if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); flipped.value = !flipped.value; }
          if (e.key === 'j') prevFlash();
          if (e.key === 'k') nextFlash();
          if (e.key === '1') rateFlash('again');
          if (e.key === '2') rateFlash('hard');
          if (e.key === '3') rateFlash('good');
          if (e.key === '4') rateFlash('easy');
        }
        // Single-key section navigation (not pressed during input editing)
        if (!e.metaKey && !e.ctrlKey && !e.altKey) {
          if (e.key === 'o') goto('overview');
          else if (e.key === 't') goto('tutorial');
          else if (e.key === 'm') goto('modules');
          else if (e.key === 'g') goto('glossary');
          else if (e.key === 'q') goto('quizzes');
          else if (e.key === 'f') goto('flashcards');
          else if (e.key === 'p') goto('podcast');
        }
      });
    });

    return {
      data, view, drawerOpen, tweaksOpen,
      theme, accent,
      activeModule, activeModuleIndex, openModule,
      glossaryQuery, filteredGlossary, glossaryCount,
      activeQuizId, activeQuiz, mcAnswers, shortAnswers, shortRevealed,
      shortKey, quizAnswered, quizProgress, answerMc, revealShort, optionClass,
      grading, gradingLoading, gradeShort, gradingStyle,
      flashIndex, flashFilter, flashSourceFilter, flipped, knownMap, knownCount,
      scheduleRef, scheduleFor, lastReviewLabel, previewInterval, DAY_MS,
      visibleFlashcards, currentFlash, prevFlash, nextFlash, rateFlash,
      shuffleFlashcards, resetOrder,
      navItems, goto, t, renderMd, renderMdInline,
      titleDisplay, shortRepo, readTime,
      moduleTintStyle,
      exportProgress, importProgress
    };
  }
});

app.mount('#app');
