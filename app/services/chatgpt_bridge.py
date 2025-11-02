import asyncio
import os
import time
from typing import Optional

from client.browser_client import BrowserClient
from server.api_server import start_api_server


class ChatGPTBridgeService:
    def __init__(self):
        self.browser = BrowserClient()
        self._initialized = False
        self._restart_count = 0
        self._max_restarts = 3
        self._last_restart_time = 0
        self._restart_cooldown = 60  # 60 секунд между перезапусками

    async def initialize(self):
        """Асинхронная инициализация браузера"""
        if not self._initialized:
            # Пытаемся восстановить сессию
            session_restored = await self.browser.initialize_with_session()
            
            if session_restored:
                print("✅ Сессия успешно восстановлена")
                self._initialized = True
            else:
                # Если сессия не восстановлена, выполняем полную инициализацию
                # Браузер уже инициализирован в initialize_with_session()
                self._initialized = True

    async def handle_request(self, prompt: str) -> str:
        """Обрабатывает запрос и возвращает ответ с автоматическим перезапуском при ошибках"""
        if not self._initialized:
            await self.initialize()

        try:
            # Используем метод с переподключением
            result = await self.browser.send_and_get_answer_with_reconnect(prompt)
            
            # Проверяем результат на ошибки, требующие перезапуска
            if self._should_restart(result):
                await self._restart_service("Ошибка в ответе браузера")
                # Повторяем запрос после перезапуска
                result = await self.browser.send_and_get_answer_with_reconnect(prompt)
            
            return result
            
        except Exception as e:
            print(f"❌ Критическая ошибка при обработке запроса: {e}")
            await self._restart_service(f"Исключение: {str(e)}")
            
            # Повторяем запрос после перезапуска
            return await self.browser.send_and_get_answer_with_reconnect(prompt)

    async def get_auth_status(self):
        """Возвращает статус аутентификации"""
        return await self.browser.get_auth_status()

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

    async def run(self):
        """Запускает сервис"""
        await self.initialize()
        print("✅ ChatGPT Bridge Service запущен и готов к работе")

        # Проверяем статус аутентификации
        auth_status = await self.get_auth_status()
        
        # Запускаем авторизацию только если сессия не восстановлена
        if auth_status.get("status") != "completed":
            await self.start_authentication()

        # Запускаем API сервер, который вызывает handle_request
        start_api_server(
            self.handle_request,
            self.get_auth_status,
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

    def _should_restart(self, result: str) -> bool:
        """Определяет, требуется ли перезапуск сервиса на основе результата"""
        critical_errors = [
            "Ошибка: браузер не инициализирован",
            "Таймаут ожидания ответа",
            "Не удалось выполнить запрос после всех попыток",
            "Ошибка обработки запроса",
            "❌ Не удалось выполнить запрос после всех попыток"
        ]
        
        return any(error in result for error in critical_errors)

    async def _restart_service(self, reason: str):
        """Перезапускает сервис с проверкой лимитов"""
        current_time = time.time()
        
        # Проверяем кулдаун между перезапусками
        if current_time - self._last_restart_time < self._restart_cooldown:
            print(f"⚠️ Слишком частый перезапуск, пропускаем (кулдаун: {self._restart_cooldown}с)")
            return
        
        # Проверяем максимальное количество перезапусков
        if self._restart_count >= self._max_restarts:
            print(f"❌ Достигнут лимит перезапусков ({self._max_restarts}). Сервис остановлен.")
            raise RuntimeError(f"Достигнут лимит перезапусков: {reason}")
        
        self._restart_count += 1
        self._last_restart_time = current_time
        
        print(f"🔄 Перезапуск сервиса ({self._restart_count}/{self._max_restarts}) по причине: {reason}")
        
        # Закрываем текущий браузер
        await self.browser.close()
        
        # Сбрасываем состояние
        self._initialized = False
        self.browser = BrowserClient()
        
        # Переинициализируем
        await self.initialize()
        
        # Если требуется авторизация, запускаем её
        auth_status = await self.browser.get_auth_status()
        if auth_status.get("status") != "completed":
            await self.start_authentication()
        
        print("✅ Сервис успешно перезапущен")

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
