import asyncio

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.request_queue import request_queue


def start_api_server(handle_request_func):
    app = FastAPI(title="GPT Bridge API", version="1.0.0")

    # Устанавливаем функцию обработки запросов в очереди
    request_queue.set_handle_request_func(handle_request_func)

    @app.post("/ask")
    async def ask_question(request: Request):
        try:
            data = await request.json()
            prompt = data.get("prompt", "")

            if not prompt:
                return JSONResponse(
                    status_code=400, content={"error": "Prompt is required"}
                )

            # Создаем Future для получения результата
            future = asyncio.Future()

            # Добавляем запрос в очередь
            await request_queue.add_request(
                prompt, lambda result: future.set_result(result)
            )

            # Ждем результат из очереди
            answer = await future

            return {"answer": answer}

        except Exception as e:
            return JSONResponse(
                status_code=500, content={"error": f"Internal server error: {str(e)}"}
            )

    @app.get("/health")
    async def health_check():
        queue_size = request_queue.get_queue_size()
        is_processing = request_queue.is_processing()
        return {
            "status": "healthy",
            "service": "GPT Bridge API",
            "queue_size": queue_size,
            "processing": is_processing,
        }

    # Запускаем сервер
    config = uvicorn.Config(app, host="0.0.0.0", port=8010, log_level="info")
    server = uvicorn.Server(config)

    # Запускаем сервер в отдельной задаче
    asyncio.create_task(server.serve())
