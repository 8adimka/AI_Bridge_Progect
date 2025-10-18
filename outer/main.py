import asyncio

from services.chatgpt_bridge import ChatGPTBridgeService


async def main():
    service = ChatGPTBridgeService()
    try:
        await service.run()
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
