import asyncio
import logging
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
CODE, READY = range(2)

# Базовый URL API сервиса
API_BASE_URL = "http://localhost:8010"

# Получаем токен бота из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")

# Конфигурация
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 30


class TelegramBotEnhanced:
    def __init__(self):
        self.application = None

    def _make_api_request(self, method: str, endpoint: str, **kwargs) -> Optional[dict]:
        """Выполняет API запрос с повторными попытками"""
        for attempt in range(MAX_RETRIES):
            try:
                url = f"{API_BASE_URL}{endpoint}"
                response = requests.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code >= 500:
                    logger.warning(f"Серверная ошибка {response.status_code}, попытка {attempt + 1}/{MAX_RETRIES}")
                else:
                    logger.error(f"Ошибка API {response.status_code}: {response.text}")
                    return None
                    
            except requests.exceptions.ConnectionError:
                logger.warning(f"Ошибка подключения, попытка {attempt + 1}/{MAX_RETRIES}")
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут запроса, попытка {attempt + 1}/{MAX_RETRIES}")
            except Exception as e:
                logger.error(f"Неожиданная ошибка при запросе: {e}")
                return None
                
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                
        logger.error(f"Не удалось выполнить запрос после {MAX_RETRIES} попыток")
        return None

    async def _send_typing_action(self, update: Update):
        """Отправляет индикатор набора текста"""

        if not update.message:
            print("Update не содержит сообщение")
            return False

        try:
            await update.message.chat.send_action(action="typing")
        except Exception as e:
            logger.warning(f"Не удалось отправить индикатор набора: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начало взаимодействия с ботом"""
        if not update.message:
            return ConversationHandler.END
            
        auth_status = self._make_api_request("GET", "/auth/status")
        
        if not auth_status:
            await update.message.reply_text(
                "❌ Ошибка подключения к сервису. Убедитесь, что сервис запущен."
            )
            return ConversationHandler.END

        if auth_status["status"] == "completed":
            await update.message.reply_text(
                "🎉 Аутентификация уже завершена!\n\n"
                "✅ Система готова к работе.\n\n"
                "Теперь вы можете отправлять запросы к ChatGPT."
            )
            return READY
        elif auth_status["status"] == "waiting_code":
            await update.message.reply_text(
                "👋 Добро пожаловать в GPT Bridge Bot!\n\n"
                "📧 На вашу почту отправлен код подтверждения.\n\n"
                "🔢 Пожалуйста, введите код с вашей почты:"
            )
            return CODE
        elif auth_status["status"] == "not_authenticated":
            await update.message.reply_text(
                "👋 Добро пожаловать в GPT Bridge Bot!\n\n"
                "⏳ Система выполняет автоматическую аутентификацию...\n\n"
                "Пожалуйста, подождите немного и попробуйте снова через /start"
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                f"Текущий статус аутентификации: {auth_status['status']}\n"
                "Пожалуйста, подождите или перезапустите систему."
            )
            return ConversationHandler.END

    async def receive_code(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получаем код подтверждения от пользователя и отправляем в сервис"""
        if not update.message:
            return ConversationHandler.END
            
        code = update.message.text

        # Отправляем код подтверждения в сервис
        result = self._make_api_request("POST", "/auth/code", json={"code": code})

        await update.message.reply_text(
            "✅ Код подтверждения отправлен!\n\n"
            "⏳ Проверяем статус авторизации...\n\n"
            "Пожалуйста, подождите..."
        )

        # Ждем завершения авторизации
        await asyncio.sleep(3)

        # Проверяем фактический статус авторизации
        auth_status = self._make_api_request("GET", "/auth/status")
        
        if not auth_status:
            await update.message.reply_text(
                "❌ Ошибка при проверке статуса авторизации. Попробуйте еще раз."
            )
            return CODE

        if auth_status["status"] == "completed":
            await update.message.reply_text(
                "🎉 Аутентификация успешно завершена!\n\n"
                "✅ Система готова к работе.\n\n"
                "Теперь вы можете отправлять запросы к ChatGPT."
            )
            return READY
        else:
            # Если авторизация не завершена, показываем текущий статус
            await update.message.reply_text(
                f"❌ Авторизация не завершена. Текущий статус: {auth_status['status']}\n\n"
                "Пожалуйста, проверьте код и попробуйте еще раз или введите /start для перезапуска."
            )
            return CODE

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Обрабатывает обычные сообщения после аутентификации"""
        if not update.message:
            return
            
        message_text = update.message.text

        # Проверяем статус аутентификации
        auth_status = self._make_api_request("GET", "/auth/status")
        
        if not auth_status:
            await update.message.reply_text("❌ Ошибка подключения к сервису.")
            return
            
        if auth_status["status"] != "completed":
            await update.message.reply_text(
                "❌ Система не аутентифицирована.\n\n"
                "Пожалуйста, введите /start для начала аутентификации."
            )
            return

        # Отправляем индикатор набора текста
        await self._send_typing_action(update)
        
        # Отправляем запрос в сервис
        await update.message.reply_text("⏳ Обрабатываю ваш запрос...")

        result = self._make_api_request("POST", "/ask", json={"prompt": message_text})
        
        if not result:
            await update.message.reply_text("❌ Ошибка при обработке запроса.")
            return

        if "answer" in result:
            answer = result["answer"]
            # Разбиваем длинные ответы на части
            if len(answer) > 4000:
                for i in range(0, len(answer), 4000):
                    await update.message.reply_text(f"🤖 {answer[i : i + 4000]}")
            else:
                await update.message.reply_text(f"🤖 {answer}")
        else:
            error_msg = result.get("error", "Неизвестная ошибка")
            await update.message.reply_text(f"❌ Ошибка: {error_msg}")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает текущий статус системы"""
        if not update.message:
            return
            
        health_status = self._make_api_request("GET", "/health")
        auth_status = self._make_api_request("GET", "/auth/status")
        
        if not health_status or not auth_status:
            await update.message.reply_text("❌ Ошибка при получении статуса системы.")
            return

        status_message = (
            "📊 **Статус системы:**\n\n"
            f"🟢 **Сервис:** {health_status.get('status', 'unknown')}\n"
            f"📊 **Очередь:** {health_status.get('queue_size', 0)} запросов\n"
            f"⚙️ **Обработка:** {'Да' if health_status.get('processing', False) else 'Нет'}\n\n"
            f"🔐 **Аутентификация:** {auth_status.get('status', 'unknown')}\n"
            f"📧 **Email:** {'✅' if auth_status.get('email_provided', False) else '❌'}\n"
            f"🔑 **Пароль:** {'✅' if auth_status.get('password_provided', False) else '❌'}\n"
            f"🔢 **Код:** {'✅' if auth_status.get('code_provided', False) else '❌'}\n"
            f"🌐 **Браузер:** {'✅' if auth_status.get('browser_initialized', False) else '❌'}"
        )

        await update.message.reply_text(status_message)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отменяет текущую операцию"""
        if update.message:
            await update.message.reply_text("Операция отменена.")
        return ConversationHandler.END

    def setup_handlers(self):
        """Настраивает обработчики команд"""
        # Conversation handler для аутентификации
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                CODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_code)
                ],
                READY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

        if not self.application:
            print("Application не инициализирован")
            return False

        # Другие обработчики
        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler("status", self.status))

        # Обработчик для обычных сообщений (после аутентификации)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    def run(self):
        """Запускает бота"""
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN не установлен")
            return
            
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Настраиваем обработчики
        self.setup_handlers()

        # Запускаем бота
        logger.info("Запуск Telegram бота...")
        self.application.run_polling()


def main():
    """Основная функция для запуска бота"""
    bot = TelegramBotEnhanced()

    # Запускаем бота
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    main()
