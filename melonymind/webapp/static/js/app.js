// MelodyMind annotation tool — top-level router and shared utilities.

import { renderStemPicker } from './stem_picker.js';
import { renderNoteEditor } from './piano_roll.js';

const view = document.getElementById('view');
const navContext = document.getElementById('nav-context');
const toastEl = document.getElementById('toast');
const exportBtn = document.getElementById('btn-export');

let toastTimer = null;

export function toast(msg, kind = 'info', ms = 3500) {
  toastEl.textContent = msg;
  toastEl.className = `toast ${kind === 'error' ? 'error' : kind === 'success' ? 'success' : ''}`;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, ms);
}

export async function api(path, options = {}) {
  const headers = options.body && !(options.body instanceof FormData)
    ? { 'Content-Type': 'application/json', ...(options.headers || {}) }
    : (options.headers || {});
  const body = options.body && typeof options.body === 'object' && !(options.body instanceof FormData)
    ? JSON.stringify(options.body)
    : options.body;
  const response = await fetch(path, { ...options, headers, body });
  if (!response.ok) {
    let detail = '';
    try { detail = (await response.json()).detail || ''; } catch (_) { /* ignore */ }
    throw new Error(`${response.status} ${response.statusText}${detail ? ` — ${detail}` : ''}`);
  }
  return response.json();
}

function setNavContext(text, link = null) {
  navContext.textContent = '';
  if (!text) return;
  navContext.append(' / ');
  if (link) {
    const a = document.createElement('a');
    a.href = link;
    a.textContent = text;
    navContext.append(a);
  } else {
    const span = document.createElement('span');
    span.textContent = text;
    span.className = 'muted';
    navContext.append(span);
  }
}

function clearView() { view.innerHTML = ''; }

function instantiate(templateId) {
  const tpl = document.getElementById(templateId);
  return tpl.content.cloneNode(true);
}

function fmtDuration(sec) {
  if (sec == null || Number.isNaN(sec)) return '—';
  const total = Math.round(sec);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

// ---------- song list ----------

async function renderSongList() {
  clearView();
  setNavContext(null);

  const frag = instantiate('tpl-song-list');
  view.append(frag);

  const filterInput = document.getElementById('filter');
  const tbody = document.getElementById('rows');
  const counts = document.getElementById('counts');
  const fileInput = document.getElementById('file-upload');
  const autoComputeEl = document.getElementById('auto-compute');
  const uploadStatus = document.getElementById('upload-status');

  let songs = [];
  try {
    const payload = await api('/api/songs');
    songs = payload.songs;
  } catch (err) {
    toast(`Could not list songs: ${err.message}`, 'error', 6000);
    return;
  }

  function paint() {
    const needle = filterInput.value.trim().toLowerCase();
    const filtered = needle ? songs.filter(s => s.filename.toLowerCase().includes(needle)) : songs;
    tbody.innerHTML = '';
    for (const song of filtered) {
      const tr = document.createElement('tr');
      tr.dataset.id = song.id;
      tr.innerHTML = `
        <td>${escapeHtml(song.filename)}</td>
        <td><span class="badge ${song.status}">${song.status}</span></td>
        <td>${song.picked_stem ? escapeHtml(song.picked_stem) : '<span class="muted">—</span>'}</td>
        <td>${fmtDuration(song.duration_sec)}</td>
        <td><button class="open">Open →</button></td>
      `;
      tr.querySelector('.open').addEventListener('click', (e) => {
        e.stopPropagation();
        location.hash = `#/song/${song.id}/stem`;
      });
      tr.addEventListener('click', () => {
        location.hash = `#/song/${song.id}/stem`;
      });
      tbody.append(tr);
    }

    const total = songs.length;
    const confirmed = songs.filter(s => s.status === 'confirmed').length;
    counts.textContent = `${filtered.length} shown · ${confirmed} confirmed / ${total} total`;
  }

  filterInput.addEventListener('input', paint);
  paint();

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    uploadStatus.hidden = false;
    uploadStatus.textContent = 'Uploading…';
    const fd = new FormData();
    fd.append('file', file);
    fd.append('auto_compute', autoComputeEl.checked ? 'true' : 'false');
    try {
      const res = await fetch('/api/songs/upload', { method: 'POST', body: fd });
      if (!res.ok) {
        let detail = '';
        try {
          const j = await res.json();
          detail = j.detail || '';
        } catch (_) { /* ignore */ }
        throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ''}`);
      }
      const data = await res.json();
      uploadStatus.textContent = '';
      uploadStatus.hidden = true;
      const ran = data.compute && !data.compute.cached;
      toast(
        ran ? 'Uploaded and analyzed. Opening stem picker…' : 'Uploaded. Opening stem picker…',
        'success',
      );
      location.hash = `#/song/${data.song.id}/stem`;
    } catch (err) {
      uploadStatus.textContent = err.message;
      toast(`Upload failed: ${err.message}`, 'error', 6000);
    } finally {
      fileInput.value = '';
    }
  });
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

// ---------- router ----------

async function route() {
  const hash = location.hash || '#/';
  const stemMatch = hash.match(/^#\/song\/([^/]+)\/stem$/);
  const notesMatch = hash.match(/^#\/song\/([^/]+)\/notes$/);

  if (stemMatch) {
    const songId = stemMatch[1];
    setNavContext('stem picker', `#/song/${songId}/stem`);
    clearView();
    try {
      await renderStemPicker({ songId, view, instantiate, toast, api });
    } catch (err) {
      toast(`Failed to load song: ${err.message}`, 'error', 6000);
    }
    return;
  }

  if (notesMatch) {
    const songId = notesMatch[1];
    setNavContext('note editor', `#/song/${songId}/notes`);
    clearView();
    try {
      await renderNoteEditor({ songId, view, instantiate, toast, api });
    } catch (err) {
      toast(`Failed to load editor: ${err.message}`, 'error', 6000);
    }
    return;
  }

  await renderSongList();
}

window.addEventListener('hashchange', route);
window.addEventListener('DOMContentLoaded', route);

// ---------- export button ----------

exportBtn.addEventListener('click', async () => {
  exportBtn.disabled = true;
  try {
    const result = await api('/api/export', {
      method: 'POST',
      body: { only_confirmed: true },
    });
    const msg = `Exported ${result.count} song(s).\nManifest: ${result.melody_manifest}\nNotes:    ${result.notes_manifest}\nReview:   ${result.review_csv}`;
    toast(msg, 'success', 12000);

    // Replace the toast plain text with a richer node carrying a Reveal button
    toastEl.textContent = '';
    const pre = document.createElement('pre');
    pre.style.cssText = 'margin:0 0 8px 0; white-space:pre-wrap; font: 12px ui-monospace, monospace;';
    pre.textContent = msg;
    toastEl.append(pre);
    const reveal = document.createElement('button');
    reveal.textContent = 'Reveal in Explorer';
    reveal.addEventListener('click', async () => {
      try {
        await api('/api/reveal', { method: 'POST', body: { path: result.melody_manifest } });
      } catch (err) {
        toast(`Reveal failed: ${err.message}`, 'error');
      }
    });
    toastEl.append(reveal);
  } catch (err) {
    toast(`Export failed: ${err.message}`, 'error', 6000);
  } finally {
    exportBtn.disabled = false;
  }
});
