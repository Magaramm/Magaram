import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          CallbackQueryHandler, CallbackContext)
from flask import Flask
from threading import Thread

# === Flask-сервер для UptimeRobot ===
app = Flask('')

@app.route('/')
def home():
    return "Я живой!"

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()

# === Константы ===
TOKEN = os.environ.get("BOT_TOKEN")
DOWNLOAD_DIR = 'downloads/'
VK_COOKIES = 'vkcookies.txt'        # файл с куки для ВК
YT_COOKIES = 'youtube.com_cookies.txt'
INST_COOKIES = 'instacookies.txt'
TT_COOKIES = 'tiktokcook'

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

QUALITY_OPTIONS = ['360', '480', '720']
user_data = {}

def is_playlist(url):
    return 'list=' in url

def parse_playlist_videos(url):
    ydl_opts = {'quiet': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        entries = info.get('entries', [])
        return [(i + 1, e['title'], e['webpage_url']) for i, e in enumerate(entries)]

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Отправь ссылку на YouTube, ВКонтакте, TikTok, Instagram или Facebook.")

async def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    user_id = update.effective_user.id

    supported_sites = ['youtube.com', 'youtu.be', 'vk.com', 'tiktok.com', 'instagram.com', 'facebook.com']

    if not any(site in url for site in supported_sites):
        await update.message.reply_text("Привет! Отправь ссылку на YouTube, ВКонтакте, TikTok, Instagram или Facebook.")
        return

    user_data[user_id] = {'url': url}

    if is_playlist(url) and 'youtube' in url:
        videos = parse_playlist_videos(url)
        if not videos:
            await update.message.reply_text("Плейлист пуст или не может быть прочитан.")
            return
        keyboard = []
        for num, title, _ in videos[:10]:
            btn_text = f"{num}. {title[:40]}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"select_{num}")])
        await update.message.reply_text("Выберите видео из плейлиста:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await ask_format(update)

async def ask_format(update: Update):
    keyboard = [[
        InlineKeyboardButton("🎵 Аудио", callback_data="format_audio"),
        InlineKeyboardButton("🎥 Видео", callback_data="format_video")
    ]]
    await update.message.reply_text("Выберите формат:", reply_markup=InlineKeyboardMarkup(keyboard))

async def ask_quality(update: Update, context: CallbackContext):
    buttons = [InlineKeyboardButton(f"{q}p", callback_data=f"quality_{q}") for q in QUALITY_OPTIONS]
    await update.callback_query.message.reply_text("Выберите качество видео:", reply_markup=InlineKeyboardMarkup([buttons]))

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = user_data.get(user_id)

    if query.data.startswith("select_"):
        num = int(query.data.split("_")[1])
        videos = parse_playlist_videos(data['url'])
        chosen = next((v for v in videos if v[0] == num), None)
        if not chosen:
            await query.edit_message_text("Ошибка выбора видео.")
            return
        user_data[user_id]['url'] = chosen[2]
        await query.edit_message_text(f"Вы выбрали: {chosen[1]}")
        await ask_format(update)

    elif query.data == "format_audio":
        user_data[user_id]['format'] = 'audio'
        await query.edit_message_text("Выбран формат: Аудио (320 kbps)")
        await start_download(update, context)

    elif query.data == "format_video":
        user_data[user_id]['format'] = 'video'
        await query.edit_message_text("Выбран формат: Видео")
        await ask_quality(update, context)

    elif query.data.startswith("quality_"):
        quality = query.data.split("_")[1]
        user_data[user_id]['quality'] = quality
        await query.edit_message_text(f"Качество видео: {quality}p")
        await start_download(update, context)

async def start_download(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    data = user_data.get(user_id)
    if not data:
        await update.callback_query.message.reply_text("Ошибка: нет данных.")
        return

    url = data['url']
    fmt = data['format']
    quality = data.get('quality', '360')
    await update.callback_query.message.reply_text("Скачиваю...")

    try:
        if fmt == 'video':
            filename, _ = download_video(url, quality)
            with open(filename, 'rb') as f:
                await update.callback_query.message.reply_video(video=f, caption="Отправлено через @Nkxay_bot")
            os.remove(filename)
        else:
            filename, title = download_audio(url)
            with open(filename, 'rb') as f:
                performer = update.callback_query.from_user.first_name
                await update.callback_query.message.reply_audio(audio=f, title=title, performer=performer, caption="Отправлено через @Nkxay_bot")
            os.remove(filename)
    except Exception as e:
        await update.callback_query.message.reply_text(f"Ошибка при скачивании: {e}")

def download_video(url, quality):
    ydl_opts = {
        'format': f'bestvideo[ext=mp4][height<={quality}]+bestaudio[ext=m4a]/mp4',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'noprogress': True,
        'cookiefile': (
            VK_COOKIES if 'vk.com' in url and os.path.exists(VK_COOKIES) else
            YT_COOKIES if 'youtube' in url and os.path.exists(YT_COOKIES) else
            INST_COOKIES if 'instagram.com' in url and os.path.exists(INST_COOKIES) else
            TT_COOKIES if 'tiktok.com' in url and os.path.exists(TT_COOKIES) else None
        ),
        'merge_output_format': 'mp4',
    }
    # Убираем None из опций, если куки нет
    ydl_opts_filtered = {k: v for k, v in ydl_opts.items() if v is not None}
    with yt_dlp.YoutubeDL(ydl_opts_filtered) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = os.path.join(DOWNLOAD_DIR, f"{info['title']}.mp4")
        return filename, info.get('title', 'Без названия')

def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'quiet': True,
        'noprogress': True,
        'cookiefile': (
            VK_COOKIES if 'vk.com' in url and os.path.exists(VK_COOKIES) else
            YT_COOKIES if 'youtube' in url and os.path.exists(YT_COOKIES) else
            INST_COOKIES if 'instagram.com' in url and os.path.exists(INST_COOKIES) else
            TT_COOKIES if 'tiktok.com' in url and os.path.exists(TT_COOKIES) else None
        ),
    }
    ydl_opts_filtered = {k: v for k, v in ydl_opts.items() if v is not None}
    with yt_dlp.YoutubeDL(ydl_opts_filtered) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
        return filename, info.get('title', 'Без названия')

def main():
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.run_polling()

if __name__ == '__main__':
    main()
