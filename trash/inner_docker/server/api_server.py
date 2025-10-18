import asyncio

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from services.request_queue import request_queue


def start_api_server(
    handle_request_func,
    authenticate_func=None,
    get_auth_status_func=None,
    provide_email_func=None,
    provide_password_func=None,
    provide_verification_code_func=None,
):
    app = FastAPI(title="GPT Bridge API (Docker)", version="1.0.0")

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

    @app.post("/auth")
    async def authenticate(request: Request):
        """Эндпоинт для аутентификации"""
        if not authenticate_func:
            return JSONResponse(
                status_code=501, content={"error": "Authentication not supported"}
            )

        try:
            data = await request.json()
            email = data.get("email", "")
            password = data.get("password", "")
            verification_code = data.get("verification_code", "")

            if not email or not password:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Email and password are required"},
                )

            success = await authenticate_func(
                email, password, verification_code or None
            )

            if success:
                return {"status": "success", "message": "Authentication successful"}
            else:
                return JSONResponse(
                    status_code=401, content={"error": "Authentication failed"}
                )

        except Exception as e:
            return JSONResponse(
                status_code=500, content={"error": f"Authentication error: {str(e)}"}
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

    @app.post("/auth/email")
    async def auth_email(request: Request):
        """Эндпоинт для предоставления email"""
        if not provide_email_func:
            return JSONResponse(
                status_code=501,
                content={"error": "Step-by-step authentication not supported"},
            )

        try:
            data = await request.json()
            email = data.get("email", "")

            if not email:
                return JSONResponse(
                    status_code=400, content={"error": "Email is required"}
                )

            success = await provide_email_func(email)

            if success:
                return {"status": "success", "message": "Email provided successfully"}
            else:
                return JSONResponse(
                    status_code=400, content={"error": "Failed to provide email"}
                )

        except Exception as e:
            return JSONResponse(
                status_code=500, content={"error": f"Error providing email: {str(e)}"}
            )

    @app.post("/auth/password")
    async def auth_password(request: Request):
        """Эндпоинт для предоставления пароля"""
        if not provide_password_func:
            return JSONResponse(
                status_code=501,
                content={"error": "Step-by-step authentication not supported"},
            )

        try:
            data = await request.json()
            password = data.get("password", "")

            if not password:
                return JSONResponse(
                    status_code=400, content={"error": "Password is required"}
                )

            success = await provide_password_func(password)

            if success:
                return {
                    "status": "success",
                    "message": "Password provided successfully",
                }
            else:
                return JSONResponse(
                    status_code=400, content={"error": "Failed to provide password"}
                )

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Error providing password: {str(e)}"},
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
            "service": "GPT Bridge API (Docker)",
            "queue_size": queue_size,
            "processing": is_processing,
        }

    # Запускаем сервер
    config = uvicorn.Config(app, host="0.0.0.0", port=8011, log_level="info")
    server = uvicorn.Server(config)

    # Запускаем сервер в отдельной задаче
    asyncio.create_task(server.serve())
