# Dockerfile
FROM python:3.12-slim

# לא כותב pyc ומדפיס ל־stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# מתקין תלויות
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# מעתיק את קבצי הפרויקט
COPY . .

# פורט ברירת־מחדל ל־Fly (חשוב!)
ENV PORT=8080
EXPOSE 8080

# מריץ את האפליקציה עם gunicorn על פורט 8080
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8080", "app:app"]
