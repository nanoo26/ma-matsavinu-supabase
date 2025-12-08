# Ma Matsavinu - Design System

Short reference to help request and implement design changes without
hunting through the entire CSS.

Main UI file: `static/style.css`  
The whole UI is built around stable CSS classes.

---

## 1. Foundation (tokens and global styles)

**Where in CSS:**  
`:root`, `body`, `.app-shell`

**What lives here:**

- Brand colors:
  - `--primary-blue`, `--primary-green`, `--primary-purple`
  - `--secondary-cyan`, `--accent-emerald`
- Backgrounds:
  - `--bg-main`, `--bg-card`, `--bg-light`
- Text colors:
  - `--text-primary`, `--text-secondary`, `--text-muted`

**Mobile first:**

- Design is optimized for max width of about 480px.
- Font sizes usually between 13px and 17px.
- No separate desktop design. Desktop just shows the same mobile layout centered.

If I say:  
"Make the whole app more purple" - it usually means changing these tokens.

---

## 2. Header

**Classes:**

- `.app-header`
- `.app-title`
- `.app-subtitle`

**Use:**  
Top gradient block with app name and subtitle.

Changes here affect the general "hero" look of the app.

---

## 3. Top navigation (main tabs: Budget / Reports / Expenses)

**Classes:**

- `.main-tabs` - container with 3 tabs.
- `.main-tab` - tab button.
- `.main-tab.active` - active tab styling.

There are also more detailed nav pieces:

- `.nav-menu`, `.top-tabs` - older tab containers.
- `.nav-item`, `.top-tab` - individual items.
- Month navigation:
  - `.month-arrow-btn`
  - `.reports-filters-section`
  - `.modern-select`

If I say:  
"Make the main navigation buttons larger or bolder" - touch these.

---

## 4. Floating add button (plus button at bottom)

**Classes:**

- `.fab-add`
- `.fab-tooltip`

**Current behavior:**

- Circular button in the center bottom.
- Gradient green background.
- Bouncy appear animation (`fabBounceIn`).

You can:

- Change size.
- Adjust distance from bottom.
- Soften the animation.
- Change the background gradient (using existing color variables).

---

## 5. Buttons

**Main button styles:**

- `.btn-primary`, `.btn-main`, `.btn-submit` - primary actions.
- `.btn-ghost` - white button with border.
- `.btn-danger`, `.btn-danger-small` - delete and dangerous actions.
- `.btn-expense-edit`, `.btn-expense-delete` - inline buttons near expenses.
- `.modern-filter-btn` - big filter button in reports.
- `.table-action-btn` - action button in tables.

Typical properties:

- Padding: around 10 to 14px.
- Font size: 14 to 16px.
- Rounded corners.

If I say:  
"Make all green buttons softer and less aggressive" - this is the group.

---

## 6. Expense cards (main expenses list)

**Key classes:**

- Container: `.expense-list`
- Row: `.expense-item`

Inside each row:

- Top line:
  - `.expense-row`
  - Date: `.exp-date`
  - Amount: `.exp-amount`
- Meta line:
  - `.exp-meta` (category, payment method, etc)
- Tags:
  - `.expense-tags`, `.expense-tag`, `.tag-primary`, `.tag-secondary`
- Notes:
  - `.expense-note-row`, `.note-bubble`, `.note-text`, `.note-ltr`
- Actions:
  - `.exp-actions`, `.btn-expense-edit`, `.btn-expense-delete`

Typical design changes here:

- Reduce or increase spacing between rows.
- Change font size of the amount.
- Highlight fixed expenses in a different way.
- Add small icons next to categories or payment methods.

---

## 7. Forms (add / edit expense)

**Classes:**

- `.form-box`, `.form-card` and the `form` element itself.
- `.form-group` - a single field block.
- Inputs:
  - `input[type="text"]`, `input[type="number"]`, `select`, `textarea`
- Submit button:
  - `button[type="submit"]`, `.btn-primary`
- Installments panel:
  - `#installments-panel`, `.installments-panel`,
    `.installments-header`, `.installments-title`, `.installments-chip`

Typical changes:

- Card background, border and shadow for the form.
- Spacing between fields.
- Making labels clearer and more readable.

---

## 8. Battery graph (budget vs "spending freedom")

**Classes:**

- `.battery-meter` - whole widget.
- `.battery-label` - text above.
- `.battery-bar` - outline of battery.
- `.battery-fill` - inside fill, with variants:
  - `.battery-fill.low`
  - `.battery-fill.mid`
  - `.battery-fill.high`
- `.battery-percent` - text inside the bar.

If I say:  
"The battery is too big / too small / needs more red when we overspend" - it is here.

---

## 9. Charts and reports visuals

**Bar charts:**

- `.chart-container`
- `.chart-title`
- `.chart-bar-row`
- `.chart-label`
- `.chart-bar-wrapper`
- `.chart-bar` with variants:
  - `.positive`
  - `.negative`
  - `.warning`

**Donut chart:**

- `.donut-chart`
- `.donut-visual`
- `.donut-legend`
- `.legend-item`
- `.legend-color` with variants:
  - `.blue`, `.green`, `.purple`, `.cyan`

**Progress indicators:**

- `.progress-indicator`
- `.progress-bar-bg`
- `.progress-bar-fill` with variants:
  - `.success`
  - `.warning`
  - `.danger`

---

## 10. Tables

### Expenses table

**Classes:**

- `.expenses-table-only`
- `.expenses-table-only th`
- `.expenses-table-only td`
- `.row-fixed` - row for fixed expenses.
- `.col-notes` - description column.

Column layout usually:

1. Checkbox
2. Date
3. Description and notes
4. Amount
5. Actions

### Reports table

**Classes:**

- `.reports-table-only`
- `.category-table`
- `.cat-cell`
- `.cat-name`
- `.cat-percent-chip` with variants:
  - `.ok`, `.warn`, `.over`

---

## 11. Receipt style list ("supermarket receipt" view)

**Classes:**

- `.receipt-section`, `.receipt-title`, `.receipt-subtitle`
- `.receipt-card` - the white receipt container.
- `.receipt-list` - scrollable list of lines.
- `.receipt-row`, `.receipt-row-main`
- Left side (amount):
  - `.receipt-left`, `.receipt-amount`, `.receipt-currency`
- Right side (details):
  - `.receipt-right`, `.receipt-date`,
    `.receipt-meta`, `.receipt-notes`

You can adjust:

- Row spacing.
- Borders (dashed lines like a real receipt).
- Font sizes for the amount vs the description.

---

## 12. Messages, empty states and utilities

**Flash messages:**

- `.flash-message`
- `.flash-success`, `.flash-error`, `.flash-info`

Behavior:

- Fixed at top center.
- Show briefly with `flashSlideIn` and `flashSlideOut` animations.

**Empty state:**

- `.empty-state` - shown when there is no data.

**Warnings:**

- `.alert-error` - prominent error box.

**Animations:**

- `fadeIn`, `rotate`, `pulse`, `batteryFlow`,
  `fabBounceIn`, `flashSlideIn`, `flashSlideOut`.

---

## 13. Budget page

**Classes:**

- `.budget-grid` - layout for summary cards.
- `.budget-edit-table` - table for editing category budgets.
- `.budget-row` - row with 3 columns.
- `.budget-category` - category name.
- `.budget-prev` - previous month amount (read only).
- `.budget-current` - current budget input.
- `.prev-amount` - chip showing previous value.
- `.budget-input` - input styling.
- `.budget-row-total` - summary row.

In income area:

- `.budget-source`
- `.budget-amount`

---

## 14. Date range display

**Classes:**

- `.date-range-display`
- `.range-icon`
- `.range-text`

Use: shows "DD/MM/YYYY - DD/MM/YYYY" in the reports page,
under the month navigation.

---

## How to request changes

When asking for a visual change, specify:

- Which area:
  - "expenses list", "add expense form", "battery", "receipt", "budget table", etc.
- What type of change:
  - Size (bigger/smaller)
  - Color
  - Spacing
  - Borders or corner radius
  - Animation

This lets the assistant jump directly to the right block in `static/style.css`
and suggest focused edits instead of touching unrelated parts.
