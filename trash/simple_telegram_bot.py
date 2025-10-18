#!/usr/bin/env python3
"""
Упрощенная версия Telegram-бота для управления аутентификацией
"""

import logging
import os

import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Базовый URL API Docker-контейнера
API_BASE_URL = "http://localhost:8011"

# Получаем токен бота из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")


def send_telegram_message(chat_id, text):
    """Отправляет сообщение через Telegram Bot API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Ошибка отправки сообщения: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        return False


def get_updates(offset=None):
    """Получает обновления от Telegram Bot API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    payload = {"timeout": 30}
    if offset:
        payload["offset"] = offset

    try:
        response = requests.post(url, json=payload, timeout=35)
        if response.status_code == 200:
            return response.json().get("result", [])
        else:
            logger.error(f"Ошибка получения обновлений: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Ошибка при получении обновлений: {e}")
        return []


def handle_start_command(chat_id):
    """Обрабатывает команду /start"""
    try:
        # Проверяем статус аутентификации в Docker-контейнере
        response = requests.get(f"{API_BASE_URL}/auth/status")
        auth_status = response.json()

        if auth_status["status"] == "completed":
            message = (
                "✅ Аутентификация уже завершена! Система готова к работе.\n\n"
                "Теперь вы можете отправлять запросы к ChatGPT."
            )
        elif (
            auth_status["status"] == "waiting_email"
            or auth_status["status"] == "not_authenticated"
        ):
            message = (
                "👋 Добро пожаловать в GPT Bridge Bot!\n\n"
                "Для начала работы необходимо пройти аутентификацию в ChatGPT.\n\n"
                "📧 Пожалуйста, введите ваш email/логин для ChatGPT:"
            )
        else:
            message = (
                f"Текущий статус аутентификации: {auth_status['status']}\n"
                "Пожалуйста, подождите или перезапустите систему."
            )

        send_telegram_message(chat_id, message)

    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {e}")
        send_telegram_message(
            chat_id,
            "❌ Ошибка подключения к сервису. Убедитесь, что Docker-контейнер запущен.",
        )


def handle_email_input(chat_id, email):
    """Обрабатывает ввод email"""
    try:
        # Отправляем email в Docker-контейнер
        response = requests.post(f"{API_BASE_URL}/auth/email", json={"email": email})

        if response.status_code == 200:
            message = (
                "✅ Email успешно принят!\n\n🔐 Теперь введите ваш пароль для ChatGPT:"
            )
        else:
            error_msg = response.json().get("error", "Неизвестная ошибка")
            message = f"❌ Ошибка при отправке email: {error_msg}"

        send_telegram_message(chat_id, message)

    except Exception as e:
        logger.error(f"Ошибка при обработке email: {e}")
        send_telegram_message(chat_id, "❌ Ошибка при обработке email.")


def handle_password_input(chat_id, password):
    """Обрабатывает ввод пароля"""
    try:
        # Отправляем пароль в Docker-контейнер
        response = requests.post(
            f"{API_BASE_URL}/auth/password", json={"password": password}
        )

        if response.status_code == 200:
            message = (
                "✅ Пароль успешно принят!\n\n"
                "⏳ Выполняется аутентификация...\n\n"
                "Пожалуйста, подождите..."
            )
            send_telegram_message(chat_id, message)

            # Ждем немного и проверяем статус
            import time

            time.sleep(5)

            # Проверяем, не требуется ли код подтверждения
            auth_status = requests.get(f"{API_BASE_URL}/auth/status").json()

            if auth_status["status"] == "waiting_code":
                send_telegram_message(
                    chat_id,
                    "📧 На вашу почту отправлен код подтверждения.\n\n"
                    "🔢 Пожалуйста, введите код с вашей почты:",
                )
            elif auth_status["status"] == "completed":
                send_telegram_message(
                    chat_id,
                    "🎉 Аутентификация успешно завершена!\n\n"
                    "✅ Система готова к работе.\n\n"
                    "Теперь вы можете отправлять запросы к ChatGPT.",
                )
            else:
                send_telegram_message(
                    chat_id,
                    f"Текущий статус: {auth_status['status']}\n"
                    "Пожалуйста, подождите...",
                )
        else:
            error_msg = response.json().get("error", "Неизвестная ошибка")
            send_telegram_message(
                chat_id, f"❌ Ошибка при отправке пароля: {error_msg}"
            )

    except Exception as e:
        logger.error(f"Ошибка при обработке пароля: {e}")
        send_telegram_message(chat_id, "❌ Ошибка при обработке пароля.")


def handle_code_input(chat_id, code):
    """Обрабатывает ввод кода подтверждения"""
    try:
        # Отправляем код подтверждения в Docker-контейнер
        response = requests.post(f"{API_BASE_URL}/auth/code", json={"code": code})

        if response.status_code == 200:
            message = (
                "✅ Код подтверждения принят!\n\n"
                "⏳ Завершаем аутентификацию...\n\n"
                "Пожалуйста, подождите..."
            )
            send_telegram_message(chat_id, message)

            # Ждем завершения аутентификации
            import time

            time.sleep(3)

            # Проверяем статус
            auth_status = requests.get(f"{API_BASE_URL}/auth/status").json()

            if auth_status["status"] == "completed":
                send_telegram_message(
                    chat_id,
                    "🎉 Аутентификация успешно завершена!\n\n"
                    "✅ Система готова к работе.\n\n"
                    "Теперь вы можете отправлять запросы к ChatGPT.",
                )
            else:
                send_telegram_message(
                    chat_id,
                    f"❌ Аутентификация не завершена. Текущий статус: {auth_status['status']}",
                )
        else:
            error_msg = response.json().get("error", "Неизвестная ошибка")
            send_telegram_message(chat_id, f"❌ Ошибка при отправке кода: {error_msg}")

    except Exception as e:
        logger.error(f"Ошибка при обработке кода: {e}")
        send_telegram_message(chat_id, "❌ Ошибка при обработке кода.")


def handle_chatgpt_request(chat_id, prompt):
    """Обрабатывает запрос к ChatGPT"""
    try:
        send_telegram_message(chat_id, "⏳ Обрабатываю ваш запрос...")

        # Отправляем запрос в Docker-контейнер
        response = requests.post(f"{API_BASE_URL}/ask", json={"prompt": prompt})

        if response.status_code == 200:
            answer = response.json().get("answer", "Ответ не получен")
            send_telegram_message(chat_id, f"🤖 {answer}")
        else:
            error_msg = response.json().get("error", "Неизвестная ошибка")
            send_telegram_message(chat_id, f"❌ Ошибка: {error_msg}")

    except Exception as e:
        logger.error(f"Ошибка при обработке запроса: {e}")
        send_telegram_message(chat_id, "❌ Ошибка при обработке запроса.")


def handle_status_command(chat_id):
    """Обрабатывает команду /status"""
    try:
        # Проверяем статус Docker-контейнера
        health_response = requests.get(f"{API_BASE_URL}/health")
        auth_response = requests.get(f"{API_BASE_URL}/auth/status")

        health_status = health_response.json()
        auth_status = auth_response.json()

        status_message = (
            "📊 **Статус системы:**\n\n"
            f"🟢 **Сервис:** {health_status.get('status', 'unknown')}\n"
            f"📊 **Очередь:** {health_status.get('queue_size', 0)} запросов\n"
            f"⚙️ **Обработка:** {'Да' if health_status.get('processing', False) else 'Нет'}\n\n"
            f"🔐 **Аутентификация:** {auth_status.get('status', 'unknown')}\n"
            f"🌐 **Браузер:** {'Запущен' if auth_status.get('browser_initialized', False) else 'Не запущен'}"
        )

        send_telegram_message(chat_id, status_message)

    except Exception as e:
        logger.error(f"Ошибка при получении статуса: {e}")
        send_telegram_message(chat_id, "❌ Ошибка при получении статуса системы.")


def process_message(chat_id, text):
    """Обрабатывает входящее сообщение"""
    # Проверяем команды
    if text == "/start":
        handle_start_command(chat_id)
    elif text == "/status":
        handle_status_command(chat_id)
    else:
        # Проверяем статус аутентификации
        try:
            auth_status = requests.get(f"{API_BASE_URL}/auth/status").json()

            # Определяем этап аутентификации по полям
            if not auth_status.get("email_provided", False):
                # Этап 1: Ввод email
                handle_email_input(chat_id, text)
            elif not auth_status.get("password_provided", False):
                # Этап 2: Ввод пароля
                handle_password_input(chat_id, text)
            elif (
                not auth_status.get("code_provided", False)
                and auth_status.get("status") == "waiting_code"
            ):
                # Этап 3: Ввод кода подтверждения
                handle_code_input(chat_id, text)
            elif auth_status["status"] == "completed":
                # Этап 4: Аутентификация завершена - обработка запросов
                handle_chatgpt_request(chat_id, text)
            else:
                send_telegram_message(
                    chat_id,
                    "❌ Система не готова к работе. Используйте /start для начала аутентификации.",
                )

        except Exception as e:
            logger.error(f"Ошибка при проверке статуса аутентификации: {e}")
            send_telegram_message(chat_id, "❌ Ошибка подключения к сервису.")


def main():
    """Основная функция для запуска бота"""
    logger.info("Запуск упрощенного Telegram-бота...")

    # Отправляем приветственное сообщение
    if TELEGRAM_CHAT_ID:
        send_telegram_message(
            TELEGRAM_CHAT_ID,
            "🤖 GPT Bridge Bot запущен!\n\n"
            "Используйте команду /start для начала аутентификации.",
        )

    last_update_id = None

    while True:
        try:
            updates = get_updates(last_update_id)

            for update in updates:
                update_id = update["update_id"]
                last_update_id = update_id + 1

                if "message" in update:
                    message = update["message"]
                    chat_id = message["chat"]["id"]
                    text = message.get("text", "")

                    if text:
                        logger.info(f"Получено сообщение от {chat_id}: {text}")
                        process_message(chat_id, text)

        except KeyboardInterrupt:
            logger.info("Бот остановлен пользователем")
            break
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
            import time

            time.sleep(5)  # Ждем перед повторной попыткой


if __name__ == "__main__":
    main()
