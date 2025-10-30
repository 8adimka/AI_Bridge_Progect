import asyncio
import os

from client.browser_client import BrowserClient
from server.api_server import start_api_server


class ChatGPTBridgeService:
    def __init__(self):
        self.browser = BrowserClient()
        self._initialized = False

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

    async def authenticate(self, email: str, password: str) -> bool:
        """Выполняет аутентификацию"""
        if not self._initialized:
            await self.initialize()

        # Устанавливаем данные для аутентификации
        await self.browser.set_auth_data(email=email, password=password)

        # Выполняем аутентификацию
        return await self.browser.perform_authentication()

    async def get_auth_status(self):
        """Возвращает статус аутентификации"""
        return await self.browser.get_auth_status()

    async def provide_email(self, email: str) -> bool:
        """Предоставляет email для пошаговой аутентификации"""
        if not self._initialized:
            await self.initialize()

        await self.browser.set_auth_data(email=email)
        return await self.browser._provide_email()

    async def provide_password(self, password: str) -> bool:
        """Предоставляет пароль для пошаговой аутентификации"""
        if not self._initialized:
            await self.initialize()

        await self.browser.set_auth_data(password=password)
        return await self.browser._provide_password()

    async def provide_verification_code(self, code: str) -> bool:
        """Предоставляет код подтверждения для пошаговой аутентификации"""
        if not self._initialized:
            await self.initialize()

        await self.browser.set_verification_code(code)
        success = await self.browser._handle_verification_code()
        # Проверяем статус авторизации после ввода кода
        auth_status = await self.browser.get_auth_status()
        if auth_status.get("status") == "completed":
            return True
        return success

    async def auto_authenticate(self):
        """Выполняет автоматическую аутентификацию с использованием данных из .env"""
        print("🔄 Выполняю автоматическую аутентификацию...")

        email = os.getenv("EMAIL_ADDRESS", "")
        password = os.getenv("PASSWORD", "")

        if not email or not password:
            print("❌ Email или пароль не установлены в переменных окружения")
            return False

        print(f"🔄 Выполняю автоматическую аутентификацию для: {email}")

        # Выполняем аутентификацию
        success = await self.authenticate(email, password)

        if success:
            print("✅ Автоматическая аутентификация успешно завершена!")
        else:
            print("❌ Автоматическая аутентификация не удалась")

        return success

    async def run(self):
        """Запускает сервис"""
        await self.initialize()
        print("✅ ChatGPT Bridge Service запущен и готов к работе")

        # Начинаем процесс авторизации (только до этапа получения кода)
        await self.start_authentication()

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

    async def start_authentication(self):
        """Начинает процесс авторизации и останавливается на этапе кода подтверждения"""
        print("🔄 Начинаю процесс авторизации...")

        email = os.getenv("EMAIL_ADDRESS", "")
        password = os.getenv("PASSWORD", "")

        if not email or not password:
            print("❌ Email или пароль не установлены в переменных окружения")
            return False

        print(f"🔄 Выполняю авторизацию для: {email}")

        # Устанавливаем данные для аутентификации
        await self.browser.set_auth_data(email=email, password=password)

        # Выполняем авторизацию до этапа кода подтверждения
        success = await self.browser.start_authentication_until_code()

        if success:
            print(
                "✅ Авторизация начата успешно! Ожидаем код подтверждения через API..."
            )
        else:
            print("❌ Ошибка при начале авторизации")

        return success

    async def close(self):
        """Закрывает браузер"""
        await self.browser.close()


async def main():
    service = ChatGPTBridgeService()
    try:
        await service.run()
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
