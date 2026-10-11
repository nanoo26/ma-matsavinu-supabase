(function () {
  // Haptic feedback is available only on some mobile devices/browsers.
  if (!('vibrate' in navigator) || typeof navigator.vibrate !== 'function') {
    return;
  }

  var lastVibrationAt = 0;
  var MIN_INTERVAL_MS = 60;

  function shouldVibrateNow() {
    var now = Date.now();
    if (now - lastVibrationAt < MIN_INTERVAL_MS) {
      return false;
    }
    lastVibrationAt = now;
    return true;
  }

  function triggerHaptic(durationMs) {
    if (!shouldVibrateNow()) {
      return;
    }
    try { navigator.vibrate(durationMs || 18); } catch (_) { /* Unsupported or restricted device. */ }
  }

  function matchesInteractiveTarget(target) {
    if (!target || typeof target.closest !== 'function') {
      return false;
    }

    var clickableSelector = [
      'button',
      'a[href]',
      'select',
      'input[type="checkbox"]',
      'input[type="radio"]',
      'input[type="button"]',
      'input[type="submit"]',
      'input[type="reset"]',
      '[role="button"]',
      '.btn',
      '.btn-primary',
      '.btn-main',
      '.btn-submit',
      '.btn-ghost',
      '.btn-danger',
      '.btn-expense-edit',
      '.btn-expense-delete',
      '.table-action-btn',
      '.month-arrow-btn',
      '.timeline-month-btn',
      '.main-tab',
      '.fab-add',
      '.back-button',
      '.category-btn',
      '.payment-card',
      '.selected-display'
    ].join(',');

    var matchedElement = target.closest(clickableSelector);
    if (!matchedElement) {
      return false;
    }

    if (matchedElement.matches('[disabled], [aria-disabled="true"], [data-no-haptic="true"]')) {
      return false;
    }

    return true;
  }

  var pointerStart = null;
  document.addEventListener('pointerdown', function (event) {
    pointerStart = { x: event.clientX, y: event.clientY };
  }, true);
  document.addEventListener('pointercancel', function () { pointerStart = null; }, true);
  document.addEventListener('pointerup', function (event) {
    var start = pointerStart;
    pointerStart = null;
    if (!start || Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) return;
    if (!matchesInteractiveTarget(event.target)) {
      return;
    }
    triggerHaptic(18);
  }, true);

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
    if (!matchesInteractiveTarget(event.target)) {
      return;
    }
    triggerHaptic(14);
  }, true);
})();
