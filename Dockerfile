# Используем официальный Python 3.10-slim образ
FROM python:3.10-slim

# Обновляем пакеты и устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    libz-dev \
    libjpeg-dev \
    libfreetype6-dev \
    pkg-config \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Задаём рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Указываем команду запуска приложения (используем переменную окружения TELEGRAM_BOT_TOKEN)
CMD ["python", "app.py"]
