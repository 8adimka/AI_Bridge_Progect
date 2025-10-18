import asyncio
import logging
import os

import requests
from dotenv import load_dotenv
from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
EMAIL, PASSWORD, CODE, READY = range(4)

# Базовый URL API Docker-контейнера
API_BASE_URL = "http://localhost:8010"

# Получаем токен бота из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")


class TelegramBotManager:
    def __init__(self):
        self.application = None
        self.user_states = {}  # Хранит состояние пользователей

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начало взаимодействия с ботом"""
        user_id = update.effective_user.id

        # Проверяем статус аутентификации в Docker-контейнере
        try:
            response = requests.get(f"{API_BASE_URL}/auth/status")
            auth_status = response.json()

            if auth_status["auth_state"] == "completed":
                await update.message.reply_text(
                    "✅ Аутентификация уже завершена! Система готова к работе.\n\n"
                    "Теперь вы можете отправлять запросы к ChatGPT."
                )
                return READY
            elif auth_status["auth_state"] == "waiting_email":
                await update.message.reply_text(
                    "👋 Добро пожаловать в GPT Bridge Bot!\n\n"
                    "Для начала работы необходимо пройти аутентификацию в ChatGPT.\n\n"
                    "📧 Пожалуйста, введите ваш email/логин для ChatGPT:"
                )
                return EMAIL
            else:
                await update.message.reply_text(
                    f"Текущий статус аутентификации: {auth_status['auth_state']}\n"
                    "Пожалуйста, подождите или перезапустите систему."
                )
                return ConversationHandler.END

        except Exception as e:
            logger.error(f"Ошибка при проверке статуса аутентификации: {e}")
            await update.message.reply_text(
                "❌ Ошибка подключения к сервису. Убедитесь, что Docker-контейнер запущен."
            )
            return ConversationHandler.END

    async def receive_email(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получаем email от пользователя и отправляем в Docker-контейнер"""
        email = update.message.text
        user_id = update.effective_user.id

        try:
            # Сохраняем email в контексте
            context.user_data["email"] = email

            # Отправляем email в Docker-контейнер
            response = requests.post(
                f"{API_BASE_URL}/auth/email", json={"email": email}
            )

            if response.status_code == 200:
                await update.message.reply_text(
                    "✅ Email успешно принят!\n\n"
                    "🔐 Теперь введите ваш пароль для ChatGPT:"
                )
                return PASSWORD
            else:
                error_msg = response.json().get("error", "Неизвестная ошибка")
                await update.message.reply_text(
                    f"❌ Ошибка при отправке email: {error_msg}\n\n"
                    "Пожалуйста, попробуйте еще раз или введите /start для перезапуска."
                )
                return ConversationHandler.END

        except Exception as e:
            logger.error(f"Ошибка при обработке email: {e}")
            await update.message.reply_text(
                "❌ Ошибка при обработке email. Пожалуйста, попробуйте еще раз или введите /start."
            )
            return ConversationHandler.END

    async def receive_password(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получаем пароль от пользователя и отправляем в Docker-контейнер"""
        password = update.message.text
        user_id = update.effective_user.id

        try:
            # Сохраняем пароль в контексте
            context.user_data["password"] = password

            # Отправляем пароль в Docker-контейнер
            response = requests.post(
                f"{API_BASE_URL}/auth/password", json={"password": password}
            )

            if response.status_code == 200:
                await update.message.reply_text(
                    "✅ Пароль успешно принят!\n\n"
                    "⏳ Выполняется аутентификация...\n\n"
                    "Пожалуйста, подождите..."
                )

                # Ждем немного и проверяем статус
                await asyncio.sleep(5)

                # Проверяем, не требуется ли код подтверждения
                auth_status = requests.get(f"{API_BASE_URL}/auth/status").json()

                if auth_status["auth_state"] == "waiting_code":
                    await update.message.reply_text(
                        "📧 На вашу почту отправлен код подтверждения.\n\n"
                        "🔢 Пожалуйста, введите код с вашей почты:"
                    )
                    return CODE
                elif auth_status["auth_state"] == "completed":
                    await update.message.reply_text(
                        "🎉 Аутентификация успешно завершена!\n\n"
                        "✅ Система готова к работе.\n\n"
                        "Теперь вы можете отправлять запросы к ChatGPT."
                    )
                    return READY
                else:
                    await update.message.reply_text(
                        f"Текущий статус: {auth_status['auth_state']}\n"
                        "Пожалуйста, подождите..."
                    )
                    # Продолжаем проверять статус
                    return await self._wait_for_auth_completion(update, context)

            else:
                error_msg = response.json().get("error", "Неизвестная ошибка")
                await update.message.reply_text(
                    f"❌ Ошибка при отправке пароля: {error_msg}\n\n"
                    "Пожалуйста, попробуйте еще раз или введите /start для перезапуска."
                )
                return ConversationHandler.END

        except Exception as e:
            logger.error(f"Ошибка при обработке пароля: {e}")
            await update.message.reply_text(
                "❌ Ошибка при обработке пароля. Пожалуйста, попробуйте еще раз или введите /start."
            )
            return ConversationHandler.END

    async def _wait_for_auth_completion(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Ожидает завершения аутентификации"""
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                auth_status = requests.get(f"{API_BASE_URL}/auth/status").json()

                if auth_status["auth_state"] == "waiting_code":
                    await update.message.reply_text(
                        "📧 На вашу почту отправлен код подтверждения.\n\n"
                        "🔢 Пожалуйста, введите код с вашей почты:"
                    )
                    return CODE
                elif auth_status["auth_state"] == "completed":
                    await update.message.reply_text(
                        "🎉 Аутентификация успешно завершена!\n\n"
                        "✅ Система готова к работе.\n\n"
                        "Теперь вы можете отправлять запросы к ChatGPT."
                    )
                    return READY

                await asyncio.sleep(2)  # Ждем 2 секунды перед следующей проверкой

            except Exception as e:
                logger.error(f"Ошибка при проверке статуса аутентификации: {e}")
                await asyncio.sleep(2)

        await update.message.reply_text(
            "❌ Таймаут ожидания аутентификации.\n\n"
            "Пожалуйста, попробуйте еще раз или введите /start для перезапуска."
        )
        return ConversationHandler.END

    async def receive_code(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получаем код подтверждения от пользователя и отправляем в Docker-контейнер"""
        code = update.message.text
        user_id = update.effective_user.id

        try:
            # Отправляем код подтверждения в Docker-контейнер
            response = requests.post(f"{API_BASE_URL}/auth/code", json={"code": code})

            if response.status_code == 200:
                await update.message.reply_text(
                    "✅ Код подтверждения принят!\n\n"
                    "⏳ Завершаем аутентификацию...\n\n"
                    "Пожалуйста, подождите..."
                )

                # Ждем завершения аутентификации
                await asyncio.sleep(3)

                # Проверяем статус
                auth_status = requests.get(f"{API_BASE_URL}/auth/status").json()

                if auth_status["auth_state"] == "completed":
                    await update.message.reply_text(
                        "🎉 Аутентификация успешно завершена!\n\n"
                        "✅ Система готова к работе.\n\n"
                        "Теперь вы можете отправлять запросы к ChatGPT."
                    )
                    return READY
                else:
                    await update.message.reply_text(
                        f"❌ Аутентификация не завершена. Текущий статус: {auth_status['auth_state']}\n\n"
                        "Пожалуйста, попробуйте еще раз или введите /start для перезапуска."
                    )
                    return ConversationHandler.END

            else:
                error_msg = response.json().get("error", "Неизвестная ошибка")
                await update.message.reply_text(
                    f"❌ Ошибка при отправке кода: {error_msg}\n\n"
                    "Пожалуйста, проверьте код и попробуйте еще раз."
                )
                return CODE

        except Exception as e:
            logger.error(f"Ошибка при обработке кода: {e}")
            await update.message.reply_text(
                "❌ Ошибка при обработке кода. Пожалуйста, попробуйте еще раз."
            )
            return CODE

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Обрабатывает обычные сообщения после аутентификации"""
        user_id = update.effective_user.id
        message_text = update.message.text

        # Проверяем статус аутентификации
        try:
            auth_status = requests.get(f"{API_BASE_URL}/auth/status").json()

            if auth_status["auth_state"] != "completed":
                await update.message.reply_text(
                    "❌ Система не аутентифицирована.\n\n"
                    "Пожалуйста, введите /start для начала аутентификации."
                )
                return

        except Exception as e:
            logger.error(f"Ошибка при проверке статуса аутентификации: {e}")
            await update.message.reply_text("❌ Ошибка подключения к сервису.")
            return

        # Отправляем запрос в Docker-контейнер
        try:
            await update.message.reply_text("⏳ Обрабатываю ваш запрос...")

            response = requests.post(
                f"{API_BASE_URL}/ask", json={"prompt": message_text}
            )

            if response.status_code == 200:
                answer = response.json().get("answer", "Ответ не получен")
                await update.message.reply_text(f"🤖 {answer}")
            else:
                error_msg = response.json().get("error", "Неизвестная ошибка")
                await update.message.reply_text(f"❌ Ошибка: {error_msg}")

        except Exception as e:
            logger.error(f"Ошибка при обработке запроса: {e}")
            await update.message.reply_text("❌ Ошибка при обработке запроса.")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отменяет текущую операцию"""
        await update.message.reply_text(
            "Операция отменена.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает текущий статус системы"""
        try:
            # Проверяем статус Docker-контейнера
            health_response = requests.get(f"{API_BASE_URL}/health")
            auth_response = requests.get(f"{API_BASE_URL}/auth/status")

            health_status = health_response.json()
            auth_status = auth_response.json()

            status_message = (
                "📊 **Статус системы:**\n\n"
                f"🟢 **Сервис:** {health_status.get('status', 'unknown')}\n"
                f"📊 **Очередь:** {health_status.get('queue_size', 0)} запросов\n"
                f"⚙️ **Обработка:** {'Да' if health_status.get('processing', False) else 'Нет'}\n\n"
                f"🔐 **Аутентификация:** {auth_status.get('auth_state', 'unknown')}\n"
                f"🌐 **Браузер:** {'Запущен' if auth_status.get('browser_initialized', False) else 'Не запущен'}"
            )

            await update.message.reply_text(status_message)

        except Exception as e:
            logger.error(f"Ошибка при получении статуса: {e}")
            await update.message.reply_text("❌ Ошибка при получении статуса системы.")

    def setup_handlers(self):
        """Настраивает обработчики команд"""
        # Conversation handler для аутентификации
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                EMAIL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_email)
                ],
                PASSWORD: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.receive_password
                    )
                ],
                CODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_code)
                ],
                READY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

        # Другие обработчики
        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler("status", self.status))

        # Обработчик для обычных сообщений (после аутентификации)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def run(self):
        """Запускает бота"""
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Настраиваем обработчики
        self.setup_handlers()

        # Запускаем бота
        logger.info("Запуск Telegram бота...")
        await self.application.run_polling()


def main():
    """Основная функция для запуска бота"""
    bot_manager = TelegramBotManager()

    # Запускаем бота с использованием asyncio.run()
    try:
        import asyncio

        asyncio.run(bot_manager.run())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    main()
