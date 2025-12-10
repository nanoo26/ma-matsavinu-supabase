# 🧭 Claude Sonnet Prompt — Ma Matsavinu UI/UX Tasks
# ================================================
# ⚙️ Activate: Lyra Mode (design assistant)
# Goal: Improve mobile navigation and touch interaction
# Project: “מה מצבינו” – family expenses manager (Flask + Jinja2)
# Focus ONLY on UI/UX — no backend or DB changes.
# ================================================

## 📋 Project Rules
- RTL layout (Right-to-Left) is mandatory.
- Mobile-first (max width: 480px).
- Use only Vanilla CSS and JS (no libraries).
- Colors must come from :root variables in `style.css`.
- Edit ONLY files under `/templates/` and `/static/`.
- All outputs must be valid, complete HTML/CSS/JS.
- Keep same design language (cards, buttons, tabs, flash messages).
- Smooth, modern, readable interface.

---

## 🧩 Navigation Tasks

1. **Persistent Bottom Navigation Bar**
   - Make `.main-tabs` fixed at the bottom of the screen.
   - Include icons + text for navigation.
   - Rounded corners, high contrast, visible even when scrolling.

2. **Active Tab Highlight**
   - Add a short 0.2–0.3s animation for the active tab.
   - Use gradient (blue → purple) and soft shadow.

3. **Back Button (Top Right)**
   - Small “←” button fixed at top-right.
   - Soft grey by default, turns colorful on hover/touch.

4. **Interactive Timeline (Month Swipe)**
   - Enable touch gestures: swipe left/right to change months.
   - RTL-correct: swipe right = previous month.
   - Use clean JS only (no external libs).

---

## ✋ Touch Interaction Enhancements

1. **Swipe on Expense Row**
   - Swipe left on `.expense-item` → show “Delete” button.
   - Swipe right → show “Edit”.
   - Add smooth transform + shadow transition.

2. **Instant Visual Feedback**
   - Apply scale effect on button/card/tap (`:active`).
   - Animation ≤ 0.2s, soft shadow glow.

3. **Page Transition Animation**
   - Fade or slide animation when switching between pages.
   - Example: `.page-enter` and `.page-leave` classes in CSS.

4. **Context Preservation**
   - After edit/save, return to the same month and scroll position.
   - Use `sessionStorage` or URL hash (no Python logic changes).

5. **Soft Toast Notifications**
   - Improve `.flash-message`: appear bottom-center.
   - Add fade-in/out animation, rounded edges, shadow.

---

## 💡 Deliverables
- Return full updated HTML, CSS, and/or JS files (not partials).
- Explain briefly (≤5 lines) each improvement.
- All output should be ready for direct paste into project folders.

---

## 🧱 Objective
Create a modern, soft, accessible, touch-friendly mobile interface —  
enhancing **navigation clarity** and **interaction comfort**  
without changing any business logic or database structure.

# ================================================
# Reminder: Always keep RTL, mobile-first, and design consistency.
# ================================================
