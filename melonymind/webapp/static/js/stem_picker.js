// Stem picker view: original + 5 separated stems, click-to-pick + confirm.

const STEM_ORDER = ['mix', 'vocals', 'accompaniment', 'bass', 'percussive'];

export async function renderStemPicker({ songId, view, instantiate, toast, api }) {
  view.append(instantiate('tpl-stem-picker'));

  const titleEl = document.getElementById('sp-title');
  const prepBlock = document.getElementById('sp-prep');
  const prepBtn = document.getElementById('sp-prepare');
  const prepMsg = document.getElementById('sp-prep-msg');
  const listEl = document.getElementById('sp-list');
  const confirmBtn = document.getElementById('sp-confirm');
  const editNotesBtn = document.getElementById('sp-edit-notes');
  const reopenBtn = document.getElementById('sp-reopen');

  let detail = await api(`/api/songs/${songId}`);
  titleEl.textContent = detail.relpath;

  function setPickedState(stem) {
    listEl.querySelectorAll('.stem-row').forEach(row => {
      row.dataset.picked = String(row.dataset.stem === stem);
    });
  }

  function setSuggestedState(scores) {
    if (!scores) return;
    const best = Object.entries(scores).sort((a, b) => b[1] - a[1])[0]?.[0];
    listEl.querySelectorAll('.stem-row').forEach(row => {
      row.dataset.suggested = String(row.dataset.stem === best);
    });
  }

  function refreshActions() {
    confirmBtn.disabled = !detail.picked_stem || detail.status === 'confirmed';
    editNotesBtn.disabled = !detail.picked_stem;
    reopenBtn.hidden = detail.status !== 'confirmed';
    confirmBtn.hidden = detail.status === 'confirmed';
    confirmBtn.classList.toggle('primary', !confirmBtn.disabled);
  }

  function renderRows() {
    listEl.innerHTML = '';
    for (const stem of STEM_ORDER) {
      const tpl = instantiate('tpl-stem-row');
      const row = tpl.querySelector('.stem-row');
      row.dataset.stem = stem;
      row.querySelector('.stem-name').textContent = stem;
      const score = detail.candidate_scores?.[stem];
      if (score != null) {
        row.querySelector('.stem-score').textContent = `score ${score.toFixed(3)}`;
      }
      const audio = row.querySelector('audio');
      audio.src = `/media/${songId}/stems/${stem}`;
      audio.dataset.stem = stem;
      audio.addEventListener('play', () => {
        // Pause other stems for clearer A/B comparison.
        listEl.querySelectorAll('audio').forEach(a => { if (a !== audio) a.pause(); });
      });
      const pickBtn = row.querySelector('.stem-pick');
      pickBtn.addEventListener('click', () => pick(stem));
      listEl.append(tpl);
    }
    setPickedState(detail.picked_stem);
    setSuggestedState(detail.candidate_scores);
  }

  async function pick(stem) {
    try {
      const res = await api(`/api/songs/${songId}/stem`, {
        method: 'POST',
        body: { stem },
      });
      detail.picked_stem = res.picked_stem;
      detail.status = res.status;
      setPickedState(detail.picked_stem);
      refreshActions();
      toast(`Picked: ${stem}`, 'success', 2000);
    } catch (err) {
      toast(`Pick failed: ${err.message}`, 'error');
    }
  }

  async function prepare(force = false) {
    prepBtn.disabled = true;
    prepMsg.textContent = 'Preparing stems… first run can take 30–60 s.';
    try {
      const res = await api(`/api/songs/${songId}/compute`, {
        method: 'POST',
        body: { force },
      });
      detail = await api(`/api/songs/${songId}`);
      prepBlock.hidden = true;
      renderRows();
      refreshActions();
      const note = res.cached ? 'Loaded from cache.' : 'Stems prepared.';
      toast(`${note} Suggested: ${res.suggested_stem}`, 'success');
    } catch (err) {
      prepMsg.textContent = '';
      prepBtn.disabled = false;
      toast(`Prepare failed: ${err.message}`, 'error');
    }
  }

  if (!detail.cache_ready) {
    prepBlock.hidden = false;
    listEl.innerHTML = '<li class="muted" style="padding:12px;">Click prepare to extract stems.</li>';
  } else {
    renderRows();
  }
  refreshActions();

  prepBtn.addEventListener('click', () => prepare(false));

  confirmBtn.addEventListener('click', async () => {
    try {
      const res = await api(`/api/songs/${songId}/confirm`, { method: 'POST' });
      detail.status = res.status;
      refreshActions();
      toast('Confirmed.', 'success', 1800);
    } catch (err) {
      toast(`Confirm failed: ${err.message}`, 'error');
    }
  });

  reopenBtn.addEventListener('click', async () => {
    try {
      const res = await api(`/api/songs/${songId}/reopen`, { method: 'POST' });
      detail.status = res.status;
      refreshActions();
    } catch (err) {
      toast(`Reopen failed: ${err.message}`, 'error');
    }
  });

  editNotesBtn.addEventListener('click', () => {
    location.hash = `#/song/${songId}/notes`;
  });
}
