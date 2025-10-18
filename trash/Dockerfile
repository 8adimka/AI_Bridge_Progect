FROM python:3.13-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем Chromium (проще и надежнее)
RUN apt-get update && apt-get install -y chromium chromium-l10n --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY pyproject.toml poetry.lock ./

# Устанавливаем Poetry и зависимости
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root

# Копируем исходный код
COPY . .

# Создаем пользователя для безопасности
RUN groupadd -r gptuser && useradd -r -g gptuser -G audio,video gptuser && \
    mkdir -p /home/gptuser/Downloads && \
    mkdir -p /home/gptuser/.cache && \
    chown -R gptuser:gptuser /app /home/gptuser

# Переключаемся на непривилегированного пользователя
USER gptuser

# Устанавливаем браузеры Playwright под пользователем gptuser
RUN playwright install chromium

# Открываем порт для API
EXPOSE 8010

# Запускаем приложение
CMD ["python", "-m", "app.main_docker_step_by_step"]
