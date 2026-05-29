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
    navigator.vibrate(durationMs || 18);
  }

  function matchesInteractiveTarget(target) {
    if (!target || typeof target.closest !== 'function') {
      return false;
    }

    var clickableSelector = [
      'button',
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

  document.addEventListener('pointerup', function (event) {
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
