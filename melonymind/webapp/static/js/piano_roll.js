// Canvas-based piano roll note editor.
// Three stacked canvases: bg (grid + keyboard + ruler), notes, overlay (playhead, marquee, ghost).

import { applyDataI18n, t } from './i18n.js';
import { syncPlayhead } from './audio_sync.js';

const PITCH_MIN_DEFAULT = 36;   // C2
const PITCH_MAX_DEFAULT = 84;   // C6
const KEYBOARD_W = 44;
const RULER_H = 24;
const BPM = 120;
const SECONDS_PER_BEAT = 60 / BPM;
const GRID_DIV = 16;
const SNAP_T = SECONDS_PER_BEAT / (GRID_DIV / 4); // 1/16 note in seconds (= 0.125s @ 120 BPM)
const RESIZE_HANDLE_PX = 6;
const AUTO_SAVE_MS = 2000;
const SHEET_BPM_STORAGE_KEY = 'melonymind_sheet_bpm';

function sheetExportBpm() {
  try {
    const raw = sessionStorage.getItem(SHEET_BPM_STORAGE_KEY);
    if (raw == null) return BPM;
    const n = parseInt(raw, 10);
    if (!Number.isFinite(n)) return BPM;
    return Math.max(40, Math.min(240, Math.round(n)));
  } catch (_) {
    return BPM;
  }
}

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
function noteName(midi) {
  return `${NOTE_NAMES[midi % 12]}${Math.floor(midi / 12) - 1}`;
}
function isBlackKey(midi) {
  return [1, 3, 6, 8, 10].includes(midi % 12);
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
}

export async function renderNoteEditor({ songId, view, instantiate, toast, api }) {
  const rootFrag = instantiate('tpl-note-editor');
  view.append(rootFrag);
  applyDataI18n(view);

  const adminBanner = document.getElementById('ne-admin-banner');
  if (adminBanner) {
    adminBanner.innerHTML = t('editor_admin_html');
  }

  const titleEl = document.getElementById('ne-title');
  const playBtn = document.getElementById('ne-play');
  const stopBtn = document.getElementById('ne-stop');
  const timeEl = document.getElementById('ne-time');
  const statusEl = document.getElementById('ne-status');
  const saveBtn = document.getElementById('ne-save');
  const reextractBtn = document.getElementById('ne-reextract');
  const sheetLyBtn = document.getElementById('ne-sheet-ly');
  const sheetHtmlBtn = document.getElementById('ne-sheet-html');
  const rollEl = document.getElementById('piano-roll');
  const bgCanvas = document.getElementById('pr-bg');
  const notesCanvas = document.getElementById('pr-notes');
  const overlayCanvas = document.getElementById('pr-overlay');

  // Song detail to know the stem and duration
  const detail = await api(`/api/songs/${songId}`);
  if (!detail.picked_stem) {
    view.innerHTML = `
      <section style="max-width:600px;margin:40px auto;text-align:center;">
        <h2>${escapeHtml(t('editor_gate_title'))}</h2>
        <p>${escapeHtml(t('editor_gate_line1'))}</p>
        <p><a href="#/song/${songId}/stem">${escapeHtml(t('editor_gate_stem'))}</a> · <a href="#/song/${songId}/sheet">${escapeHtml(t('editor_gate_sheet'))}</a></p>
      </section>`;
    return;
  }

  titleEl.textContent = `${detail.relpath} · ${detail.picked_stem}`;
  const backSheet = document.getElementById('ne-back-sheet');
  if (backSheet) backSheet.href = `#/song/${songId}/sheet`;

  // Fetch notes
  const notesPayload = await api(`/api/songs/${songId}/notes?stem=${encodeURIComponent(detail.picked_stem)}`);
  const sr = notesPayload.sr;
  let notes = notesPayload.notes.map((n, i) => ({
    id: n.id ?? i,
    pitch: n.pitch,
    start: n.start,
    end: n.end,
    confidence: n.confidence ?? 1.0,
  }));
  let nextId = (notes.reduce((m, n) => Math.max(m, n.id), -1) + 1) || notes.length;

  // Audio
  const audio = new Audio(`/media/${songId}/stems/${encodeURIComponent(detail.picked_stem)}`);
  audio.preload = 'metadata';
  audio.addEventListener('loadedmetadata', () => {
    state.duration = audio.duration || state.duration;
    fitInitialView();
    draw();
  });

  // View state
  const state = {
    pitchMin: PITCH_MIN_DEFAULT,
    pitchMax: PITCH_MAX_DEFAULT,
    timeStart: 0,
    timeEnd: Math.max(8, detail.duration_sec || 8),
    duration: detail.duration_sec || 0,
    cursor: 0,
    selected: new Set(),
    dirty: false,
  };

  function fitInitialView() {
    // Pad slightly so the first note isn't pinned to the left edge.
    state.timeStart = 0;
    state.timeEnd = Math.max(8, state.duration || 8);
    if (notes.length) {
      const maxEnd = Math.max(...notes.map(n => n.end));
      state.timeEnd = Math.max(state.timeEnd, maxEnd + 1);
    }
  }
  fitInitialView();

  // ---------- canvas sizing ----------

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    const { width, height } = rollEl.getBoundingClientRect();
    for (const canvas of [bgCanvas, notesCanvas, overlayCanvas]) {
      canvas.width = Math.max(1, Math.floor(width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
      canvas.style.width = width + 'px';
      canvas.style.height = height + 'px';
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    draw();
  }

  // ---------- coord transforms ----------

  function plotRect() {
    const { width, height } = rollEl.getBoundingClientRect();
    return {
      x: KEYBOARD_W,
      y: RULER_H,
      w: Math.max(1, width - KEYBOARD_W),
      h: Math.max(1, height - RULER_H),
    };
  }

  function timeToX(t) {
    const r = plotRect();
    return r.x + ((t - state.timeStart) / (state.timeEnd - state.timeStart)) * r.w;
  }
  function xToTime(x) {
    const r = plotRect();
    return state.timeStart + ((x - r.x) / r.w) * (state.timeEnd - state.timeStart);
  }
  function pitchRowCount() { return state.pitchMax - state.pitchMin + 1; }
  function rowHeight() { return plotRect().h / pitchRowCount(); }
  function pitchToY(p) {
    const r = plotRect();
    const rows = pitchRowCount();
    return r.y + ((state.pitchMax - p) / rows) * r.h;
  }
  function yToPitch(y) {
    const r = plotRect();
    const rows = pitchRowCount();
    const row = Math.floor((y - r.y) / (r.h / rows));
    return Math.max(state.pitchMin, Math.min(state.pitchMax, state.pitchMax - row));
  }

  function snapTime(t, freeMode = false) {
    if (freeMode) return Math.max(0, t);
    return Math.max(0, Math.round(t / SNAP_T) * SNAP_T);
  }

  // ---------- drawing ----------

  function draw() {
    drawBg();
    drawNotes();
    drawOverlay();
  }

  function drawBg() {
    const ctx = bgCanvas.getContext('2d');
    const { width, height } = rollEl.getBoundingClientRect();
    ctx.clearRect(0, 0, width, height);
    const r = plotRect();
    const rh = rowHeight();

    // Pitch rows
    for (let p = state.pitchMin; p <= state.pitchMax; p++) {
      const y = pitchToY(p);
      ctx.fillStyle = isBlackKey(p) ? '#1a1f27' : '#212833';
      ctx.fillRect(r.x, y - rh, r.w, rh);
    }

    // Vertical grid: beats heavy, 1/16 light
    const visTime = state.timeEnd - state.timeStart;
    const showBeats = visTime / SECONDS_PER_BEAT < 80;
    const showSixteenths = visTime / SNAP_T < 200;
    const tickStart = Math.floor(state.timeStart / SNAP_T) * SNAP_T;
    for (let t = tickStart; t <= state.timeEnd; t += SNAP_T) {
      const x = timeToX(t);
      if (x < r.x) continue;
      const isBeat = Math.abs((t / SECONDS_PER_BEAT) - Math.round(t / SECONDS_PER_BEAT)) < 1e-3;
      const isBar = isBeat && Math.round(t / SECONDS_PER_BEAT) % 4 === 0;
      if (isBar) {
        ctx.strokeStyle = '#3a414c';
      } else if (isBeat && showBeats) {
        ctx.strokeStyle = '#30363d';
      } else if (showSixteenths) {
        ctx.strokeStyle = '#262c35';
      } else {
        continue;
      }
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + 0.5, r.y);
      ctx.lineTo(x + 0.5, r.y + r.h);
      ctx.stroke();
    }

    // Horizontal pitch lines (every C is brighter)
    for (let p = state.pitchMin; p <= state.pitchMax; p++) {
      const y = pitchToY(p);
      ctx.strokeStyle = (p % 12 === 0) ? '#3a414c' : '#262c35';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(r.x, Math.floor(y) + 0.5);
      ctx.lineTo(r.x + r.w, Math.floor(y) + 0.5);
      ctx.stroke();
    }

    // Keyboard
    ctx.fillStyle = '#11151b';
    ctx.fillRect(0, 0, KEYBOARD_W, height);
    for (let p = state.pitchMin; p <= state.pitchMax; p++) {
      const y = pitchToY(p);
      ctx.fillStyle = isBlackKey(p) ? '#2a2f37' : '#e6edf3';
      ctx.fillRect(0, y - rh, KEYBOARD_W - 1, rh);
      if (p % 12 === 0) {
        ctx.fillStyle = '#0f1217';
        ctx.font = '10px ui-monospace, monospace';
        ctx.fillText(noteName(p), 4, y - 4);
      }
    }

    // Top ruler
    ctx.fillStyle = '#11151b';
    ctx.fillRect(KEYBOARD_W, 0, width - KEYBOARD_W, RULER_H);
    ctx.fillStyle = '#8b949e';
    ctx.font = '11px ui-monospace, monospace';
    for (let t = Math.ceil(state.timeStart); t <= state.timeEnd; t++) {
      const x = timeToX(t);
      if (x < KEYBOARD_W) continue;
      ctx.fillRect(x, RULER_H - 6, 1, 6);
      ctx.fillText(`${t}s`, x + 3, RULER_H - 8);
    }
    ctx.strokeStyle = '#30363d';
    ctx.beginPath();
    ctx.moveTo(KEYBOARD_W, RULER_H + 0.5);
    ctx.lineTo(width, RULER_H + 0.5);
    ctx.stroke();
  }

  function drawNotes() {
    const ctx = notesCanvas.getContext('2d');
    const { width, height } = rollEl.getBoundingClientRect();
    ctx.clearRect(0, 0, width, height);
    const r = plotRect();
    ctx.save();
    ctx.beginPath();
    ctx.rect(r.x, r.y, r.w, r.h);
    ctx.clip();

    for (const note of notes) {
      if (note.pitch < state.pitchMin || note.pitch > state.pitchMax) continue;
      if (note.end < state.timeStart || note.start > state.timeEnd) continue;
      const x1 = timeToX(note.start);
      const x2 = timeToX(note.end);
      const y = pitchToY(note.pitch);
      const rh = rowHeight();
      const selected = state.selected.has(note.id);
      ctx.fillStyle = selected ? '#ffd166' : `rgba(88,166,255,${0.55 + 0.4 * (note.confidence ?? 1)})`;
      ctx.fillRect(x1, y - rh + 1, Math.max(2, x2 - x1), Math.max(2, rh - 2));
      ctx.strokeStyle = selected ? '#ff9c39' : '#1f6feb';
      ctx.lineWidth = selected ? 2 : 1;
      ctx.strokeRect(x1 + 0.5, y - rh + 1.5, Math.max(2, x2 - x1) - 1, Math.max(2, rh - 2) - 1);
    }

    ctx.restore();
  }

  function drawOverlay() {
    const ctx = overlayCanvas.getContext('2d');
    const { width, height } = rollEl.getBoundingClientRect();
    ctx.clearRect(0, 0, width, height);
    const r = plotRect();

    // Playhead
    if (state.cursor >= state.timeStart && state.cursor <= state.timeEnd) {
      const x = timeToX(state.cursor);
      ctx.strokeStyle = '#ff6b6b';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }

    if (drag && drag.mode === 'marquee') {
      const { x0, y0, x1, y1 } = drag.bounds;
      ctx.fillStyle = 'rgba(88,166,255,0.15)';
      ctx.strokeStyle = '#58a6ff';
      ctx.lineWidth = 1;
      ctx.fillRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
      ctx.strokeRect(Math.min(x0, x1) + 0.5, Math.min(y0, y1) + 0.5, Math.abs(x1 - x0), Math.abs(y1 - y0));
    }
  }

  function drawOverlayOnly() { drawOverlay(); }

  // ---------- hit testing ----------

  function noteAt(x, y) {
    for (let i = notes.length - 1; i >= 0; i--) {
      const note = notes[i];
      const y0 = pitchToY(note.pitch) - rowHeight() + 1;
      const y1 = pitchToY(note.pitch) - 1;
      const x0 = timeToX(note.start);
      const x1 = timeToX(note.end);
      if (x >= x0 && x <= x1 && y >= y0 && y <= y1) {
        let edge = 'body';
        if (x - x0 < RESIZE_HANDLE_PX) edge = 'left';
        else if (x1 - x < RESIZE_HANDLE_PX) edge = 'right';
        return { note, edge };
      }
    }
    return null;
  }

  // ---------- interaction state ----------

  let drag = null;
  let saveTimer = null;

  function markDirty() {
    state.dirty = true;
    statusEl.textContent = t('editor_status_unsaved');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, AUTO_SAVE_MS);
  }

  async function save() {
    if (!state.dirty) return;
    clearTimeout(saveTimer);
    saveTimer = null;
    statusEl.textContent = t('editor_status_saving');
    try {
      const body = {
        stem: detail.picked_stem,
        notes: notes.map(n => ({
          id: n.id, pitch: n.pitch, start: n.start, end: n.end, confidence: n.confidence ?? 1.0,
        })),
      };
      await api(`/api/songs/${songId}/notes`, { method: 'PUT', body });
      state.dirty = false;
      statusEl.textContent = t('editor_status_saved');
      setTimeout(() => { if (!state.dirty) statusEl.textContent = ''; }, 1500);
    } catch (err) {
      statusEl.textContent = '';
      toast(t('editor_err_save', { msg: err.message }), 'error');
    }
  }

  function getMouse(e) {
    const r = rollEl.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  notesCanvas.addEventListener('mousedown', () => {});
  overlayCanvas.addEventListener('mousedown', (e) => {
    const { x, y } = getMouse(e);

    // Ruler seek
    if (y < RULER_H && x >= KEYBOARD_W) {
      const t = Math.max(0, xToTime(x));
      audio.currentTime = t;
      state.cursor = t;
      drawOverlayOnly();
      return;
    }

    if (x < KEYBOARD_W || y < RULER_H) return;

    if (e.button === 1) {
      // Middle = pan
      drag = { mode: 'pan', startX: e.clientX, startY: e.clientY, t0: state.timeStart, t1: state.timeEnd, p0: state.pitchMin, p1: state.pitchMax };
      e.preventDefault();
      return;
    }

    const hit = noteAt(x, y);
    if (hit) {
      if (!state.selected.has(hit.note.id)) {
        if (!e.shiftKey) state.selected.clear();
        state.selected.add(hit.note.id);
        drawNotes();
      }
      drag = {
        mode: hit.edge === 'body' ? 'move' : `resize-${hit.edge}`,
        anchor: hit.note,
        startX: x, startY: y,
        snapshot: snapshotSelected(),
        altKey: e.altKey,
      };
    } else {
      if (!e.shiftKey) state.selected.clear();
      if (e.button === 0 && (e.metaKey || e.ctrlKey)) {
        drag = { mode: 'marquee', bounds: { x0: x, y0: y, x1: x, y1: y } };
      } else {
        // Empty click: add a new note
        const pitch = yToPitch(y);
        const start = snapTime(xToTime(x), e.altKey);
        const newNote = {
          id: nextId++,
          pitch,
          start,
          end: start + Math.max(SNAP_T, 0.25),
          confidence: 1.0,
        };
        notes.push(newNote);
        state.selected.clear();
        state.selected.add(newNote.id);
        markDirty();
        drawNotes();
        // Continue with resize-right so the user can drag to set duration
        drag = {
          mode: 'resize-right',
          anchor: newNote,
          startX: x, startY: y,
          snapshot: snapshotSelected(),
          altKey: e.altKey,
        };
      }
    }
  });

  function snapshotSelected() {
    return notes
      .filter(n => state.selected.has(n.id))
      .map(n => ({ id: n.id, pitch: n.pitch, start: n.start, end: n.end }));
  }

  window.addEventListener('mousemove', (e) => {
    if (!drag) return;
    const { x, y } = getMouse(e);
    const r = plotRect();

    if (drag.mode === 'pan') {
      const dx = (e.clientX - drag.startX);
      const dy = (e.clientY - drag.startY);
      const tSpan = drag.t1 - drag.t0;
      const dt = -(dx / r.w) * tSpan;
      const pSpan = drag.p1 - drag.p0;
      const dp = Math.round((dy / r.h) * pSpan);
      state.timeStart = Math.max(0, drag.t0 + dt);
      state.timeEnd = state.timeStart + tSpan;
      state.pitchMin = Math.max(0, drag.p0 + dp);
      state.pitchMax = Math.min(127, drag.p1 + dp);
      if (state.pitchMin >= state.pitchMax) state.pitchMax = state.pitchMin + 1;
      draw();
      return;
    }

    if (drag.mode === 'marquee') {
      drag.bounds.x1 = x;
      drag.bounds.y1 = y;
      drawOverlayOnly();
      return;
    }

    if (drag.mode === 'move') {
      const baseNote = drag.snapshot.find(s => s.id === drag.anchor.id);
      const dxTime = xToTime(x) - xToTime(drag.startX);
      const newStart = snapTime(baseNote.start + dxTime, drag.altKey);
      const dt = newStart - baseNote.start;
      const dPitch = yToPitch(y) - yToPitch(drag.startY);
      for (const snap of drag.snapshot) {
        const n = notes.find(nn => nn.id === snap.id);
        n.start = Math.max(0, snap.start + dt);
        n.end = n.start + (snap.end - snap.start);
        n.pitch = Math.max(state.pitchMin, Math.min(state.pitchMax, snap.pitch + dPitch));
      }
      drawNotes();
      return;
    }

    if (drag.mode === 'resize-left' || drag.mode === 'resize-right') {
      const isLeft = drag.mode === 'resize-left';
      for (const snap of drag.snapshot) {
        const n = notes.find(nn => nn.id === snap.id);
        if (isLeft) {
          const newStart = snapTime(xToTime(x), drag.altKey);
          n.start = Math.min(n.end - 0.05, Math.max(0, newStart));
        } else {
          const newEnd = snapTime(xToTime(x), drag.altKey);
          n.end = Math.max(n.start + 0.05, newEnd);
        }
      }
      drawNotes();
      return;
    }
  });

  window.addEventListener('mouseup', () => {
    if (!drag) return;
    if (drag.mode === 'marquee') {
      const { x0, y0, x1, y1 } = drag.bounds;
      const xmin = Math.min(x0, x1), xmax = Math.max(x0, x1);
      const ymin = Math.min(y0, y1), ymax = Math.max(y0, y1);
      for (const n of notes) {
        const nx0 = timeToX(n.start), nx1 = timeToX(n.end);
        const ny0 = pitchToY(n.pitch) - rowHeight(), ny1 = pitchToY(n.pitch);
        if (nx0 < xmax && nx1 > xmin && ny0 < ymax && ny1 > ymin) {
          state.selected.add(n.id);
        }
      }
      drawNotes();
      drawOverlayOnly();
    } else if (drag.mode === 'move' || drag.mode === 'resize-left' || drag.mode === 'resize-right') {
      markDirty();
    }
    drag = null;
  });

  overlayCanvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const { x, y } = getMouse(e);
    if (e.ctrlKey || e.metaKey) {
      // Time zoom around mouse x
      const tAt = xToTime(x);
      const factor = e.deltaY > 0 ? 1.2 : 1 / 1.2;
      const newSpan = (state.timeEnd - state.timeStart) * factor;
      const ratio = (tAt - state.timeStart) / (state.timeEnd - state.timeStart);
      state.timeStart = Math.max(0, tAt - ratio * newSpan);
      state.timeEnd = state.timeStart + newSpan;
    } else if (e.shiftKey) {
      // Pitch zoom around mouse y
      const pAt = yToPitch(y);
      const factor = e.deltaY > 0 ? 1.15 : 1 / 1.15;
      const newRows = Math.max(6, Math.round(pitchRowCount() * factor));
      const half = Math.floor(newRows / 2);
      state.pitchMin = Math.max(0, pAt - half);
      state.pitchMax = Math.min(127, state.pitchMin + newRows - 1);
    } else {
      // Vertical scroll: pitch
      const step = e.deltaY > 0 ? 2 : -2;
      const span = state.pitchMax - state.pitchMin;
      state.pitchMin = Math.max(0, state.pitchMin + step);
      state.pitchMax = Math.min(127, state.pitchMin + span);
    }
    draw();
  }, { passive: false });

  window.addEventListener('keydown', (e) => {
    if (document.activeElement && ['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
    if (e.key === 'Delete' || e.key === 'Backspace') {
      if (state.selected.size === 0) return;
      notes = notes.filter(n => !state.selected.has(n.id));
      state.selected.clear();
      markDirty();
      drawNotes();
      e.preventDefault();
    } else if (e.key === ' ' || e.code === 'Space') {
      if (audio.paused) audio.play(); else audio.pause();
      e.preventDefault();
    } else if (e.key === 'Escape') {
      state.selected.clear();
      drawNotes();
    } else if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      save();
    } else if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
      e.preventDefault();
      for (const n of notes) state.selected.add(n.id);
      drawNotes();
    }
  });

  // ---------- transport ----------

  playBtn.addEventListener('click', () => audio.play());
  stopBtn.addEventListener('click', () => { audio.pause(); audio.currentTime = 0; });
  saveBtn.addEventListener('click', save);

  function sheetParams() {
    const title = detail.filename || 'melody';
    return new URLSearchParams({
      stem: detail.picked_stem,
      title,
      tempo: String(sheetExportBpm()),
      time_signature: '4/4',
      key: 'C major',
    });
  }

  async function ensureSavedForSheet() {
    if (state.dirty) await save();
  }

  sheetLyBtn.addEventListener('click', async () => {
    try {
      await ensureSavedForSheet();
      const params = sheetParams();
      params.set('sheet_format', 'lilypond');
      const url = `/api/songs/${songId}/sheet?${params}`;
      const res = await fetch(url);
      if (!res.ok) {
        let detail = '';
        try {
          const j = await res.json();
          detail = j.detail || '';
        } catch (_) { /* ignore */ }
        throw new Error(`${res.status}${detail ? ` — ${detail}` : ''}`);
      }
      const blob = await res.blob();
      const a = document.createElement('a');
      const base = String(detail.filename || 'melody').replace(/[^\w.\-]/g, '_');
      a.href = URL.createObjectURL(blob);
      a.download = `${base}.ly`;
      a.click();
      URL.revokeObjectURL(a.href);
      toast(t('editor_toast_sheet_ok'), 'success', 2500);
    } catch (err) {
      toast(t('editor_err_sheet', { msg: err.message }), 'error');
    }
  });

  sheetHtmlBtn.addEventListener('click', async () => {
    try {
      await ensureSavedForSheet();
      const params = sheetParams();
      params.set('sheet_format', 'html');
      window.open(`/api/songs/${songId}/sheet?${params}`, '_blank', 'noopener,noreferrer');
    } catch (err) {
      toast(t('editor_err_preview', { msg: err.message }), 'error');
    }
  });

  reextractBtn.addEventListener('click', async () => {
    if (state.dirty && !confirm(t('editor_reextract_confirm'))) return;
    try {
      const res = await api(`/api/songs/${songId}/notes/reextract`, {
        method: 'POST', body: { stem: detail.picked_stem },
      });
      notes = res.notes.map((n, i) => ({
        id: n.id ?? i,
        pitch: n.pitch,
        start: n.start,
        end: n.end,
        confidence: n.confidence ?? 1.0,
      }));
      nextId = (notes.reduce((m, n) => Math.max(m, n.id), -1) + 1) || notes.length;
      state.selected.clear();
      state.dirty = false;
      draw();
      toast(t('editor_toast_reextracted'), 'success', 1800);
    } catch (err) {
      toast(t('editor_err_reextract', { msg: err.message }), 'error');
    }
  });

  // ---------- playhead sync ----------

  syncPlayhead(audio, () => {
    state.cursor = audio.currentTime;
    timeEl.textContent = `${audio.currentTime.toFixed(2)} / ${(audio.duration || state.duration).toFixed(2)} s`;
    drawOverlayOnly();
  });

  // ---------- resize observer ----------

  const ro = new ResizeObserver(resize);
  ro.observe(rollEl);
  resize();

  // Save before leaving
  window.addEventListener('beforeunload', () => { if (state.dirty) save(); });
}
