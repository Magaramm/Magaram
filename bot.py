import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          CallbackQueryHandler, CallbackContext,
                          PicklePersistence)
from flask import Flask
from threading import Thread

# === Flask-сервер для UptimeRobot ===
app = Flask('')


@app.route('/')
def home():
    return "Я живой!"


def run_web():
    app.run(host='0.0.0.0', port=8080)


Thread(target=run_web).start()

# === Константы ===
TOKEN = os.environ.get("BOT_TOKEN")
DOWNLOAD_DIR = 'downloads/'

VK_COOKIES = os.environ.get("VK_COOKIES", "vk.com_cookies.txt")
YT_COOKIES = os.environ.get("YT_COOKIES", "youtube.com_cookies.txt")
TT_COOKIES = os.environ.get("TT_COOKIES", "tiktok_cookies.txt")
IG_COOKIES = os.environ.get("IG_COOKIES", "instacookies.txt")
FB_COOKIES = os.environ.get("FB_COOKIES", "facebook_cookies.txt")

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

QUALITY_OPTIONS = {'video': ['360', '480', '720']}
user_data = {}


def get_cookie_file(url: str):
    if 'vk.com' in url:
        return VK_COOKIES
    elif 'youtube.com' in url or 'youtu.be' in url:
        return YT_COOKIES
    elif 'tiktok.com' in url:
        return TT_COOKIES
    elif 'instagram.com' in url:
        return IG_COOKIES
    elif 'facebook.com' in url:
        return FB_COOKIES
    else:
        return None


def is_playlist(url):
    return 'list=' in url


def is_youtube_short(url: str) -> bool:
    return 'youtube.com/shorts/' in url


def parse_playlist_videos(url):
    ydl_opts = {'quiet': True, 'skip_download': True, 'cookiefile': get_cookie_file(url)}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        entries = info.get('entries', [])
        return [(i + 1, e['title'], e['webpage_url'])
                for i, e in enumerate(entries)]


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Привет! Отправь ссылку на YouTube, ВКонтакте, TikTok, Instagram или Facebook."
    )


async def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    user_id = update.effective_user.id

    supported_sites = [
        'youtube.com', 'youtu.be', 'vk.com', 'tiktok.com', 'instagram.com',
        'facebook.com'
    ]

    if not any(site in url for site in supported_sites):
        await update.message.reply_text(
            "Пожалуйста, отправь ссылку на поддерживаемый сайт.")
        return

    user_data[user_id] = {'url': url}

    if is_playlist(url) and 'youtube' in url:
        videos = parse_playlist_videos(url)
        if not videos:
            await update.message.reply_text(
                "Плейлист пуст или не может быть прочитан.")
            return
        keyboard = []
        for num, title, _ in videos[:10]:
            btn_text = f"{num}. {title[:40]}"
            keyboard.append([
                InlineKeyboardButton(btn_text, callback_data=f"select_{num}")
            ])
        await update.message.reply_text(
            "Выберите видео из плейлиста:",
            reply_markup=InlineKeyboardMarkup(keyboard))
    elif is_youtube_short(url):
        # Для YouTube Shorts скачиваем сразу в макс качестве и отправляем
        await update.message.reply_text("Всё делается с любовью, минутку!")
        try:
            filename, title = download_best_video(url)  # вот исправленный участок
            with open(filename, 'rb') as f:
                await update.message.reply_video(video=f,
                                                caption="Отправлено через @Nkxay_bot")
            os.remove(filename)
        except Exception as e:
            await update.message.reply_text(f"Ошибка при скачивании: {e}")
    elif any(x in url for x in ['tiktok.com', 'instagram.com', 'facebook.com']):
        await update.message.reply_text("Всё делается с любовью, минутку!")
        try:
            filename, title = download_best_video(url)
            with open(filename, 'rb') as f:
                await update.message.reply_video(video=f,
                                                caption="Отправлено через @Nkxay_bot")
            os.remove(filename)
        except Exception as e:
            await update.message.reply_text(f"Ошибка при скачивании: {e}")
    else:
        await ask_format(update)


async def ask_format(update: Update):
    keyboard = [[
        InlineKeyboardButton("🎵 Аудио", callback_data="format_audio"),
        InlineKeyboardButton("🎥 Видео", callback_data="format_video")
    ]]
    await update.message.reply_text(
        "Выберите формат:", reply_markup=InlineKeyboardMarkup(keyboard))


async def ask_quality(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    buttons = [
        InlineKeyboardButton(f"{q}p", callback_data=f"quality_{q}")
        for q in QUALITY_OPTIONS['video']
    ]
    await update.callback_query.message.reply_text(
        "Выберите качество видео:",
        reply_markup=InlineKeyboardMarkup([buttons]))


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

    await update.callback_query.edit_message_text("Всё делается с любовью, минутку!")

    try:
        if fmt == 'video':
            filename, title = download_video(url, quality)
            with open(filename, 'rb') as f:
                await update.callback_query.message.reply_video(video=f,
                                                                caption=title)
        else:
            filename, title = download_audio(url)
            with open(filename, 'rb') as f:
                performer = update.callback_query.from_user.first_name
                await update.callback_query.message.reply_audio(
                    audio=f, title=title, performer=performer)
        os.remove(filename)
        await update.callback_query.message.reply_text("Отправлено через @Nkxay_bot")
    except Exception as e:
        await update.callback_query.message.reply_text(
            f"Ошибка при скачивании: {e}")


def download_video(url, quality):
    ydl_opts = {
        'format':
        f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': True,
        'noprogress': True,
        'max_filesize': 100_000_000,
        'cookiefile': get_cookie_file(url),
        'http_headers': {
            'User-Agent': 'Mozilla/5.0'
        }
    }
    with yt_dlp.YoutubeDL({k: v for k, v in ydl_opts.items() if v is not None}) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = os.path.join(DOWNLOAD_DIR, f"{info['id']}.mp4")
        return filename, info.get('title', 'Без названия')


def download_audio(url):
    ydl_opts = {
        'format':
        'bestaudio/best',
        'outtmpl':
        os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'quiet':
        True,
        'noprogress':
        True,
        'cookiefile':
        get_cookie_file(url),
        'http_headers': {
            'User-Agent': 'Mozilla/5.0'
        }
    }
    with yt_dlp.YoutubeDL({k: v for k, v in ydl_opts.items() if v is not None}) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = os.path.join(DOWNLOAD_DIR, f"{info['id']}.mp3")
        return filename, info.get('title', 'Без названия')


def download_best_video(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': True,
        'noprogress': True,
        'max_filesize': 50_000_000,
        'cookiefile': get_cookie_file(url),
        'http_headers': {
            'User-Agent': 'Mozilla/5.0'
        }
    }
    with yt_dlp.YoutubeDL({k: v for k, v in ydl_opts.items() if v is not None}) as ydl:
        info = ydl.extract_info(url, download=True)
        ext = info.get('ext', 'mp4')
        filename = os.path.join(DOWNLOAD_DIR, f"{info['id']}.{ext}")
        return filename, info.get('title', 'Без названия')


def main():
    persistence = PicklePersistence(filepath='bot_data.pkl')
    application = Application.builder().token(TOKEN).persistence(persistence).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()


if __name__ == "__main__":
    main()
