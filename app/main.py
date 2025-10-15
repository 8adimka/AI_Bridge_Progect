import asyncio

from app.services.chatgpt_bridge import ChatGPTBridgeService


async def main():
    service = ChatGPTBridgeService()
    try:
        await service.run()
        # Держим программу запущенной
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
