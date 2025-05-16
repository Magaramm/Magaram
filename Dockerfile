# Берём образ Ubuntu 22.04
FROM ubuntu:22.04

# Обновляем систему и ставим Python 3.11, pip и ffmpeg
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую папку
WORKDIR /app

# Копируем все файлы из твоей локальной папки в контейнер
COPY . /app

# Обновляем pip и ставим зависимости из requirements.txt
RUN python3.11 -m pip install --upgrade pip setuptools wheel
RUN python3.11 -m pip install -r requirements.txt

# Команда для запуска бота (замени bot.py на название твоего скрипта)
CMD ["python3.11", "bot.py"]
