// Audio playback ↔ canvas sync via requestAnimationFrame.

export function syncPlayhead(audio, tick) {
  let rafId = null;
  let running = false;

  function loop() {
    if (!running) return;
    tick();
    rafId = requestAnimationFrame(loop);
  }

  function start() {
    if (running) return;
    running = true;
    loop();
  }

  function stop() {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    // Final tick so the playhead lands exactly on pause/end position
    tick();
  }

  audio.addEventListener('play', start);
  audio.addEventListener('pause', stop);
  audio.addEventListener('ended', stop);
  audio.addEventListener('seeked', tick);
  audio.addEventListener('loadedmetadata', tick);

  // Initial paint
  tick();

  return { stop };
}
