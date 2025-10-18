#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы системы авторизации GPT Bridge
"""

import asyncio
import os
import sys

import requests

# Добавляем путь к outer_docker для импорта
sys.path.append(os.path.join(os.path.dirname(__file__), "outer"))

from outer.services.chatgpt_bridge import ChatGPTBridgeService


async def test_system():
    """Тестирует систему авторизации и работу API"""
    print("🧪 Тестирование системы GPT Bridge...")

    # Создаем сервис
    service = ChatGPTBridgeService()

    try:
        # Инициализируем сервис
        print("🔄 Инициализация сервиса...")
        await service.initialize()
        print("✅ Сервис инициализирован")

        # Начинаем авторизацию
        print("🔄 Начинаем процесс авторизации...")
        auth_started = await service.start_authentication()

        if auth_started:
            print("✅ Авторизация начата успешно!")

            # Проверяем статус авторизации
            auth_status = await service.get_auth_status()
            print(f"📊 Статус авторизации: {auth_status}")

            if auth_status.get("status") == "waiting_code":
                print("📧 Система ожидает код подтверждения с почты")
                print("🔗 Используйте API эндпоинт /auth/code для отправки кода")

                # Демонстрируем работу API
                print("\n🔗 API эндпоинты:")
                print("  GET  /health - проверка состояния сервиса")
                print("  GET  /auth/status - статус авторизации")
                print("  POST /auth/code - отправка кода подтверждения")
                print("  POST /ask - отправка запроса к ChatGPT")

                # Запускаем API сервер в фоновом режиме
                print("\n🚀 Запуск API сервера...")
                from outer.server.api_server import start_api_server

                start_api_server(
                    service.handle_request,
                    service.authenticate,
                    service.get_auth_status,
                    service.provide_email,
                    service.provide_password,
                    service.provide_verification_code,
                )

                print("✅ API сервер запущен на http://localhost:8010")
                print("\n📋 Инструкция для тестирования:")
                print("1. Проверьте почту и найдите код подтверждения")
                print("2. Отправьте код через API:")
                print(
                    '   curl -X POST http://localhost:8010/auth/code -H "Content-Type: application/json" -d \'{"code": "ВАШ_КОД"}\''
                )
                print("3. Проверьте статус авторизации:")
                print("   curl http://localhost:8010/auth/status")
                print("4. Отправьте тестовый запрос:")
                print(
                    '   curl -X POST http://localhost:8010/ask -H "Content-Type: application/json" -d \'{"prompt": "Привет, как дела?"}\''
                )

                # Ждем завершения
                print("\n⏳ Ожидаем завершения авторизации...")
                while True:
                    await asyncio.sleep(1)

            else:
                print(f"ℹ️ Текущий статус: {auth_status.get('status')}")

        else:
            print("❌ Ошибка при начале авторизации")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await service.close()


def test_api_endpoints():
    """Тестирует API эндпоинты"""
    print("\n🧪 Тестирование API эндпоинтов...")

    base_url = "http://localhost:8010"

    try:
        # Проверяем health endpoint
        print("🔍 Проверка /health...")
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print(f"✅ Health: {response.json()}")
        else:
            print(f"❌ Health error: {response.status_code}")

        # Проверяем auth status
        print("🔍 Проверка /auth/status...")
        response = requests.get(f"{base_url}/auth/status")
        if response.status_code == 200:
            auth_status = response.json()
            print(f"✅ Auth status: {auth_status}")
            return auth_status
        else:
            print(f"❌ Auth status error: {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("❌ API сервер не запущен")
        return None
    except Exception as e:
        print(f"❌ Ошибка при тестировании API: {e}")
        return None


async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования системы GPT Bridge")
    print("=" * 50)

    # Проверяем наличие переменных окружения
    email = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("PASSWORD")

    if not email or not password:
        print("❌ Переменные окружения не установлены")
        print("   Установите EMAIL_ADDRESS и PASSWORD в файле .env")
        return

    print(f"📧 Email: {email}")
    print(f"🔑 Пароль: {'*' * len(password)}")
    print()

    # Запускаем тестирование системы
    await test_system()


if __name__ == "__main__":
    asyncio.run(main())
