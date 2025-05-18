import os
import yt_dlp
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from flask import Flask
from threading import Thread

# --- Flask сервер для пинга UptimeRobot ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

Thread(target=run_web).start()

# --- Константы ---
TOKEN = os.environ.get("BOT_TOKEN")
DOWNLOAD_DIR = "downloads/"
YT_COOKIES = "youtube.com_cookies.txt"
INST_COOKIES = "instacookies.txt"
TIKTOK_COOKIES = "tiktokcook"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

user_data = {}

QUALITY_OPTIONS = ['360', '480', '720']

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь ссылку на видео с YouTube, TikTok, Instagram или VK.")

# --- Обработка сообщения с ссылкой ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    user_data[user_id] = {'url': url}

    if 'tiktok.com' in url or 'instagram.com' in url:
        await update.message.reply_text("Скачиваю...")
        try:
            filename, _ = download_best_video(url)
            with open(filename, 'rb') as f:
                await update.message.reply_video(video=f, caption="Отправлено через @Nkxay_bot")
            os.remove(filename)
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        keyboard = [
            [InlineKeyboardButton("🎵 Аудио", callback_data="format_audio"),
             InlineKeyboardButton("🎥 Видео", callback_data="format_video")]
        ]
        await update.message.reply_text("Выбери формат:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Обработка кнопок ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = user_data.get(user_id, {})

    if query.data == "format_audio":
        await query.edit_message_text("Скачиваю аудио...")
        try:
            filename, title = download_audio(data['url'])
            with open(filename, 'rb') as f:
                await query.message.reply_audio(audio=f, title=title, performer=query.from_user.first_name)
            os.remove(filename)
        except Exception as e:
            await query.message.reply_text(f"Ошибка: {e}")

    elif query.data == "format_video":
        keyboard = [[InlineKeyboardButton(f"{q}p", callback_data=f"quality_{q}") for q in QUALITY_OPTIONS]]
        await query.edit_message_text("Выбери качество видео:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("quality_"):
        quality = query.data.split("_")[1]
        await query.edit_message_text(f"Скачиваю видео {quality}p...")
        try:
            filename, _ = download_video(data['url'], quality)
            with open(filename, 'rb') as f:
                await query.message.reply_video(video=f, caption="Отправлено через @Nkxay_bot")
            os.remove(filename)
        except Exception as e:
            await query.message.reply_text(f"Ошибка: {e}")

# --- Скачивание видео ---
def download_video(url, quality):
    cookiefile = detect_cookie(url)
    ydl_opts = {
        'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'cookiefile': cookiefile,
        'quiet': True,
        'noprogress': True,
        'concurrent_fragment_downloads': 4,
        'max_filesize': 50_000_000,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info.get('title')

# --- Скачивание аудио ---
def download_audio(url):
    cookiefile = detect_cookie(url)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'noprogress': True,
        'cookiefile': cookiefile,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = os.path.join(DOWNLOAD_DIR, f"{info['title']}.mp3")
        return filename, info.get('title')

# --- Универсальный загрузчик (для TikTok и Instagram) ---
def download_best_video(url):
    return download_video(url, '720')

# --- Определение куки-файла ---
def detect_cookie(url):
    if 'youtube' in url and os.path.exists(YT_COOKIES):
        return YT_COOKIES
    if 'instagram.com' in url and os.path.exists(INST_COOKIES):
        return INST_COOKIES
    if 'tiktok.com' in url and os.path.exists(TIKTOK_COOKIES):
        return TIKTOK_COOKIES
    return None

# --- Запуск бота ---
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Бот запущен.")
    app.run_polling()

if __name__ == "__main__":
    main()
