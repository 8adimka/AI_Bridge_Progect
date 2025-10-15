from app.client.browser_client import BrowserClient
from app.server.api_server import start_api_server


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

    async def run(self):
        """Запускает сервис"""
        await self.initialize()
        # Запускаем API сервер, который вызывает handle_request
        start_api_server(self.handle_request)

    async def close(self):
        """Закрывает браузер"""
        await self.browser.close()
