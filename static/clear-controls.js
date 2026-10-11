/* White option sheets retain the native fields and existing form contracts. */
(() => {
  'use strict';
  if (!document.body.classList.contains('clear-ui')) return;
  let activeSheet = null;
  function sheet(title, description, options) {
    if (activeSheet) activeSheet.close();
    const opener = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    const overlay = document.createElement('div');
    overlay.className = 'clear-control-overlay';
    const panel = document.createElement('section');
    panel.className = 'clear-control-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-labelledby', 'clear-control-title');
    const heading = document.createElement('h2');
    heading.id = 'clear-control-title';
    heading.textContent = title;
    const info = document.createElement('p');
    info.textContent = description;
    const choices = document.createElement('div');
    choices.className = 'clear-control-choices' + (title === 'קטגוריה' ? ' clear-category-choices' : '');
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'clear-control-cancel';
    cancel.textContent = 'חזרה';
    function close() {
      document.removeEventListener('keydown', keyboard, true);
      overlay.remove();
      document.body.style.overflow = previousOverflow;
      activeSheet = null;
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    }
    function keyboard(event) {
      if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); close(); }
      if (event.key === 'Tab') {
        const buttons = Array.from(panel.querySelectorAll('button:not(:disabled)'));
        const first = buttons[0], last = buttons[buttons.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        event.stopImmediatePropagation();
      }
    }
    options.forEach(option => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'clear-control-option' + (option.danger ? ' danger' : '');
      button.textContent = option.label;
      button.disabled = !!option.disabled;
      if (option.selected !== undefined) button.setAttribute('aria-pressed', String(option.selected));
      button.addEventListener('click', () => { close(); option.action(); });
      choices.appendChild(button);
    });
    cancel.addEventListener('click', close);
    overlay.addEventListener('click', event => { if (event.target === overlay) close(); });
    panel.append(heading, info, choices, cancel);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', keyboard, true);
    activeSheet = { close };
    (choices.querySelector('button:not(:disabled)') || cancel).focus({ preventScroll: true });
    return close;
  }
  const labels = { category: 'קטגוריה', category_filter: 'קטגוריה', payment_method: 'אמצעי תשלום', payment_filter: 'אמצעי תשלום', expense_type: 'סוג הוצאה' };
  document.querySelectorAll('select').forEach(select => {
    if (!labels[select.name] || select.multiple) return;
    const holder = document.createElement('span');
    holder.className = 'clear-select-holder';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = select.className + ' clear-select-button';
    button.setAttribute('aria-haspopup', 'dialog');
    const label = select.getAttribute('aria-label') || labels[select.name];
    function sync() {
      button.textContent = select.selectedOptions[0]?.textContent || label;
      button.setAttribute('aria-label', label + ': ' + button.textContent);
      button.setAttribute('aria-invalid', 'false');
    }
    select.before(holder);
    holder.append(select, button);
    select.classList.add('clear-native-select');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    select.addEventListener('change', sync);
    select.addEventListener('invalid', event => {
      event.preventDefault();
      button.setAttribute('aria-invalid', 'true');
      button.focus({ preventScroll: true });
    });
    button.addEventListener('click', event => {
      event.preventDefault();
      sheet(label, 'בחרו אפשרות', Array.from(select.options).map(option => ({
        label: option.textContent, disabled: option.disabled, selected: option.selected,
        action: () => {
          select.value = option.value;
          select.dispatchEvent(new Event('input', { bubbles: true }));
          select.dispatchEvent(new Event('change', { bubbles: true }));
        }
      })));
    });
    sync();
  });
  window.ClearRecurringActions = {
    choose({ month, update, stop }) {
      if (!/^\d{4}-\d{2}$/.test(month || '')) return;
      sheet('שינוי בהוצאה קבועה', 'הפעולה תחול מחודש ' + month + '. ההוצאות בחודשים הקודמים יישמרו.', [
        { label: 'עדכון סכום ופרטים מחודש זה', action: update },
        { label: 'הפסקה מלאה מחודש זה', danger: true, action: () => {
          sheet('אישור הפסקה', 'ההוצאה תופסק מחודש ' + month + ', כולל ביטול שינויים עתידיים שנקבעו. העבר יישמר.', [
            { label: 'אישור הפסקה מחודש ' + month, danger: true, action: stop }
          ]);
        } }
      ]);
    }
  };
  const manage = document.getElementById('manage-recurring');
  const amount = document.getElementById('amount');
  if (manage) manage.addEventListener('click', () => {
    const monthField = document.getElementById('effective-month');
    if (!monthField.reportValidity()) return;
    window.ClearRecurringActions.choose({
      month: monthField.value,
      update: () => { amount.focus({ preventScroll: true }); amount.select(); },
      stop: () => document.getElementById('expense-form').requestSubmit(document.getElementById('stop-recurring-submit'))
    });
  });
  if (amount && location.pathname.startsWith('/edit/')) {
    requestAnimationFrame(() => { amount.focus({ preventScroll: true }); amount.select(); });
  }
})();
