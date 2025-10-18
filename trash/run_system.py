#!/usr/bin/env python3
"""
Основной скрипт для запуска всей системы GPT Bridge
"""

import asyncio
import os
import signal
import subprocess
import sys

from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class SystemManager:
    def __init__(self):
        self.processes = []

    async def start_docker_container(self):
        """Запускает Docker-контейнер с основным сервисом"""
        print("🚀 Запуск Docker-контейнера...")

        try:
            # Проверяем, запущен ли уже контейнер
            result = subprocess.run(
                ["docker-compose", "ps"], capture_output=True, text=True
            )

            if (
                "gptbridge_progect-gptbridge-1" in result.stdout
                and "Up" in result.stdout
            ):
                print("✅ Docker-контейнер уже запущен")
                return True

            # Запускаем контейнер
            process = subprocess.Popen(
                ["docker-compose", "up", "-d"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Ждем завершения
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                print("✅ Docker-контейнер успешно запущен")

                # Ждем, пока сервис внутри контейнера запустится
                print("⏳ Ожидание запуска сервиса в контейнере...")
                await asyncio.sleep(10)

                return True
            else:
                print(f"❌ Ошибка при запуске Docker-контейнера: {stderr.decode()}")
                return False

        except Exception as e:
            print(f"❌ Ошибка при запуске Docker-контейнера: {e}")
            return False

    async def check_docker_status(self):
        """Проверяет статус Docker-контейнера"""
        try:
            import requests

            response = requests.get("http://localhost:8010/health", timeout=5)
            if response.status_code == 200:
                status = response.json()
                print(f"✅ Docker-контейнер работает: {status}")
                return True
            else:
                print(f"❌ Docker-контейнер не отвечает: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Ошибка при проверке Docker-контейнера: {e}")
            return False

    async def start_telegram_bot(self):
        """Запускает Telegram-бота"""
        print("🤖 Запуск Telegram-бота...")

        try:
            # Проверяем наличие токена
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            if not token:
                print("❌ TELEGRAM_BOT_TOKEN не установлен в .env файле")
                return False

            # Запускаем бота в отдельном процессе
            process = subprocess.Popen(
                [sys.executable, "telegram_bot_manager.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.processes.append(process)
            print("✅ Telegram-бот запущен")

            # Даем боту время на запуск
            await asyncio.sleep(3)

            return True

        except Exception as e:
            print(f"❌ Ошибка при запуске Telegram-бота: {e}")
            return False

    async def stop_system(self):
        """Останавливает всю систему"""
        print("\n🛑 Остановка системы...")

        # Останавливаем процессы
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()

        # Останавливаем Docker-контейнер
        try:
            subprocess.run(["docker-compose", "down"], capture_output=True)
            print("✅ Docker-контейнер остановлен")
        except Exception as e:
            print(f"❌ Ошибка при остановке Docker-контейнера: {e}")

        print("✅ Система остановлена")

    def signal_handler(self, sig, frame):
        """Обработчик сигналов для корректного завершения"""
        print(f"\n📡 Получен сигнал {sig}, останавливаем систему...")
        asyncio.create_task(self.stop_system())
        sys.exit(0)

    async def run(self):
        """Запускает всю систему"""
        print("=" * 50)
        print("🚀 ЗАПУСК СИСТЕМЫ GPT BRIDGE")
        print("=" * 50)

        # Настраиваем обработчики сигналов
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            # 1. Запускаем Docker-контейнер
            if not await self.start_docker_container():
                print("❌ Не удалось запустить Docker-контейнер")
                return

            # 2. Проверяем статус Docker-контейнера
            if not await self.check_docker_status():
                print("❌ Docker-контейнер не работает корректно")
                return

            # 3. Запускаем Telegram-бота
            if not await self.start_telegram_bot():
                print("❌ Не удалось запустить Telegram-бота")
                return

            print("\n" + "=" * 50)
            print("✅ СИСТЕМА УСПЕШНО ЗАПУЩЕНА")
            print("=" * 50)
            print("\n📋 Инструкция по использованию:")
            print("1. Откройте Telegram и найдите бота")
            print("2. Отправьте команду /start для начала аутентификации")
            print("3. Следуйте инструкциям бота для ввода email, пароля и кода")
            print("4. После аутентификации отправляйте запросы к ChatGPT")
            print("\n🛑 Для остановки системы нажмите Ctrl+C")
            print("=" * 50)

            # Бесконечный цикл для поддержания работы
            while True:
                await asyncio.sleep(1)

        except Exception as e:
            print(f"❌ Критическая ошибка при запуске системы: {e}")
            await self.stop_system()


async def main():
    """Основная функция"""
    system_manager = SystemManager()
    await system_manager.run()


if __name__ == "__main__":
    asyncio.run(main())
