import asyncio

from app.client.browser_client import BrowserClient


async def test_chatgpt():
    """Тестируем работу с ChatGPT напрямую"""
    browser = BrowserClient()
    try:
        await browser.initialize()
        await browser.open_chatgpt()

        # Тестируем отправку запроса
        response = await browser.send_and_get_answer("Hello, how are you?")
        print(f"Ответ от ChatGPT: {response}")

    except Exception as e:
        print(f"Ошибка при тестировании: {e}")
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_chatgpt())
