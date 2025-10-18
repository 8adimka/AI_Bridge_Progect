import asyncio

from services.chatgpt_bridge import ChatGPTBridgeService


async def main():
    print("🚀 Запуск GPT Bridge Service (Docker версия)...")

    # Инициализируем сервис ChatGPT
    chatgpt_service = ChatGPTBridgeService()

    try:
        # Запускаем только сервис ChatGPT с API сервером
        await chatgpt_service.run()

        # Держим программу запущенной
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал прерывания, завершаем работу...")
    except Exception as e:
        print(f"❌ Ошибка при запуске сервиса: {e}")
    finally:
        # Закрываем сервис
        await chatgpt_service.close()


if __name__ == "__main__":
    asyncio.run(main())
