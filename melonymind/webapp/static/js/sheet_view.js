// After stem selection: preview / download sheet music (main user flow).

import { applyDataI18n, t } from './i18n.js';

const DEFAULT_BPM = 120;
const BPM_STORAGE_KEY = 'melonymind_sheet_bpm';

function clampBpm(n) {
  if (!Number.isFinite(n)) return DEFAULT_BPM;
  return Math.max(40, Math.min(240, Math.round(n)));
}

function getStoredBpm() {
  try {
    const raw = sessionStorage.getItem(BPM_STORAGE_KEY);
    if (raw == null) return DEFAULT_BPM;
    return clampBpm(parseInt(raw, 10));
  } catch (_) {
    return DEFAULT_BPM;
  }
}

function storeBpm(n) {
  try {
    sessionStorage.setItem(BPM_STORAGE_KEY, String(clampBpm(n)));
  } catch (_) { /* ignore */ }
}

function sheetQuery(songId, detail, tempo) {
  const title = detail.filename || 'melody';
  return new URLSearchParams({
    stem: detail.picked_stem,
    title,
    tempo: String(clampBpm(tempo)),
    time_signature: '4/4',
    key: 'C major',
  });
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
}

export async function renderSheetView({ songId, view, instantiate, toast }) {
  const frag = instantiate('tpl-sheet-view');
  view.append(frag);
  applyDataI18n(view);

  const titleEl = document.getElementById('sv-title');
  const stemEl = document.getElementById('sv-stem');
  const previewBtn = document.getElementById('sv-preview');
  const lyBtn = document.getElementById('sv-ly');
  const backStem = document.getElementById('sv-back-stem');
  const adminNotes = document.getElementById('sv-admin-notes');
  const tempoInput = document.getElementById('sv-tempo');

  const res = await fetch(`/api/songs/${songId}`);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  const detail = await res.json();

  if (!detail.picked_stem) {
    view.innerHTML = `
      <section class="sheet-view gate">
        <h2>${escapeHtml(t('sheet_gate_title'))}</h2>
        <p class="muted">${escapeHtml(t('sheet_gate_body'))}</p>
        <p><a href="#/song/${songId}/stem">${escapeHtml(t('sheet_gate_back'))}</a></p>
      </section>`;
    return;
  }

  titleEl.textContent = detail.filename || detail.relpath;
  stemEl.textContent = t('sheet_stem', { stem: detail.picked_stem });

  backStem.href = `#/song/${songId}/stem`;
  adminNotes.href = `#/song/${songId}/notes`;

  tempoInput.value = String(getStoredBpm());
  tempoInput.addEventListener('change', () => {
    const v = clampBpm(parseInt(tempoInput.value, 10));
    tempoInput.value = String(v);
    storeBpm(v);
  });

  previewBtn.addEventListener('click', () => {
    const bpm = clampBpm(parseInt(tempoInput.value, 10));
    storeBpm(bpm);
    const q = sheetQuery(songId, detail, bpm);
    q.set('sheet_format', 'html');
    window.open(`/api/songs/${songId}/sheet?${q}`, '_blank', 'noopener,noreferrer');
  });

  lyBtn.addEventListener('click', async () => {
    lyBtn.disabled = true;
    try {
      const bpm = clampBpm(parseInt(tempoInput.value, 10));
      storeBpm(bpm);
      const q = sheetQuery(songId, detail, bpm);
      q.set('sheet_format', 'lilypond');
      const url = `/api/songs/${songId}/sheet?${q}`;
      const r = await fetch(url);
      if (!r.ok) {
        let d = '';
        try {
          const j = await r.json();
          d = j.detail || '';
        } catch (_) { /* ignore */ }
        throw new Error(`${r.status}${d ? ` — ${d}` : ''}`);
      }
      const blob = await r.blob();
      const a = document.createElement('a');
      const base = String(detail.filename || 'melody').replace(/[^\w.\-]/g, '_');
      a.href = URL.createObjectURL(blob);
      a.download = `${base}.ly`;
      a.click();
      URL.revokeObjectURL(a.href);
      toast(t('toast_dl_ly'), 'success', 2500);
    } catch (err) {
      toast(t('err_dl', { msg: err.message }), 'error');
    } finally {
      lyBtn.disabled = false;
    }
  });
}
