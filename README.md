# Ma Matsavinu – Family Expense Tracking App (Hebrew, RTL)

A modern, mobile-first, right-to-left family expense tracking web app built with  
**Flask + Supabase**.  
Designed specifically for fast daily use on mobile, with clean UI, category budgets, reports, financial month logic, and installment tracking.

## Live App
https://ma-matsavinu.supabase.onrender.com/

---

## ✨ Key Features

### 📱 Mobile-First RTL Interface
- Hebrew UI, 100% RTL  
- Optimized for 360-480px phone screens  
- Smooth cards, gradients, and modern mobile navigation

### 💸 Expense Management
- Add, edit, delete expenses  
- Categories (מזון, בילויים, רכב ועוד)  
- Payment methods  
- Notes, descriptions, tagging  
- Full support for:
  - One-time expenses  
  - Recurring fixed expenses (הוראות קבע)  
  - Installments (תשלומים) with automatic month breakdown

### 📅 Financial Month Engine
Uses custom financial month:
- **10th to 9th** of the next month  
Used across:
- Filters  
- Reports  
- Budget calculations  
- Installment rendering

### 📊 Reports & Analytics
- Monthly totals  
- Category usage  
- Fixed vs variable spending  
- Battery-style budget meter  
- Donut and bar charts  
- Date-range display

### 📦 Monthly Budget System
- Budget per category  
- Previous month comparison  
- Income tracking (salary, ביטוח לאומי, קצבאות)  
- Smart grid layout for mobile

### ☁️ Supabase Backend
- `expenses` table  
- `budgets` table  
- `payment_plans` (installments)  
- REST API via `requests` (no ORM)

### 💾 Automatic Daily Backup System
- **Daily automated backups** of all Supabase data (expenses, budgets, payment_plans)
- **JSON format** - human-readable and version-control friendly
- **Smart cleanup** - automatically removes backups older than 30 days
- **Easy restore** - interactive restore script with backup selection
- **Windows Task Scheduler** integration for hands-free operation
- **Manual backup**: `python backup_daily.py`
- **Restore backup**: `python restore_backup.py`
- 📖 Full documentation in `BACKUP_INSTRUCTIONS.md`

---

## 🧱 Tech Stack

### Backend
- Python 3.12  
- Flask  
- Supabase REST API  
- Sessions for month sync  

### Frontend
- HTML (Jinja2 templates)  
- Mobile-first CSS (no frameworks)  
- RTL layout  
- Animated UI components  

### Deployment
- Render (auto-deploy from GitHub)  
- Dockerfile + gunicorn  
- Environment variables:
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `SECRET_KEY`

---

## 📂 Project Structure

```
project/
│   app.py
│   requirements.txt
│   README.md
│   render.yaml (optional)
│   Dockerfile (optional)
│   backup_daily.py          # Daily backup script
│   restore_backup.py        # Restore backup script
│   backup_schedule.bat      # Windows Task Scheduler wrapper
│   BACKUP_INSTRUCTIONS.md   # Backup system guide
│
├── templates/
│   ├── expenses.html
│   ├── add_expense.html
│   ├── edit_expense.html
│   ├── budget.html
│   ├── reports.html
│   └── tabs.html
│
├── static/
│   ├── style.css
│   └── design-system.md
│
└── backups/                 # Daily backups (auto-created, git-ignored)
    └── 2025-12-08_23-00/
        ├── expenses.json
        ├── budgets.json
        ├── payment_plans.json
        ├── backup_summary.json
        └── README.txt
```

---

## 🚀 Running Locally

### Install dependencies
pip install -r requirements.txt

shell
Copy code

### Set environment variables
export SUPABASE_URL="..."
export SUPABASE_KEY="..."
export SECRET_KEY="dev-secret-key"

shell
Copy code

### Run the app
python app.py

yaml
Copy code

Open at http://localhost:5000

---

## 🧪 Testing
Utility scripts included for:
- Budget debugging  
- Supabase test calls  
(See `test_budget_data.py`, `test_supabase*.py`)

---

## 👨‍💻 Development Notes
- No ORMs used  
- No external CSS frameworks  
- All logic is in `app.py` (intentional monolith)  
- Design system documented in `static/design-system.md`  
- Strong coupling between templates + CSS classes  
- Changes MUST respect:
  - RTL  
  - Mobile screen size  
  - Financial month logic  
  - Supabase schema 