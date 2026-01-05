# Python 3.11 slim
FROM python:3.11-slim

# متغیرهای محیطی
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# دایرکتوری کاری
WORKDIR /app

# نصب وابستگی‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی فایل‌ها
COPY app.py .
COPY templates/ templates/

# ایجاد پوشه دیتابیس
RUN mkdir -p /app/data
ENV DB_PATH=/app/data/warehouse.db

# Volume برای دیتابیس
VOLUME ["/app/data"]

# پورت
EXPOSE 5000

# اجرا با gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
