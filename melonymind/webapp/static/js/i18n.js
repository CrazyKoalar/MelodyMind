/**
 * Lightweight UI locale (English / 简体中文). Persists in localStorage.
 */

const STORAGE_KEY = 'melonymind_locale';

/** @type {Set<(loc: string) => void>} */
const listeners = new Set();

/** @returns {'en' | 'zh'} */
export function getLocale() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw === 'zh' ? 'zh' : 'en';
  } catch (_) {
    return 'en';
  }
}

/** @param {'en' | 'zh'} loc */
export function setLocale(loc) {
  const next = loc === 'zh' ? 'zh' : 'en';
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch (_) { /* ignore */ }
  document.documentElement.lang = next === 'zh' ? 'zh-CN' : 'en';
  listeners.forEach((fn) => {
    try {
      fn(next);
    } catch (_) { /* ignore */ }
  });
}

/** @param {(loc: string) => void} fn */
export function subscribeLocale(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/**
 * @param {string} key
 * @param {Record<string, string | number>} [vars]
 */
export function t(key, vars = {}) {
  const loc = getLocale();
  let s = STRINGS[loc]?.[key] ?? STRINGS.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) {
    s = s.split(`{${k}}`).join(String(v));
  }
  return s;
}

/** Apply data-i18n / data-i18n-title / data-i18n-placeholder under root. */
export function applyDataI18n(root) {
  if (!root || !root.querySelectorAll) return;
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.getAttribute('data-i18n');
    if (key) el.textContent = t(key);
  });
  root.querySelectorAll('[data-i18n-title]').forEach((el) => {
    const key = el.getAttribute('data-i18n-title');
    if (key) el.title = t(key);
  });
  root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (key) el.placeholder = t(key);
  });
}

export function syncDocumentTitle() {
  document.title = t('doc_title');
}

export function updateLangSwitcher() {
  const loc = getLocale();
  const en = document.getElementById('lang-en');
  const zh = document.getElementById('lang-zh');
  if (en) {
    en.classList.toggle('lang-btn--active', loc === 'en');
    en.setAttribute('aria-pressed', loc === 'en' ? 'true' : 'false');
  }
  if (zh) {
    zh.classList.toggle('lang-btn--active', loc === 'zh');
    zh.setAttribute('aria-pressed', loc === 'zh' ? 'true' : 'false');
  }
}

const STRINGS = {
  en: {
    doc_title: 'MelodyMind Annotation',
    app_title: 'MelodyMind Annotation',
    nav_songs: 'Songs',
    export_manifest: 'Export manifest',
    export_manifest_title: 'Export training manifest from confirmed songs',
    lang_label: 'Language',
    lang_en: 'EN',
    lang_zh: '中文',

    list_upload_label: 'Upload audio',
    list_upload_hint: 'WAV, MP3, FLAC, OGG, M4A — saved to dataset/uploads',
    list_auto_compute: 'Run recognition after upload (stems + pitch, may take 30–60s)',
    list_filter_ph: 'Filter by filename…',
    list_col_file: 'File',
    list_col_status: 'Status',
    list_col_stem: 'Picked stem',
    list_col_duration: 'Duration',
    list_col_action: '',
    list_open: 'Open →',
    list_counts: '{shown} shown · {confirmed} confirmed / {total} total',
    list_uploading: 'Uploading…',

    status_new: 'new',
    status_opened: 'opened',
    status_stem_picked: 'stem_picked',
    status_notes_edited: 'notes_edited',
    status_confirmed: 'confirmed',

    err_list_songs: 'Could not list songs: {msg}',
    err_upload: 'Upload failed: {msg}',
    toast_upload_analyzed: 'Uploaded and analyzed. Opening stem picker…',
    toast_upload_open: 'Uploaded. Opening stem picker…',
    err_load_song: 'Failed to load song: {msg}',
    nav_stem_picker: 'stem picker',
    nav_sheet_music: 'sheet music',
    nav_admin_editor: 'admin: note editor',
    err_sheet_view: 'Failed to load sheet view: {msg}',
    err_editor: 'Failed to load editor: {msg}',

    stem_prepare: 'Prepare stems (first time, ~30s)',
    stem_prep_msg: 'Preparing stems… first run can take 30–60 s.',
    stem_prep_hint: 'Click prepare to extract stems.',
    stem_pick: 'Pick',
    stem_score: 'score {v}',
    stem_to_sheet: 'Continue to sheet music →',
    stem_confirm_export: 'Confirm for training export',
    stem_reopen: 'Reopen for editing',
    stem_admin_link: 'Refine pitch detection (admin) →',
    toast_picked: 'Picked: {stem}',
    err_pick: 'Pick failed: {msg}',
    stem_toast_cached: 'Loaded from cache.',
    stem_toast_prepared: 'Stems prepared.',
    stem_toast_suggested: '{note} Suggested: {stem}',
    err_prepare: 'Prepare failed: {msg}',
    toast_confirmed: 'Confirmed.',
    err_confirm: 'Confirm failed: {msg}',
    err_reopen: 'Reopen failed: {msg}',

    sheet_gate_title: 'Pick a stem first',
    sheet_gate_body: 'Choose which separated track carries the melody you want notated.',
    sheet_gate_back: '← Back to stem choice',
    sheet_stem: 'Melody track: {stem}',
    sheet_lead:
      'Open a browser preview or download LilyPond source. Notation uses the notes detected on the stem you picked (same as the training pipeline’s pitch step). Set BPM to match the song so note lengths map sensibly.',
    sheet_tempo_label: 'Tempo (BPM)',
    sheet_preview: 'Open sheet preview (new tab)',
    sheet_dl_ly: 'Download .ly',
    sheet_back_stem: '← Change stem',
    sheet_admin: 'Refine detection (admin) →',
    toast_dl_ly: 'Downloaded .ly file.',
    err_dl: 'Download failed: {msg}',

    editor_admin_html:
      'Admin: manual correction of automatic pitch detection. End users use <a href="#" id="ne-back-sheet">sheet music</a> instead.',
    editor_gate_title: 'No stem picked',
    editor_gate_line1: 'Pick a stem first.',
    editor_gate_stem: '← stem picker',
    editor_gate_sheet: 'sheet music',
    editor_play: '▶ Play',
    editor_stop: '■ Stop',
    editor_save: 'Save now',
    editor_save_title: 'Force save',
    editor_reextract: 'Re-extract',
    editor_reextract_title: 'Re-run pYIN on this stem',
    editor_sheet_ly: 'Download .ly',
    editor_sheet_ly_title: 'Download LilyPond source',
    editor_sheet_preview: 'Sheet preview',
    editor_sheet_preview_title: 'Open VexFlow preview in a new tab',
    editor_hint:
      'Click empty cell to add a note · drag note body to move · drag edges to resize · Delete to remove selected · ctrl+wheel = zoom time · shift+wheel = zoom pitch · middle-drag = pan · Alt disables time snap · click time ruler to seek · Space to play',
    editor_status_unsaved: 'unsaved…',
    editor_status_saving: 'saving…',
    editor_status_saved: 'saved.',
    editor_reextract_confirm: 'You have unsaved edits. Discard and re-extract?',
    editor_toast_sheet_ok: 'Downloaded .ly file.',
    editor_err_sheet: 'Sheet export failed: {msg}',
    editor_err_preview: 'Preview failed: {msg}',
    editor_toast_reextracted: 'Re-extracted notes.',
    editor_err_reextract: 'Re-extract failed: {msg}',
    editor_err_save: 'Save failed: {msg}',

    export_body:
      'Exported {count} song(s).\nManifest: {melody}\nNotes:    {notes}\nReview:   {review}',
    export_reveal: 'Reveal in Explorer',
    err_export: 'Export failed: {msg}',
    err_reveal: 'Reveal failed: {msg}',
  },
  zh: {
    doc_title: 'MelodyMind 标注',
    app_title: 'MelodyMind 标注',
    nav_songs: '曲目',
    export_manifest: '导出清单',
    export_manifest_title: '导出已确认曲目的训练用清单',
    lang_label: '语言',
    lang_en: 'EN',
    lang_zh: '中文',

    list_upload_label: '上传音频',
    list_upload_hint: '支持 WAV、MP3、FLAC、OGG、M4A — 保存至 dataset/uploads',
    list_auto_compute: '上传后自动识别（分轨 + 音高，约 30–60 秒）',
    list_filter_ph: '按文件名筛选…',
    list_col_file: '文件',
    list_col_status: '状态',
    list_col_stem: '所选分轨',
    list_col_duration: '时长',
    list_col_action: '',
    list_open: '打开 →',
    list_counts: '显示 {shown} 条 · 已确认 {confirmed} / 共 {total} 条',
    list_uploading: '正在上传…',

    status_new: '新建',
    status_opened: '已打开',
    status_stem_picked: '已选分轨',
    status_notes_edited: '已改音符',
    status_confirmed: '已确认',

    err_list_songs: '无法加载曲目列表：{msg}',
    err_upload: '上传失败：{msg}',
    toast_upload_analyzed: '已上传并完成分析，正在打开分轨选择…',
    toast_upload_open: '已上传，正在打开分轨选择…',
    err_load_song: '加载曲目失败：{msg}',
    nav_stem_picker: '分轨选择',
    nav_sheet_music: '谱面',
    nav_admin_editor: '管理员：音符编辑',
    err_sheet_view: '加载谱面页失败：{msg}',
    err_editor: '加载编辑器失败：{msg}',

    stem_prepare: '准备分轨（首次约 30 秒）',
    stem_prep_msg: '正在准备分轨… 首次运行可能需要 30–60 秒。',
    stem_prep_hint: '请点击「准备分轨」进行分离。',
    stem_pick: '选择',
    stem_score: '分数 {v}',
    stem_to_sheet: '继续生成谱面 →',
    stem_confirm_export: '确认并加入训练导出',
    stem_reopen: '重新打开编辑',
    stem_admin_link: '精调音高识别（管理员）→',
    toast_picked: '已选择：{stem}',
    err_pick: '选择失败：{msg}',
    stem_toast_cached: '已从缓存加载。',
    stem_toast_prepared: '分轨已准备好。',
    stem_toast_suggested: '{note} 建议：{stem}',
    err_prepare: '准备分轨失败：{msg}',
    toast_confirmed: '已确认。',
    err_confirm: '确认失败：{msg}',
    err_reopen: '重新打开失败：{msg}',

    sheet_gate_title: '请先选择分轨',
    sheet_gate_body: '请选择哪条分离音轨作为要记谱的旋律。',
    sheet_gate_back: '← 返回分轨选择',
    sheet_stem: '旋律轨道：{stem}',
    sheet_lead:
      '可在浏览器中预览谱面，或下载 LilyPond（.ly）源文件。记谱使用当前所选分轨上检测到的音符（与训练管线中的音高步骤一致）。请将 BPM 设为接近歌曲速度，以便时值映射更合理。',
    sheet_tempo_label: '速度（BPM）',
    sheet_preview: '在新标签页打开谱面预览',
    sheet_dl_ly: '下载 .ly',
    sheet_back_stem: '← 更换分轨',
    sheet_admin: '精调识别（管理员）→',
    toast_dl_ly: '已下载 .ly 文件。',
    err_dl: '下载失败：{msg}',

    editor_admin_html:
      '管理员：手动修正自动音高识别结果。普通用户请使用<a href="#" id="ne-back-sheet">谱面</a>流程。',
    editor_gate_title: '尚未选择分轨',
    editor_gate_line1: '请先在分轨页选择一条轨道。',
    editor_gate_stem: '← 分轨选择',
    editor_gate_sheet: '谱面',
    editor_play: '▶ 播放',
    editor_stop: '■ 停止',
    editor_save: '立即保存',
    editor_save_title: '强制保存',
    editor_reextract: '重新提取',
    editor_reextract_title: '对此分轨重新运行 pYIN',
    editor_sheet_ly: '下载 .ly',
    editor_sheet_ly_title: '下载 LilyPond 源文件',
    editor_sheet_preview: '谱面预览',
    editor_sheet_preview_title: '在新标签页打开 VexFlow 预览',
    editor_hint:
      '在空白格点击添加音符 · 拖音符主体移动 · 拖边缘改时值 · Delete 删除选中 · Ctrl+滚轮缩放时间 · Shift+滚轮缩放音高 · 中键拖动平移 · Alt 关闭时间吸附 · 点时间标尺跳转 · 空格播放',
    editor_status_unsaved: '未保存…',
    editor_status_saving: '正在保存…',
    editor_status_saved: '已保存。',
    editor_reextract_confirm: '有未保存修改，确定放弃并重新提取？',
    editor_toast_sheet_ok: '已下载 .ly 文件。',
    editor_err_sheet: '导出谱面失败：{msg}',
    editor_err_preview: '预览失败：{msg}',
    editor_toast_reextracted: '已重新提取音符。',
    editor_err_reextract: '重新提取失败：{msg}',
    editor_err_save: '保存失败：{msg}',

    export_body:
      '已导出 {count} 首曲目。\n清单：{melody}\n音符：{notes}\n审阅：{review}',
    export_reveal: '在资源管理器中显示',
    err_export: '导出失败：{msg}',
    err_reveal: '打开文件夹失败：{msg}',
  },
};

const STATUS_KEYS = {
  new: 'status_new',
  opened: 'status_opened',
  stem_picked: 'status_stem_picked',
  notes_edited: 'status_notes_edited',
  confirmed: 'status_confirmed',
};

/** Localized label for API song status. */
export function tStatus(status) {
  const k = STATUS_KEYS[status];
  return k ? t(k) : String(status);
}

export function initI18nShell() {
  document.documentElement.lang = getLocale() === 'zh' ? 'zh-CN' : 'en';
  syncDocumentTitle();
  updateLangSwitcher();
  applyDataI18n(document);
  const en = document.getElementById('lang-en');
  const zh = document.getElementById('lang-zh');
  if (en) en.addEventListener('click', () => setLocale('en'));
  if (zh) zh.addEventListener('click', () => setLocale('zh'));
}
