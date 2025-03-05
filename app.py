import logging
import os
import io
import tempfile

from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from PIL import Image, ImageFilter
import moviepy.editor as mpy
import sys

# ---------------------------------------------------------------------------------
# 1. Настройка логирования
# ---------------------------------------------------------------------------------

# Уровень логирования можно менять (DEBUG, INFO, WARNING, ERROR)
logging.basicConfig(
    stream=sys.stdout,  # выводим логи в stdout
    level=logging.DEBUG,  # DEBUG - максимально подробная информация
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------
# 2. Функция уникализации текста
# ---------------------------------------------------------------------------------

def transform_text(text: str) -> str:
    mapping = {
        'A': '𝒜', 'B': '𝒝', 'C': '𝒞', 'D': '𝒟', 'E': '𝒠',
        'a': '𝒶', 'b': '𝒷', 'c': '𝒸', 'd': '𝒹', 'e': '𝒺'
    }
    return ''.join(mapping.get(char, char) for char in text)

# ---------------------------------------------------------------------------------
# 3. Обработчики текста и фото
# ---------------------------------------------------------------------------------

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logger.info(f"Получен текст от пользователя {update.effective_user.id}: {user_text}")
    new_text = transform_text(user_text)
    await update.message.reply_text(f"Уникализированный текст:\n{new_text}")

def process_image(image_bytes: bytes) -> bytes:
    logger.debug("Начинаем обработку изображения...")
    with Image.open(io.BytesIO(image_bytes)) as img:
        # Пример: размытие
        img = img.filter(ImageFilter.GaussianBlur(radius=2))
        # Удаляем метаданные, пересоздавая объект
        data = list(img.getdata())
        new_img = Image.new(img.mode, img.size)
        new_img.putdata(data)
        output = io.BytesIO()
        new_img.save(output, format="JPEG")
        logger.debug("Изображение успешно обработано и сохранено в буфер.")
        return output.getvalue()

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получено фото от пользователя {update.effective_user.id}")
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()
    logger.debug(f"Размер загруженного фото: {len(image_bytes)} байт")
    processed_image = process_image(image_bytes)
    await update.message.reply_photo(
        photo=InputFile(io.BytesIO(processed_image), filename="unique.jpg")
    )
    logger.info("Отправлено обработанное фото пользователю.")

# ---------------------------------------------------------------------------------
# 4. Обработка видео
# ---------------------------------------------------------------------------------

def process_video(video_path: str, output_path: str):
    """
    Обрабатывает видео, используя MoviePy:
    - Пример: замедление (speedx, factor=0.8)
    - Запись с кодеком libx264 и аудиокодеком aac
    - Пресет ultrafast для быстрой перекодировки
    - threads=1 для ограничения числа потоков
    - Логирование в консоли (logger="bar") для наглядности
    """
    logger.debug(f"Начинаем обработку видео: {video_path}")
    clip = mpy.VideoFileClip(video_path)

    new_clip = clip.fx(mpy.vfx.speedx, factor=0.8)
    try:
        new_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp-audio.m4a",  # временный файл аудио
            remove_temp=True,                 # удалять временные файлы
            threads=1,
            ffmpeg_params=["-preset", "ultrafast"],
            logger="bar"  # отображает прогресс MoviePy/ffmpeg в консоли
        )
    finally:
        # Закрываем клипы в блоке finally,
        # чтобы они точно были закрыты даже при ошибке
        new_clip.close()
        clip.close()

    # Проверяем размер выходного файла
    file_size = os.path.getsize(output_path)
    logger.info(f"Выходной файл: {output_path}, размер {file_size} байт")
    if file_size < 1024:
        logger.warning("Полученный видеофайл слишком мал, возможно произошла ошибка кодирования.")

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получено видео от пользователя {update.effective_user.id}")
    video_file = await update.message.video.get_file()

    # Создаём временный файл для входного видео
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_in:
        video_path = temp_in.name

    # Скачиваем видео
    video_bytes = await video_file.download_as_bytearray()
    logger.debug(f"Размер загруженного видео: {len(video_bytes)} байт")

    with open(video_path, "wb") as f:
        f.write(video_bytes)
    logger.debug(f"Видео сохранено во временный файл: {video_path}")

    # Создаём временный файл для выходного видео
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_out:
        output_path = temp_out.name

    try:
        process_video(video_path, output_path)
        # Отправляем обработанный файл пользователю
        await update.message.reply_video(video=InputFile(output_path))
        logger.info("Отправлено обработанное видео пользователю.")
    except Exception as e:
        logger.error(f"Ошибка обработки видео: {e}")
        await update.message.reply_text("Произошла ошибка при обработке видео.")
    finally:
        # Удаляем временные файлы
        os.remove(video_path)
        os.remove(output_path)
        logger.debug("Временные файлы удалены.")

# ---------------------------------------------------------------------------------
# 5. Команда /start
# ---------------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Пользователь {update.effective_user.id} запустил бота командой /start")
    await update.message.reply_text("Привет! Отправь мне текст, фото или видео для уникализации.")

# ---------------------------------------------------------------------------------
# 6. Основная функция main()
# ---------------------------------------------------------------------------------

def main():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.critical("Переменная окружения TELEGRAM_BOT_TOKEN не установлена!")
        raise ValueError("Пожалуйста, установите TELEGRAM_BOT_TOKEN")

    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.VIDEO, video_handler))

    logger.info("Запускаем бота...")
    application.run_polling()

if __name__ == "__main__":
    main()
