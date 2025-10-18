import asyncio
import os

from client.browser_client import BrowserClient
from server.api_server import start_api_server


class ChatGPTBridgeService:
    def __init__(self):
        self.browser = BrowserClient()
        self._initialized = False
        self._auth_data = {"email": "", "password": "", "verification_code": ""}

    async def initialize(self):
        """Асинхронная инициализация браузера"""
        if not self._initialized:
            await self.browser.initialize()
            await self.browser.open_chatgpt()
            self._initialized = True

    async def handle_request(self, prompt: str) -> str:
        """Обрабатывает запрос и возвращает ответ"""
        if not self._initialized:
            await self.initialize()

        return await self.browser.send_and_get_answer(prompt)

    async def authenticate(
        self, email: str, password: str, verification_code: str = None
    ) -> bool:
        """Выполняет аутентификацию с предоставленными данными"""
        try:
            if not self._initialized:
                await self.initialize()

            # Сохраняем данные для аутентификации
            self._auth_data = {
                "email": email,
                "password": password,
                "verification_code": verification_code,
            }

            # Передаем данные в браузер
            await self.browser.set_auth_data(email, password, verification_code)

            # Выполняем аутентификацию
            success = await self.browser.perform_authentication()
            return success

        except Exception as e:
            print(f"Ошибка при аутентификации: {e}")
            return False

    async def get_auth_status(self):
        """Возвращает статус аутентификации"""
        if not self._initialized:
            return {"status": "not_initialized"}

        return await self.browser.get_auth_status()

    async def provide_email(self, email: str) -> bool:
        """Предоставляет email для пошаговой аутентификации"""
        try:
            if not self._initialized:
                await self.initialize()

            self._auth_data["email"] = email
            await self.browser.set_auth_data(email, "", "")
            return await self.browser.provide_email(email)

        except Exception as e:
            print(f"Ошибка при предоставлении email: {e}")
            return False

    async def provide_password(self, password: str) -> bool:
        """Предоставляет пароль для пошаговой аутентификации"""
        try:
            if not self._initialized:
                await self.initialize()

            self._auth_data["password"] = password
            await self.browser.set_auth_data("", password, "")
            return await self.browser.provide_password(password)

        except Exception as e:
            print(f"Ошибка при предоставлении пароля: {e}")
            return False

    async def provide_verification_code(self, code: str) -> bool:
        """Предоставляет код подтверждения для пошаговой аутентификации"""
        try:
            if not self._initialized:
                await self.initialize()

            self._auth_data["verification_code"] = code
            await self.browser.set_auth_data("", "", code)
            return await self.browser.provide_verification_code(code)

        except Exception as e:
            print(f"Ошибка при предоставлении кода подтверждения: {e}")
            return False

    async def auto_authenticate(self):
        """Автоматическая аутентификация с использованием переменных окружения"""
        try:
            # Получаем email и пароль из переменных окружения
            email = os.getenv("EMAIL_ADDRESS")
            password = os.getenv("PASSWORD")

            if not email or not password:
                print(
                    "❌ Переменные окружения EMAIL_ADDRESS или PASSWORD не установлены"
                )
                return False

            print(f"🔄 Выполняю автоматическую аутентификацию для: {email}")

            # Выполняем аутентификацию
            success = await self.authenticate(email, password)

            if success:
                print("✅ Автоматическая аутентификация успешна!")
            else:
                print("❌ Автоматическая аутентификация не удалась")

            return success

        except Exception as e:
            print(f"❌ Ошибка при автоматической аутентификации: {e}")
            return False

    async def run(self):
        """Запускает сервис"""
        await self.initialize()
        print("✅ ChatGPT Bridge Service запущен и готов к работе")

        # Выполняем автоматическую аутентификацию с email и паролем из .env
        await self.auto_authenticate()

        # Запускаем API сервер, который вызывает handle_request
        start_api_server(
            self.handle_request,
            self.authenticate,
            self.get_auth_status,
            self.provide_email,
            self.provide_password,
            self.provide_verification_code,
        )

        # Бесконечный цикл для поддержания работы сервиса
        while True:
            await asyncio.sleep(1)

    async def close(self):
        """Закрывает браузер"""
        await self.browser.close()
