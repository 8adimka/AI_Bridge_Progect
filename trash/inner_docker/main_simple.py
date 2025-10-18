import asyncio

from dotenv import load_dotenv
from services.chatgpt_bridge import ChatGPTBridgeService
from services.telegram_service import TelegramService

# Загружаем переменные окружения
load_dotenv()


async def main():
    print("🚀 Запуск GPT Bridge Service (Docker версия)...")

    # Инициализируем сервисы
    chatgpt_service = ChatGPTBridgeService()
    telegram_service = TelegramService(chatgpt_service)

    try:
        # Запускаем только телеграм-бота
        print("🤖 Запускаем телеграм-бота...")
        await telegram_service.run()

    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал прерывания, завершаем работу...")
    except Exception as e:
        print(f"❌ Ошибка при запуске сервисов: {e}")
    finally:
        # Закрываем сервисы
        await chatgpt_service.close()
        await telegram_service.close()


if __name__ == "__main__":
    asyncio.run(main())
