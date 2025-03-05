import logging
import os
import io
import tempfile

from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageFilter
import moviepy.editor as mpy

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def transform_text(text: str) -> str:
    mapping = {
        'A': '𝒜', 'B': '𝒝', 'C': '𝒞', 'D': '𝒟', 'E': '𝒠',
        'a': '𝒶', 'b': '𝒷', 'c': '𝒸', 'd': '𝒹', 'e': '𝒺'
    }
    return ''.join(mapping.get(char, char) for char in text)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    original_text = update.message.text
    new_text = transform_text(original_text)
    await update.message.reply_text(f"Уникализированный текст:\n{new_text}")

def process_image(image_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.filter(ImageFilter.GaussianBlur(radius=2))
        data = list(img.getdata())
        new_img = Image.new(img.mode, img.size)
        new_img.putdata(data)
        output = io.BytesIO()
        new_img.save(output, format="JPEG")
        return output.getvalue()

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    processed_image = process_image(image_bytes)
    await update.message.reply_photo(
        photo=InputFile(io.BytesIO(processed_image), filename="unique.jpg")
    )

def process_video(video_path: str, output_path: str):
    try:
        clip = mpy.VideoFileClip(video_path)
        new_clip = clip.fx(mpy.vfx.speedx, factor=0.8)
        
        # Попробуем сначала без аудио для диагностики
        new_clip.write_videofile(
            output_path,
            codec="libx264",
            audio=False,  # временно отключаем аудио
            threads=1,
            ffmpeg_params=["-preset", "ultrafast"],
            logger="bar"  # вывод прогресса
        )
        
        # Проверяем размер файла после записи
        file_size = os.path.getsize(output_path)
        if file_size < 1024:
            raise ValueError(f"Полученный видеофайл слишком мал: {file_size} байт")
    finally:
        new_clip.close()
        clip.close()

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_file = await update.message.video.get_file()

    # Создаём временный файл для сохранения входного видео
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_in:
        video_path = temp_in.name

    # Скачиваем видео и сохраняем в файл
    video_bytes = await video_file.download_as_bytearray()
    with open(video_path, "wb") as f:
        f.write(video_bytes)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_out:
        output_path = temp_out.name

    try:
        process_video(video_path, output_path)
        await update.message.reply_video(video=InputFile(output_path))
    except Exception as e:
        logger.error(f"Ошибка обработки видео: {e}")
        await update.message.reply_text("Произошла ошибка при обработке видео.")
    finally:
        os.remove(video_path)
        os.remove(output_path)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне текст, фото или видео для уникализации.")

def main():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("Пожалуйста, установите переменную окружения TELEGRAM_BOT_TOKEN")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.VIDEO, video_handler))
    application.run_polling()

if __name__ == "__main__":
    main()
