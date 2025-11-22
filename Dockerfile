# Image בסיס קליל של פייתון
FROM python:3.12-slim

# לא לשלוח קבצי pyc ועוד
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# לעבוד בתיקייה /app
WORKDIR /app

# להעתיק קבצי requirements ולהתקין חבילות
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# להעתיק את שאר הקבצים (קוד, templates, static וכו')
COPY . .

# פורט שהאפליקציה מאזינה עליו
ENV PORT=5000
EXPOSE 5000

# פקודת הרצה בפרודקשן עם gunicorn
# app:app = הקובץ app.py והאובייקט Flask שנקרא app
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
