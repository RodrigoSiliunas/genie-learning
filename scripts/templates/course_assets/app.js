const STORAGE_KEY = 'genie:' + (window.__COURSE_DATA.owner_name || 'course');

function loadState() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
}
function saveState(s) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
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
    const density = ref(persisted.density || 'comfortable');

    const activeModule = ref(null);
    const glossaryQuery = ref('');

    const activeQuizId = ref(persisted.activeQuizId || (data.value.quizzes[0] && data.value.quizzes[0].id) || null);
    const mcAnswers = ref(persisted.mcAnswers || {});         // { quizId: { qi: 'B' } }
    const shortAnswers = ref(persisted.shortAnswers || {});   // { 'quizId:qi': text }
    const shortRevealed = ref(persisted.shortRevealed || {}); // { 'quizId:qi': true }

    const flashIndex = ref(persisted.flashIndex || 0);
    const flashFilter = ref(persisted.flashFilter || 'all');
    const flipped = ref(false);
    const knownMap = ref(persisted.knownMap || {});           // { 'front-hash': true }

    /* ---------- i18n ---------- */
    const t = (key) => (data.value.chrome && data.value.chrome[key]) || key;

    /* ---------- Markdown rendering ---------- */
    if (window.marked) {
      window.marked.use({
        breaks: false, gfm: true,
        renderer: {
          link({href, title, text}) {
            return `<a href="${href}" ${title ? `title="${title}"` : ''} target="_blank" rel="noopener">${text}</a>`;
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
    const titleDisplay = computed(() => {
      const t = data.value.title_display || '';
      // Add subtle italic to first word for editorial feel
      const parts = t.split(' ');
      if (parts.length < 2) return t;
      return parts.join(' ');
    });

    const shortRepo = computed(() => {
      if (!data.value.repo_url) return '';
      try {
        const u = new URL(data.value.repo_url);
        return u.pathname.replace(/^\//, '');
      } catch { return data.value.repo_url; }
    });

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

    const quizProgress = (q) => {
      let answered = 0;
      q.questions.forEach((qq, qi) => {
        if (qq.kind === 'mc') {
          if (mcAnswers.value[q.id] && mcAnswers.value[q.id][qi]) answered++;
        } else if (qq.kind === 'short') {
          if (shortRevealed.value[shortKey(q.id, qi)]) answered++;
        } else {
          answered++; // trace always "answered"
        }
      });
      return { answered };
    };

    const answerMc = (qid, qi, key) => {
      if (!mcAnswers.value[qid]) mcAnswers.value[qid] = {};
      if (mcAnswers.value[qid][qi]) return;
      mcAnswers.value[qid] = { ...mcAnswers.value[qid], [qi]: key };
    };

    const revealShort = (qid, qi) => {
      shortRevealed.value = { ...shortRevealed.value, [shortKey(qid, qi)]: true };
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
    const visibleFlashcards = computed(() => {
      if (flashFilter.value === 'unknown') {
        return data.value.flashcards.filter(f => !knownMap.value[flashHash(f)]);
      }
      return data.value.flashcards;
    });
    const currentFlash = computed(() => visibleFlashcards.value[Math.min(flashIndex.value, visibleFlashcards.value.length - 1)] || data.value.flashcards[0]);
    const knownCount = computed(() => data.value.flashcards.filter(f => knownMap.value[flashHash(f)]).length);

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
    const markFlash = (known) => {
      const f = currentFlash.value;
      if (!f) return;
      const h = flashHash(f);
      const m = { ...knownMap.value };
      if (known) m[h] = true; else delete m[h];
      knownMap.value = m;
      nextFlash();
    };

    /* ---------- Nav ---------- */
    const goto = (id) => {
      if (view.value !== id) {
        view.value = id;
        activeModule.value = null;
        window.scrollTo({top: 0, behavior: 'smooth'});
      }
    };

    /* ---------- Apply tweaks to <html> ---------- */
    const applyTweaks = () => {
      const root = document.documentElement;
      root.setAttribute('data-theme', theme.value);
      root.setAttribute('data-accent', accent.value);
      root.setAttribute('data-density', density.value);
    };

    /* ---------- Persistence ---------- */
    const persist = () => {
      saveState({
        view: view.value,
        theme: theme.value,
        accent: accent.value,
        density: density.value,
        activeQuizId: activeQuizId.value,
        mcAnswers: mcAnswers.value,
        shortAnswers: shortAnswers.value,
        shortRevealed: shortRevealed.value,
        flashIndex: flashIndex.value,
        flashFilter: flashFilter.value,
        knownMap: knownMap.value
      });
    };

    watch([view, theme, accent, density, activeQuizId, flashIndex, flashFilter,
           mcAnswers, shortAnswers, shortRevealed, knownMap], () => { persist(); }, { deep: true });
    watch([theme, accent, density], applyTweaks, { immediate: true });
    watch(flashFilter, () => { flashIndex.value = 0; flipped.value = false; });
    watch(view, () => { flipped.value = false; });

    onMounted(() => {
      applyTweaks();
      // keyboard: left/right for flashcards & modules
      window.addEventListener('keydown', (e) => {
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
        if (view.value === 'flashcards') {
          if (e.key === 'ArrowRight') nextFlash();
          if (e.key === 'ArrowLeft') prevFlash();
          if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); flipped.value = !flipped.value; }
        }
      });
    });

    return {
      data, view, drawerOpen, tweaksOpen,
      theme, accent, density,
      activeModule, activeModuleIndex, openModule,
      glossaryQuery, filteredGlossary, glossaryCount,
      activeQuizId, activeQuiz, mcAnswers, shortAnswers, shortRevealed,
      shortKey, quizAnswered, quizProgress, answerMc, revealShort, optionClass,
      flashIndex, flashFilter, flipped, knownMap, knownCount,
      visibleFlashcards, currentFlash, prevFlash, nextFlash, markFlash,
      navItems, goto, t, renderMd, renderMdInline,
      titleDisplay, shortRepo,
      moduleTintStyle
    };
  }
});

app.mount('#app');
