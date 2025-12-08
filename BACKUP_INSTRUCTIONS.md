# מדריך מערכת גיבוי יומית

## 📋 סקירה

מערכת הגיבוי כוללת 3 רכיבים עיקריים:

1. **backup_daily.py** - סקריפט גיבוי אוטומטי
2. **restore_backup.py** - סקריפט שחזור גיבוי
3. **backup_schedule.bat** - קובץ BAT להפעלה אוטומטית ב-Windows

---

## 🚀 הפעלה ידנית

### גיבוי

```bash
python backup_daily.py
```

הגיבוי ישמר בתיקייה: `backups/YYYY-MM-DD_HH-MM/`

### שחזור

```bash
python restore_backup.py
```

תבחר גיבוי מהרשימה ותאשר את השחזור.

---

## ⏰ הגדרת גיבוי יומי אוטומטי ב-Windows

### שלב 1: פתיחת Task Scheduler

1. לחץ **Win + R**
2. הקלד: `taskschd.msc`
3. לחץ Enter

### שלב 2: יצירת Task חדש

1. לחץ **Create Basic Task** בפאנל ימין
2. שם: `Matsavinu Daily Backup`
3. תיאור: `גיבוי יומי של נתוני הוצאות`
4. לחץ **Next**

### שלב 3: הגדרת תזמון

1. בחר **Daily** (יומי)
2. לחץ **Next**
3. בחר שעה: **23:00** (11 PM) - או כל שעה שנוחה לך
4. בחר **Recur every: 1 days**
5. לחץ **Next**

### שלב 4: הגדרת הפעולה

1. בחר **Start a program**
2. לחץ **Next**
3. ב-Program/script:
   ```
   H:\מעקב הוצאות\supabase\supabase\backup_schedule.bat
   ```
   (התאם את הנתיב למיקום שלך)
4. לחץ **Next**

### שלב 5: סיום

1. סמן את **Open the Properties dialog...**
2. לחץ **Finish**

### שלב 6: הגדרות מתקדמות

בחלון Properties שנפתח:

#### General (כללי):
- ✅ Run whether user is logged on or not
- ✅ Run with highest privileges

#### Conditions (תנאים):
- ❌ Start the task only if the computer is on AC power (בטל!)
- ✅ Wake the computer to run this task (אופציונלי)

#### Settings (הגדרות):
- ✅ Allow task to be run on demand
- ✅ If the task fails, restart every: **1 hour**
- ✅ Stop the task if it runs longer than: **1 hour**

לחץ **OK** ושמור.

---

## 📁 מבנה תיקיית גיבוי

```
backups/
├── 2025-12-08_23-00/
│   ├── expenses.json           # כל ההוצאות
│   ├── budgets.json            # כל התקציבים
│   ├── payment_plans.json      # תוכניות תשלומים
│   ├── backup_summary.json     # סיכום טכני
│   └── README.txt              # סיכום קריא
├── 2025-12-07_23-00/
└── 2025-12-06_23-00/
```

---

## 🧹 ניקוי אוטומטי

הסקריפט **שומר אוטומטית רק 30 ימי גיבוי אחרונים**.

לשינוי התקופה, ערוך ב-`backup_daily.py`:

```python
cleanup_old_backups(keep_days=30)  # שנה למספר הרצוי
```

---

## 🔍 בדיקת סטטוס

### לוג הפעלות:

הקובץ `backup_log.txt` מתעדך אוטומטית אחרי כל גיבוי:

```
Backup completed at 08/12/2025 23:00:15
Backup completed at 09/12/2025 23:00:12
```

### בדיקה ידנית:

```bash
# הצג את כל הגיבויים
dir backups

# הצג סיכום גיבוי אחרון
type backups\<תאריך>\README.txt
```

---

## ⚠️ חשוב לדעת

1. **הגיבוי אינו מחליף את Supabase** - זה עותק מקומי בלבד
2. **גיבויים נשמרים במחשב שלך** - אם תמחק את התיקייה, הם ילכו לאיבוד
3. **יש לשמור את `.env`** - בלי זה לא ניתן לגבות/לשחזר
4. **גיבוי חיצוני מומלץ** - העתק את `backups/` לדיסק חיצוני או ענן

---

## 🆘 פתרון בעיות

### הגיבוי לא רץ אוטומטית

1. בדוק ב-Task Scheduler אם ה-Task פעיל
2. לחץ ימין על Task → **Run** לבדיקה ידנית
3. בדוק את הלוג: `backup_log.txt`

### שגיאת חיבור ל-Supabase

1. ודא ש-`.env` קיים ומכיל:
   ```
   SUPABASE_URL=...
   SUPABASE_KEY=...
   ```
2. בדוק חיבור אינטרנט

### הסקריפט לא מוצא את הסביבה הוירטואלית

1. ודא שהתיקייה `.venv` קיימת
2. הפעל:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

---

## 📞 צור קשר

לשאלות או בעיות, פנה למפתח הפרויקט.

**גרסה:** 1.0  
**עודכן לאחרונה:** דצמבר 2025
