import os
from yt_dlp import YoutubeDL
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# Токен бота
TOKEN = 'YOUR_BOT_TOKEN_HERE'  # замени на свой токен

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Файлы с куки для VK и YouTube
COOKIES_VK = 'cookies_vk.txt'
COOKIES_YT = 'cookies_yt.txt'

def download_video(url: str, cookiefile: str) -> str:
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
        'outtmpl': '%(title)s.%(ext)s',
        'cookiefile': cookiefile if cookiefile else None,
        'quiet': True,
        'no_warnings': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    return filename

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("Привет! Отправь ссылку на видео или плейлист.")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('choose_'))
async def process_callback_choose(callback_query: types.CallbackQuery):
    video_id = callback_query.data[len('choose_'):]
    url = f"https://www.youtube.com/watch?v={video_id}"
    await bot.answer_callback_query(callback_query.id, text="Начинаю загрузку выбранного видео...")

    try:
        file_path = download_video(url, COOKIES_YT)
        with open(file_path, 'rb') as video_file:
            await bot.send_video(callback_query.from_user.id, video_file)
        os.remove(file_path)
    except Exception as e:
        await bot.send_message(callback_query.from_user.id, f"Ошибка при скачивании видео: {e}")

@dp.message_handler()
async def handle_message(message: types.Message):
    url = message.text.strip()

    if 'vk.com' in url:
        cookiefile = COOKIES_VK
    elif 'youtube.com' in url or 'youtu.be' in url:
        cookiefile = COOKIES_YT
    else:
        cookiefile = None

    # Если ссылка на плейлист
    if 'list=' in url:
        ydl_opts = {
            'ignoreerrors': True,
            'cookiefile': cookiefile if cookiefile else None,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if info and 'entries' in info:
            keyboard = InlineKeyboardMarkup(row_width=1)
            for entry in info['entries']:
                if entry is None:
                    continue
                btn_text = entry.get('title', 'Видео')
                video_id = entry.get('id')
                keyboard.insert(InlineKeyboardButton(btn_text, callback_data=f'choose_{video_id}'))
            await message.answer("Выберите видео из плейлиста:", reply_markup=keyboard)
            return
        else:
            await message.answer("Не удалось получить плейлист.")
            return

    # Обычная ссылка на видео
    try:
        file_path = download_video(url, cookiefile) if cookiefile else download_video(url, '')
        with open(file_path, 'rb') as video_file:
            await bot.send_video(message.chat.id, video_file)
        os.remove(file_path)
    except Exception as e:
        await message.answer(f"Ошибка при скачивании видео: {e}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
