import asyncio
import uuid
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Request:
    id: str
    prompt: str
    callback: Callable[[str], None]
    created_at: float


class RequestQueue:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RequestQueue, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.queue = asyncio.Queue()
            self.processing = False
            self.current_request: Optional[Request] = None
            self.handle_request_func = None
            self._initialized = True

    def set_handle_request_func(self, handle_request_func):
        """Устанавливает функцию обработки запросов"""
        self.handle_request_func = handle_request_func

    async def add_request(self, prompt: str, callback: Callable[[str], None]) -> str:
        """Добавляет запрос в очередь и возвращает его ID"""
        request_id = str(uuid.uuid4())
        request = Request(
            id=request_id,
            prompt=prompt,
            callback=callback,
            created_at=asyncio.get_event_loop().time(),
        )

        print(f"Добавлен запрос в очередь: {prompt[:50]}... (ID: {request_id})")

        await self.queue.put(request)

        # Запускаем обработчик очереди, если он еще не запущен
        if not self.processing:
            asyncio.create_task(self._process_queue())

        return request_id

    async def _process_queue(self):
        """Обрабатывает очередь запросов строго последовательно"""
        self.processing = True
        print("Запущен обработчик очереди")

        try:
            while True:
                # Ждем следующий запрос из очереди
                request = await self.queue.get()
                self.current_request = request

                print(
                    f"Обрабатывается запрос: {request.prompt[:50]}... (ID: {request.id})"
                )

                try:
                    # Выполняем запрос
                    result = await self._execute_request(request.prompt)
                    print(f"Запрос обработан успешно: {request.id}")
                    request.callback(result)
                except Exception as e:
                    print(f"Ошибка при обработке запроса {request.id}: {e}")
                    request.callback(f"Ошибка обработки запроса: {str(e)}")
                finally:
                    # Помечаем задачу как выполненную
                    self.queue.task_done()
                    self.current_request = None

                    # Небольшая пауза между запросами для стабильности
                    await asyncio.sleep(1)

        except Exception as e:
            print(f"Критическая ошибка в обработчике очереди: {e}")
        finally:
            self.processing = False
            print("Обработчик очереди остановлен")

    async def _execute_request(self, prompt: str) -> str:
        """Выполняет запрос к ChatGPT через браузер"""
        if not self.handle_request_func:
            raise RuntimeError("Функция обработки запросов не установлена")

        return await self.handle_request_func(prompt)

    def get_queue_size(self) -> int:
        """Возвращает текущий размер очереди"""
        return self.queue.qsize()

    def is_processing(self) -> bool:
        """Проверяет, обрабатывается ли очередь в данный момент"""
        return self.processing

    def get_current_request(self) -> Optional[Request]:
        """Возвращает текущий обрабатываемый запрос"""
        return self.current_request


# Синглтон экземпляр
request_queue = RequestQueue()
