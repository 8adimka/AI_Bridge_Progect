import asyncio
import time
import uuid

import uvicorn
from fastapi import APIRouter, Body, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from services.request_queue import request_queue


def start_api_server(
    handle_request_func,
    get_auth_status_func=None,
    provide_verification_code_func=None,
):
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

    @app.get("/auth/status")
    async def auth_status():
        """Эндпоинт для проверки статуса аутентификации"""
        if not get_auth_status_func:
            return JSONResponse(
                status_code=501, content={"error": "Auth status not supported"}
            )

        try:
            status = await get_auth_status_func()
            return status
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Error getting auth status: {str(e)}"},
            )

    @app.post("/auth/code")
    async def auth_code(request: Request):
        """Эндпоинт для предоставления кода подтверждения"""
        if not provide_verification_code_func:
            return JSONResponse(
                status_code=501,
                content={"error": "Step-by-step authentication not supported"},
            )

        try:
            data = await request.json()
            code = data.get("code", "")

            if not code:
                return JSONResponse(
                    status_code=400, content={"error": "Verification code is required"}
                )

            success = await provide_verification_code_func(code)

            if success:
                return {
                    "status": "success",
                    "message": "Verification code provided successfully",
                }
            else:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Failed to provide verification code"},
                )

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Error providing verification code: {str(e)}"},
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

    class ChatMessage(BaseModel):
        role: str
        content: str

    class OpenAIChatRequest(BaseModel):
        model: str = Field(default="gpt-4-turbo")
        messages: list[ChatMessage]
        temperature: float = 0.7
        top_p: float = 1.0
        n: int = 1
        stream: bool = False

    router = APIRouter()

    @router.post("/v1/chat/completions")
    async def openai_chat_completions(req: OpenAIChatRequest = Body(...)):
        # Извлекаем system + user сообщение
        system_prompt = next(
            (m.content for m in req.messages if m.role == "system"), ""
        )
        user_message = next(
            (m.content for m in reversed(req.messages) if m.role == "user"), ""
        )
        full_prompt = (
            f"{system_prompt}\n{user_message}" if system_prompt else user_message
        )

        # Отправляем запрос в твою очередь
        future = asyncio.Future()
        await request_queue.add_request(full_prompt, lambda r: future.set_result(r))
        answer = await future

        # Рассчитываем usage
        prompt_tokens = len(full_prompt.split())
        completion_tokens = len(answer.split())

        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": answer},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    app.include_router(router)

    # Запускаем сервер
    config = uvicorn.Config(app, host="0.0.0.0", port=8010, log_level="info")
    server = uvicorn.Server(config)

    # Запускаем сервер в отдельной задаче
    asyncio.create_task(server.serve())
