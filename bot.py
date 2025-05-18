import os
import yt_dlp
import subprocess
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, CallbackContext
from flask import Flask
from threading import Thread

# Flask для UptimeRobot
app = Flask('')

@app.route('/')
def home():
    return "Я живой!"

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()

TOKEN = os.environ.get("BOT_TOKEN")
DOWNLOAD_DIR = 'downloads/'
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

VK_COOKIES = 'vkcookies.txt'
TT_COOKIES = 'tiktokcook.txt'

QUALITY_OPTIONS = ['360', '480', '720']
user_data = {}

def is_playlist(url):
    return 'list=' in url and ('youtube.com' in url or 'youtu.be' in url)

def is_vertical_video(url):
    return any(site in url for site in ['tiktok.com', 'instagram.com', 'facebook.com'])

def parse_playlist_videos(url):
    ydl_opts = {'quiet': True, 'skip_download': True, 'cookiefile': VK_COOKIES}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        entries = info.get('entries', [])
        return [(i+1, e['title'], e['webpage_url']) for i, e in enumerate(entries)]

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Отправь ссылку на YouTube, ВКонтакте, TikTok, Instagram или Facebook.")

async def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    user_id = update.effective_user.id

    supported_sites = ['youtube.com', 'youtu.be', 'vk.com', 'tiktok.com', 'instagram.com', 'facebook.com']

    if not any(site in url for site in supported_sites):
        await update.message.reply_text("Поддерживаются ссылки с YouTube, ВКонтакте, TikTok, Instagram и Facebook.")
        return

    user_data[user_id] = {'url': url}

    if is_playlist(url):
        videos = parse_playlist_videos(url)
        if not videos:
            await update.message.reply_text("Плейлист пуст или не может быть прочитан.")
            return
        keyboard = []
        for num, title, _ in videos[:10]:
            btn_text = f"{num}. {title[:40]}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"select_{num}")])
        await update.message.reply_text("Выберите видео из плейлиста:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif is_vertical_video(url):
        await update.message.reply_text("Скачиваю вертикальное видео...")
        try:
            filename = await asyncio.to_thread(download_best_video, url)
            with open(filename, 'rb') as f:
                await update.message.reply_video(video=f, caption="Отправлено через @Nkxay_bot")
            os.remove(filename)
        except Exception as e:
            await update.message.reply_text(f"Ошибка при скачивании: {e}")
    else:
        await ask_format(update)

async def ask_format(update: Update):
    keyboard = [
        [
            InlineKeyboardButton("🎵 Аудио", callback_data="format_audio"),
            InlineKeyboardButton("🎥 Видео", callback_data="format_video"),
        ]
    ]
    await update.message.reply_text("Выберите формат:", reply_markup=InlineKeyboardMarkup(keyboard))

async def ask_quality(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
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
    quality = data.get('quality', '320')
    await update.callback_query.message.reply_text("Скачиваю...")

    try:
        if fmt == 'video':
            if is_vertical_video(url):
                filename = await asyncio.to_thread(download_best_video, url)
            else:
                filename = await asyncio.to_thread(download_video, url, quality)
            with open(filename, 'rb') as f:
                await update.callback_query.message.reply_video(video=f, caption="Отправлено через @Nkxay_bot")
            os.remove(filename)
        else:
            filename, title = await asyncio.to_thread(download_audio, url)
            with open(filename, 'rb') as f:
                performer = update.callback_query.from_user.first_name
                await update.callback_query.message.reply_audio(audio=f, title=title, performer=performer, caption="Отправлено через @Nkxay_bot")
            os.remove(filename)
    except Exception as e:
        await update.callback_query.message.reply_text(f"Ошибка при скачивании: {e}")

def convert_to_ios_compatible(input_file, output_file):
    command = [
        'ffmpeg', '-i', input_file,
        '-c:v', 'libx264', '-profile:v', 'baseline', '-level', '3.0',
        '-c:a', 'aac',
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        output_file,
        '-y'
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def download_best_video(url):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'cookiefile': TT_COOKIES if 'tiktok' in url else (VK_COOKIES if 'vk.com' in url else None),
        'merge_output_format': 'mp4',
        'noprogress': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    output_file = filename.rsplit('.', 1)[0] + '_ios.mp4'
    convert_to_ios_compatible(filename, output_file)
    os.remove(filename)
    return output_file

def download_video(url, quality):
    ydl_opts = {
        'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'cookiefile': VK_COOKIES if 'vk.com' in url else None,
        'merge_output_format': 'mp4',
        'noprogress': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    output_file = filename.rsplit('.', 1)[0] + '_ios.mp4'
    convert_to_ios_compatible(filename, output_file)
    os.remove(filename)
    return output_file

def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'cookiefile': VK_COOKIES if 'vk.com' in url else None,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'noprogress': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = os.path.splitext(ydl.prepare_filename(info))[0] + '.mp3'
    title = info.get('title', 'audio')
    return filename, title

def main():
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    print("Бот запущен!")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
