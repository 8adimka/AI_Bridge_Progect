import os

from services.chatgpt_bridge import ChatGPTBridgeService
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


class TelegramService:
    def __init__(self, chatgpt_service: ChatGPTBridgeService):
        self.chatgpt_service = chatgpt_service
        self.application = None
        self.user_states = {}  # Хранит состояние пользователей
        self.auth_data = {}  # Хранит данные аутентификации пользователей

        # Получаем токен бота из переменных окружения
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")

    async def run(self):
        """Запускает телеграм бота"""
        try:
            # Создаем приложение
            self.application = Application.builder().token(self.bot_token).build()

            # Добавляем обработчики
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("auth", self.auth_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )

            print("🤖 Телеграм бот запускается...")

            # Запускаем бота (run_polling сам управляет event loop)
            await self.application.run_polling()
        except Exception as e:
            print(f"❌ Ошибка при запуске телеграм бота: {e}")
            raise

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        await update.message.reply_text(
            "👋 Привет! Я бот для взаимодействия с ChatGPT.\n\n"
            "Доступные команды:\n"
            "/auth - начать аутентификацию\n"
            "/status - проверить статус аутентификации\n\n"
            "После аутентификации вы можете просто отправлять сообщения, и я передам их в ChatGPT."
        )

    async def auth_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /auth - начинает процесс аутентификации"""
        user_id = update.effective_user.id

        # Инициализируем состояние пользователя
        self.user_states[user_id] = "waiting_email"
        self.auth_data[user_id] = {"email": None, "password": None, "code": None}

        await update.message.reply_text(
            "🔐 Начинаем процесс аутентификации.\n\n"
            "Пожалуйста, введите ваш email для доступа к ChatGPT:"
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status - показывает статус аутентификации"""
        try:
            status = await self.chatgpt_service.get_auth_status()
            await update.message.reply_text(f"📊 Статус аутентификации: {status}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при получении статуса: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        message_text = update.message.text

        # Проверяем состояние пользователя
        user_state = self.user_states.get(user_id)

        if user_state == "waiting_email":
            # Получаем email
            self.auth_data[user_id]["email"] = message_text
            self.user_states[user_id] = "waiting_password"

            await update.message.reply_text(
                "✅ Email получен.\n\nТеперь введите ваш пароль:"
            )

        elif user_state == "waiting_password":
            # Получаем пароль
            self.auth_data[user_id]["password"] = message_text
            self.user_states[user_id] = "waiting_code_or_complete"

            # Пытаемся выполнить аутентификацию
            email = self.auth_data[user_id]["email"]
            password = self.auth_data[user_id]["password"]

            await update.message.reply_text(
                "🔄 Выполняю аутентификацию...\n\n"
                "Если потребуется код подтверждения с почты, я запрошу его."
            )

            # Выполняем аутентификацию
            success = await self.chatgpt_service.authenticate(email, password)

            if success:
                await update.message.reply_text(
                    "✅ Аутентификация успешна! Теперь вы можете отправлять запросы."
                )
                self.user_states[user_id] = "authenticated"
            else:
                await update.message.reply_text(
                    "❌ Аутентификация не удалась.\n"
                    "Возможно, требуется код подтверждения. Введите код с вашей почты:"
                )
                self.user_states[user_id] = "waiting_code"

        elif user_state == "waiting_code":
            # Получаем код подтверждения
            code = message_text
            email = self.auth_data[user_id]["email"]
            password = self.auth_data[user_id]["password"]

            await update.message.reply_text("🔄 Проверяю код подтверждения...")

            # Повторяем аутентификацию с кодом
            success = await self.chatgpt_service.authenticate(email, password, code)

            if success:
                await update.message.reply_text(
                    "✅ Аутентификация успешна! Теперь вы можете отправлять запросы."
                )
                self.user_states[user_id] = "authenticated"
            else:
                await update.message.reply_text(
                    "❌ Аутентификация не удалась даже с кодом.\n"
                    "Попробуйте начать заново командой /auth"
                )
                self.user_states[user_id] = None

        elif user_state == "authenticated":
            # Пользователь аутентифицирован - обрабатываем запрос к ChatGPT
            await update.message.reply_text("🔄 Обрабатываю ваш запрос...")

            try:
                answer = await self.chatgpt_service.handle_request(message_text)
                await update.message.reply_text(f"🤖 ChatGPT ответ:\n\n{answer}")
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка при обработке запроса: {e}")

        else:
            # Пользователь не в процессе аутентификации
            await update.message.reply_text(
                "Для начала работы выполните аутентификацию командой /auth\n\n"
                "После аутентификации вы сможете отправлять запросы напрямую."
            )

    async def close(self):
        """Закрывает телеграм бота"""
        if self.application:
            await self.application.shutdown()
