import asyncio
from typing import Callable, Optional


class RequestQueue:
    def __init__(self):
        self._queue = asyncio.Queue()
        self._processing = False
        self._handle_request_func: Optional[Callable] = None
        self._current_task = None

    def set_handle_request_func(self, func: Callable):
        """Устанавливает функцию обработки запросов"""
        self._handle_request_func = func

    async def add_request(self, prompt: str, callback: Callable):
        """Добавляет запрос в очередь"""
        await self._queue.put((prompt, callback))

        # Запускаем обработку очереди, если она еще не запущена
        if not self._processing:
            self._processing = True
            self._current_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        """Обрабатывает очередь запросов"""
        while not self._queue.empty() or self._processing:
            try:
                # Получаем запрос из очереди
                prompt, callback = await self._queue.get()

                if self._handle_request_func:
                    try:
                        # Обрабатываем запрос
                        result = await self._handle_request_func(prompt)
                        # Вызываем callback с результатом
                        callback(result)
                    except Exception as e:
                        # В случае ошибки возвращаем сообщение об ошибке
                        callback(f"Ошибка при обработке запроса: {str(e)}")
                else:
                    callback("Ошибка: функция обработки запросов не установлена")

                # Помечаем задачу как выполненную
                self._queue.task_done()

            except Exception as e:
                print(f"Ошибка при обработке очереди: {e}")
                await asyncio.sleep(1)

        # Когда очередь пуста, останавливаем обработку
        self._processing = False

    def get_queue_size(self) -> int:
        """Возвращает размер очереди"""
        return self._queue.qsize()

    def is_processing(self) -> bool:
        """Возвращает статус обработки"""
        return self._processing

    async def wait_until_empty(self):
        """Ждет, пока очередь не станет пустой"""
        await self._queue.join()


# Глобальный экземпляр очереди
request_queue = RequestQueue()
