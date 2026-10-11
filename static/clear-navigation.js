(function () {
  'use strict';
  if (!document.body.classList.contains('clear-ui')) return;
  const storageKey = 'clear-view-v1';
  const safeStore = {
    get() { try { return JSON.parse(sessionStorage.getItem(storageKey) || '{}'); } catch (_) { return {}; } },
    set(value) { try { sessionStorage.setItem(storageKey, JSON.stringify(value)); } catch (_) {} }
  };
  function pageKey(value) {
    const url = new URL(value, location.href);
    url.hash = '';
    url.searchParams.sort();
    return url.pathname + url.search;
  }
  const currentKey = pageKey(location.href);
  const isList = /^\/(expenses|reports|budget)$/.test(location.pathname);
  const arriving = safeStore.get().pending;
  if (isList && arriving?.key === currentKey && Number.isFinite(arriving.view?.y) && Date.now() - arriving.view.at < 30 * 60 * 1000) {
    document.documentElement.classList.add('clear-restoring');
  }
  let sourceView = null;
  function snapshot() {
    const controls = document.querySelector('.reports-filters-section');
    const edge = controls?.classList.contains('filters-docked') ? controls.getBoundingClientRect().bottom + 12 : 12;
    const anchors = Array.from(document.querySelectorAll('main [id]')).filter(el =>
      !el.closest('.reports-filters-section, [role="dialog"], .modal, .drawer') &&
      el.getClientRects().length && /^(exp-|ledger-|category-breakdown|payment-breakdown|all-report-expenses|income-section|budget-section|savings-goal|budget-balance)/.test(el.id));
    const anchor = anchors.find(el => el.getBoundingClientRect().top >= edge && el.getBoundingClientRect().top < innerHeight - 90);
    return { y: scrollY, anchor: anchor?.id, offset: anchor?.getBoundingClientRect().top, at: Date.now() };
  }
  function remember(destination, view) {
    if (!isList) return;
    const state = safeStore.get();
    state.views = { [currentKey]: view || snapshot() };
    state.pending = { key: pageKey(destination), view: view || state.views[currentKey] };
    safeStore.set(state);
  }
  function filterURL(form) {
    const url = new URL(form.action, location.href);
    url.search = new URLSearchParams(new FormData(form)).toString();
    return url;
  }
  window.ClearNavigation = {
    submitFilters(form) { const url = filterURL(form); remember(url); location.assign(url.href); }
  };
  document.addEventListener('pointerdown', event => {
    if (isList && event.target.closest('.table-action-btn')) sourceView = snapshot();
  }, true);
  document.addEventListener('click', event => {
    if (isList && event.target.closest('.table-action-btn')) sourceView = snapshot();
    const link = event.target.closest('a[href]');
    if (!link || !isList || event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || link.target) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin) return;
    if (/^\/edit\//.test(url.pathname)) {
      const modalOrigin = link.closest('.expense-modal');
      remember(url.searchParams.get('return_to') || location.href, (modalOrigin && sourceView) || snapshot());
    } else if (url.pathname === location.pathname && !url.hash) {
      remember(url);
    }
  }, true);
  document.addEventListener('submit', event => {
    const form = event.target;
    if (!isList) return;
    if (form.method.toLowerCase() === 'get') remember(filterURL(form));
    else remember(location.href);
  }, true);
  addEventListener('pagehide', () => {
    if (!isList) return;
    const state = safeStore.get();
    state.views = { [currentKey]: snapshot() };
    safeStore.set(state);
  });

  // Keep the fixed navigation outside headers and their containing blocks.
  const tabs = document.querySelector('.main-tabs');
  if (tabs) document.body.appendChild(tabs);
  const filters = document.querySelector('.reports-filters-section');
  let updateDock = () => {};
  if (filters) {
    const spacer = document.createElement('div');
    spacer.className = 'filters-placeholder';
    filters.before(spacer);
    let height = filters.getBoundingClientRect().height;
    updateDock = () => {
      const docked = spacer.getBoundingClientRect().top < 0;
      // Measure the full controls after undocking, never their compact height.
      if (!docked) {
        filters.classList.remove('filters-docked');
        height = filters.getBoundingClientRect().height;
      }
      spacer.style.height = docked ? height + 'px' : '0px';
      filters.classList.toggle('filters-docked', docked);
      if (docked) {
        const bounds = spacer.getBoundingClientRect();
        filters.style.setProperty('--dock-left', bounds.left + 'px');
        filters.style.setProperty('--dock-width', bounds.width + 'px');
      }
    };
    let queued = false;
    addEventListener('scroll', () => {
      if (!queued) requestAnimationFrame(() => { queued = false; updateDock(); });
      queued = true;
    }, { passive: true });
    addEventListener('resize', () => {
      const wasDocked = filters.classList.contains('filters-docked');
      if (wasDocked) {
        filters.classList.remove('filters-docked');
        height = filters.getBoundingClientRect().height;
        filters.classList.add('filters-docked');
      }
      updateDock();
    });
  }

  const scroller = document.getElementById('timeline-scroller');
  if (scroller) {
    const monthInput = document.querySelector('.month-select');
    const parts = monthInput.value.split('-').map(Number);
    const labels = ['ינואר','פברואר','מרץ','אפריל','מאי','יוני','יולי','אוגוסט','ספטמבר','אוקטובר','נובמבר','דצמבר'];
    scroller.setAttribute('aria-label', 'בחירת חודש בגלילה');
    scroller.setAttribute('role', 'group');
    for (let i = -12; i <= 12; i++) {
      const date = new Date(parts[0], parts[1] - 1 + i, 1);
      const value = date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'timeline-month-btn' + (i === 0 ? ' active' : '');
      button.dataset.month = value;
      const face = document.createElement('span');
      face.className = 'month-wheel-face';
      face.textContent = labels[date.getMonth()] + ' ' + date.getFullYear();
      button.appendChild(face);
      if (i === 0) button.setAttribute('aria-current', 'date');
      button.addEventListener('click', () => {
        monthInput.value = value;
        window.ClearNavigation.submitFilters(monthInput.form);
      });
      scroller.appendChild(button);
    }
    const buttons = Array.from(scroller.children);
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    function paintWheel() {
      const bounds = scroller.getBoundingClientRect();
      const center = bounds.left + bounds.width / 2;
      buttons.forEach(button => {
        const buttonCenter = bounds.left + button.offsetLeft - scroller.scrollLeft + button.offsetWidth / 2;
        const distance = Math.max(-1, Math.min(1, (buttonCenter - center) / (bounds.width / 2)));
        button.style.setProperty('--wheel-angle', reduced ? '0deg' : distance * -42 + 'deg');
        button.style.setProperty('--wheel-depth', reduced ? '0px' : -Math.abs(distance) * 28 + 'px');
        button.style.setProperty('--wheel-scale', 1 - Math.abs(distance) * 0.12);
      });
    }
    // Offset geometry avoids RTL scrollLeft sign assumptions and transformed bounds.
    function centerButton(button, behavior) {
      const delta = button.offsetLeft + button.offsetWidth / 2 - (scroller.scrollLeft + scroller.clientWidth / 2);
      scroller.scrollBy({ left: delta, behavior });
    }
    requestAnimationFrame(() => { centerButton(scroller.querySelector('.active'), 'instant'); paintWheel(); });
    let paintQueued = false;
    scroller.addEventListener('scroll', () => {
      if (!paintQueued) requestAnimationFrame(() => { paintQueued = false; paintWheel(); });
      paintQueued = true;
    }, { passive: true });
    addEventListener('resize', paintWheel);
    let drag = null, suppressClick = false;
    scroller.addEventListener('pointerdown', event => {
      // A new gesture must never inherit the preceding mouse drag's click guard.
      suppressClick = false;
      if (event.pointerType !== 'mouse' || event.button !== 0) return;
      drag = { x: event.clientX, scroll: scroller.scrollLeft, moved: false };
      suppressClick = false;
    });
    addEventListener('pointermove', event => {
      if (!drag) return;
      const distance = event.clientX - drag.x;
      if (Math.abs(distance) > 5) { drag.moved = true; scroller.classList.add('wheel-dragging'); }
      if (drag.moved) { event.preventDefault(); scroller.scrollLeft = drag.scroll - distance; }
    });
    addEventListener('pointerup', () => {
      if (!drag) return;
      suppressClick = drag.moved;
      drag = null;
      scroller.classList.remove('wheel-dragging');
    });
    addEventListener('pointercancel', () => { drag = null; suppressClick = false; scroller.classList.remove('wheel-dragging'); });
    scroller.addEventListener('click', event => {
      if (suppressClick) { event.preventDefault(); event.stopImmediatePropagation(); suppressClick = false; }
    }, true);
    scroller.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      const index = buttons.indexOf(document.activeElement);
      const target = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : index + (event.key === 'ArrowLeft' ? 1 : -1);
      const button = buttons[Math.max(0, Math.min(buttons.length - 1, target))];
      event.preventDefault();
      button.focus({ preventScroll: true });
      centerButton(button, reduced ? 'instant' : 'smooth');
    });
  }

  function restoreView(event) {
    if (!isList) return;
    const state = safeStore.get();
    const pending = state.pending?.key === currentKey ? state.pending.view : null;
    const back = event?.persisted || performance.getEntriesByType('navigation')[0]?.type === 'back_forward';
    const view = pending || (back && state.views?.[currentKey]);
    if (!view || Date.now() - view.at > 30 * 60 * 1000 || !Number.isFinite(view.y)) {
      document.documentElement.classList.remove('clear-restoring'); updateDock(); return;
    }
    if (pending) { delete state.pending; safeStore.set(state); }
    document.documentElement.classList.add('clear-restoring');
    const restore = () => {
      scrollTo({ top: view.y, behavior: 'instant' });
      updateDock();
      const anchor = view.anchor && document.getElementById(view.anchor);
      if (anchor && Number.isFinite(view.offset)) {
        scrollTo({ top: scrollY + anchor.getBoundingClientRect().top - view.offset, behavior: 'instant' });
        updateDock();
      }
      document.documentElement.classList.remove('clear-restoring');
    };
    requestAnimationFrame(() => requestAnimationFrame(restore));
  }
  if (document.readyState === 'complete') restoreView();
  else addEventListener('load', restoreView, { once: true });
  addEventListener('pageshow', event => { if (event.persisted) restoreView(event); });
})();
