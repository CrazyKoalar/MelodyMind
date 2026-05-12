// Stem picker view: original + 5 separated stems, click-to-pick + confirm.

import { applyDataI18n, t } from './i18n.js';

const STEM_ORDER = ['mix', 'vocals', 'accompaniment', 'bass', 'percussive'];

export async function renderStemPicker({ songId, view, instantiate, toast, api }) {
  const frag = instantiate('tpl-stem-picker');
  view.append(frag);
  applyDataI18n(view);

  const titleEl = document.getElementById('sp-title');
  const prepBlock = document.getElementById('sp-prep');
  const prepBtn = document.getElementById('sp-prepare');
  const prepMsg = document.getElementById('sp-prep-msg');
  const listEl = document.getElementById('sp-list');
  const confirmBtn = document.getElementById('sp-confirm');
  const toSheetBtn = document.getElementById('sp-to-sheet');
  const reopenBtn = document.getElementById('sp-reopen');
  const adminNotesLink = document.getElementById('sp-admin-notes');

  let detail = await api(`/api/songs/${songId}`);
  titleEl.textContent = detail.relpath;

  function setPickedState(stem) {
    listEl.querySelectorAll('.stem-row').forEach((row) => {
      row.dataset.picked = String(row.dataset.stem === stem);
    });
  }

  function setSuggestedState(scores) {
    if (!scores) return;
    const best = Object.entries(scores).sort((a, b) => b[1] - a[1])[0]?.[0];
    listEl.querySelectorAll('.stem-row').forEach((row) => {
      row.dataset.suggested = String(row.dataset.stem === best);
    });
  }

  function refreshActions() {
    toSheetBtn.disabled = !detail.picked_stem;
    confirmBtn.disabled = !detail.picked_stem || detail.status === 'confirmed';
    reopenBtn.hidden = detail.status !== 'confirmed';
    confirmBtn.hidden = detail.status === 'confirmed';
    toSheetBtn.classList.toggle('primary', Boolean(detail.picked_stem));
  }

  function renderRows() {
    listEl.innerHTML = '';
    for (const stem of STEM_ORDER) {
      const tpl = instantiate('tpl-stem-row');
      applyDataI18n(tpl);
      const row = tpl.querySelector('.stem-row');
      row.dataset.stem = stem;
      row.querySelector('.stem-name').textContent = stem;
      const score = detail.candidate_scores?.[stem];
      if (score != null) {
        row.querySelector('.stem-score').textContent = t('stem_score', { v: score.toFixed(3) });
      }
      const audio = row.querySelector('audio');
      audio.src = `/media/${songId}/stems/${stem}`;
      audio.dataset.stem = stem;
      audio.addEventListener('play', () => {
        listEl.querySelectorAll('audio').forEach((a) => { if (a !== audio) a.pause(); });
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
      toast(t('toast_picked', { stem }), 'success', 2000);
    } catch (err) {
      toast(t('err_pick', { msg: err.message }), 'error');
    }
  }

  async function prepare(force = false) {
    prepBtn.disabled = true;
    prepMsg.textContent = t('stem_prep_msg');
    try {
      const res = await api(`/api/songs/${songId}/compute`, {
        method: 'POST',
        body: { force },
      });
      detail = await api(`/api/songs/${songId}`);
      prepBlock.hidden = true;
      renderRows();
      refreshActions();
      const note = res.cached ? t('stem_toast_cached') : t('stem_toast_prepared');
      toast(t('stem_toast_suggested', { note, stem: res.suggested_stem }), 'success');
    } catch (err) {
      prepMsg.textContent = '';
      prepBtn.disabled = false;
      toast(t('err_prepare', { msg: err.message }), 'error');
    }
  }

  if (!detail.cache_ready) {
    prepBlock.hidden = false;
    listEl.innerHTML = `<li class="muted" style="padding:12px;">${escapeHtml(t('stem_prep_hint'))}</li>`;
  } else {
    renderRows();
  }
  refreshActions();

  prepBtn.addEventListener('click', () => prepare(false));

  adminNotesLink.href = `#/song/${songId}/notes`;

  toSheetBtn.addEventListener('click', () => {
    location.hash = `#/song/${songId}/sheet`;
  });

  confirmBtn.addEventListener('click', async () => {
    try {
      const res = await api(`/api/songs/${songId}/confirm`, { method: 'POST' });
      detail.status = res.status;
      refreshActions();
      toast(t('toast_confirmed'), 'success', 1800);
    } catch (err) {
      toast(t('err_confirm', { msg: err.message }), 'error');
    }
  });

  reopenBtn.addEventListener('click', async () => {
    try {
      const res = await api(`/api/songs/${songId}/reopen`, { method: 'POST' });
      detail.status = res.status;
      refreshActions();
    } catch (err) {
      toast(t('err_reopen', { msg: err.message }), 'error');
    }
  });
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
}
