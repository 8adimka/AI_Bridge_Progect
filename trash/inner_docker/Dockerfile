FROM python:3.11-slim

# Устанавливаем системные зависимости для браузера
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libgtk-3-0 \
    libasound2 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Playwright и браузер
RUN pip install playwright==1.42.0 && playwright install chromium

# Устанавливаем зависимости приложения
COPY requirements.txt .
RUN pip install -r requirements.txt

# Копируем код приложения
COPY . /app
WORKDIR /app

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app

# Запускаем приложение под root
CMD ["python", "main.py"]
