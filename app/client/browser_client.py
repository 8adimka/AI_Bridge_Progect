import asyncio
import os
import time

from dotenv import load_dotenv
from playwright.async_api import Page, async_playwright

# Загружаем переменные окружения из .env файла
load_dotenv()

CHATGPT_URL = "https://chatgpt.com/"
WAIT_TIMEOUT = 45000  # 45 секунд в миллисекундах для Playwright


class BrowserClient:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page: Page | None = None
        self.context = None

    async def initialize(self):
        """Инициализация браузера"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Показываем браузер для отладки
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=VizDisplayCompositor",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
            ],
        )

        # Создаем контекст с пользовательским агентом
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )

        self.page = await self.context.new_page()

        # Отключаем обнаружение автоматизации
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)

    async def open_chatgpt(self):
        """Открывает ChatGPT и ждет загрузки"""
        if not self.page:
            raise RuntimeError("Browser page is not initialized")

        await self.page.goto(CHATGPT_URL, wait_until="networkidle")

        # Ждем загрузки страницы
        await self.page.wait_for_load_state("networkidle")

        # Обрабатываем cookie-окно если оно появилось
        try:
            accept_button = await self.page.wait_for_selector(
                "button:has-text('Accept all'), button:has-text('Принять все')",
                timeout=5000,
            )
            await accept_button.click()
            print("Cookie-окно обработано")
            await asyncio.sleep(2)  # Ждем после клика
        except:
            print("Cookie-окно не найдено или уже обработано")

        # Выполняем аутентификацию
        await self._authenticate()

        # Пробуем разные селекторы для поля ввода
        selectors = [
            "textarea",
            "[data-testid='send-button']",
            "[placeholder*='Ask']",
            "[placeholder*='Message']",
            "[contenteditable='true']",
            ".prose",
        ]

        for selector in selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=10000)
                print(f"Найден элемент с селектором: {selector}")
                break
            except:
                continue
        else:
            # Если не нашли стандартные селекторы, попробуем найти любой интерактивный элемент
            try:
                await self.page.wait_for_selector(
                    "button, input, textarea", timeout=10000
                )
                print("Найден интерактивный элемент")
            except Exception as e:
                print(f"Ошибка при загрузке ChatGPT: {e}")
                # Сохраняем скриншот для отладки
                await self.page.screenshot(path="chatgpt_debug.png")
                raise

        print("ChatGPT успешно загружен и аутентифицирован")

    async def _authenticate(self):
        """Выполняет аутентификацию в ChatGPT"""
        if not self.page:
            raise RuntimeError("Browser page is not initialized")

        print("Начинаем процесс аутентификации...")

        # Ищем кнопку Log In
        login_selectors = [
            "button:has-text('Log in')",
            "button:has-text('Войти')",
            "a:has-text('Log in')",
            "a:has-text('Войти')",
            "[data-testid='mobile-login-button']",
            "[data-testid='login-button']",
            "button[type='button']:has-text('Log in')",
            "button[type='button']:has-text('Войти')",
        ]

        login_button = None
        for selector in login_selectors:
            try:
                login_button = await self.page.wait_for_selector(selector, timeout=5000)
                print(f"Найдена кнопка Log In с селектором: {selector}")
                break
            except:
                continue

        if login_button:
            await login_button.click()
            print("Нажата кнопка Log In")
            await asyncio.sleep(3)  # Ждем загрузки страницы аутентификации
        else:
            print(
                "Кнопка Log In не найдена. Возможно, пользователь уже аутентифицирован"
            )
            return

        # Вводим email на странице аутентификации
        try:
            email_input = await self.page.wait_for_selector(
                "input[type='email'], input[name='email'], input[placeholder*='email'], input[placeholder*='Email']",
                timeout=10000,
            )
            email = os.getenv("EMAIL_ADDRESS")
            if not email:
                raise ValueError("EMAIL_ADDRESS не найден в переменных окружения")

            await email_input.fill(email)
            print("Введен email")
            await asyncio.sleep(1)

            # Ищем кнопку Continue под полем ввода email
            continue_selectors = [
                "button[type='submit']:has-text('Continue')",
                "button[type='submit']:has-text('Продолжить')",
                "button:has-text('Continue'):not(:has-text('Google'))",
                "button:has-text('Продолжить'):not(:has-text('Google'))",
                "[data-testid*='continue']",
                "[data-action*='continue']",
                "[id*='continue']",
                "[class*='continue']",
                "button:has-text('Continue')",
                "button:has-text('Продолжить')",
                "button[type='submit']",
            ]

            continue_button = None
            for selector in continue_selectors:
                try:
                    continue_button = await self.page.wait_for_selector(
                        selector, timeout=3000
                    )
                    # Проверяем, что кнопка видима и кликабельна
                    is_visible = await continue_button.is_visible()
                    is_enabled = await continue_button.is_enabled()
                    if is_visible and is_enabled:
                        print(f"Найдена кнопка Continue с селектором: {selector}")
                        break
                    else:
                        continue_button = None
                except:
                    continue

            if continue_button:
                await continue_button.click()
                print("Нажата кнопка Continue после email")
                await asyncio.sleep(3)  # Ждем загрузки страницы пароля
            else:
                print("Кнопка Continue не найдена или не кликабельна")
                return
        except Exception as e:
            print(f"Ошибка при вводе email: {e}")
            return

        # Вводим пароль
        try:
            # Добавляем больше селекторов для поиска поля пароля
            password_selectors = [
                "input[type='password']:not([aria-hidden])",
                "input[name='password']:not([aria-hidden])",
                "input[placeholder*='password']",
                "input[placeholder*='пароль']",
                "input[data-testid*='password']",
                "input[jsname*='password']",
                "input[autocomplete='current-password']",
                "input[type='password'][tabindex='0']",
                "input[type='password']:visible",
            ]

            password_input = None
            for selector in password_selectors:
                try:
                    password_input = await self.page.wait_for_selector(
                        selector, timeout=5000
                    )
                    print(f"Найдено поле пароля с селектором: {selector}")
                    break
                except:
                    continue

            if not password_input:
                # Если не нашли стандартными селекторами, попробуем найти по XPath
                try:
                    password_input = await self.page.wait_for_selector(
                        "xpath=//input[@type='password' and not(@aria-hidden='true')]",
                        timeout=5000,
                    )
                    print("Найдено поле пароля через XPath")
                except:
                    raise Exception("Не удалось найти поле ввода пароля")

            password = os.getenv("PASSWORD")
            if not password:
                raise ValueError("PASSWORD не найден в переменных окружения")

            await password_input.fill(password)
            print("Введен пароль")
            await asyncio.sleep(1)

            # Ищем кнопку Continue для пароля
            continue_selectors = [
                "button:has-text('Continue')",
                "button:has-text('Продолжить')",
                "button[type='submit']",
                "button[data-testid*='continue']",
                "button[jsname*='submit']",
            ]

            continue_button = None
            for selector in continue_selectors:
                try:
                    continue_button = await self.page.wait_for_selector(
                        selector, timeout=5000
                    )
                    print(f"Найдена кнопка Continue с селектором: {selector}")
                    break
                except:
                    continue

            if continue_button:
                await continue_button.click()
                print("Нажата кнопка Continue после пароля")
                await asyncio.sleep(5)  # Ждем завершения аутентификации
            else:
                print("Кнопка Continue не найдена, пробуем нажать Enter")
                await password_input.press("Enter")
                await asyncio.sleep(5)

        except Exception as e:
            print(f"Ошибка при вводе пароля: {e}")
            return

        print("Аутентификация успешно завершена")

    async def send_and_get_answer(self, prompt: str) -> str:
        """Отправляет запрос и получает ответ"""
        if not self.page:
            return "Ошибка: браузер не инициализирован"

        try:
            # Пробуем разные селекторы для поля ввода
            input_selectors = [
                "textarea",
                "[contenteditable='true']",
                "[placeholder*='Ask']",
                "[placeholder*='Message']",
                "input[type='text']",
            ]

            input_element = None
            for selector in input_selectors:
                try:
                    input_element = await self.page.wait_for_selector(
                        selector, timeout=10000
                    )
                    print(f"Найдено поле ввода с селектором: {selector}")
                    break
                except:
                    continue

            if not input_element:
                return "Ошибка: не найдено поле ввода"

            # Очищаем поле и вводим текст - используем простой надежный метод
            await input_element.click()
            await asyncio.sleep(1)  # Ждем активации поля

            # Очищаем поле стандартным способом
            await input_element.fill("")
            await asyncio.sleep(0.5)

            # Вводим текст с задержкой для имитации человеческого ввода
            await input_element.type(prompt, delay=50)
            await asyncio.sleep(0.5)

            # Отправляем запрос (пробуем разные способы)
            try:
                await input_element.press("Enter")
            except:
                # Если Enter не работает, ищем кнопку отправки
                try:
                    send_button = await self.page.wait_for_selector(
                        "[data-testid='send-button'], button[type='submit'], button:has-text('Send')",
                        timeout=5000,
                    )
                    await send_button.click()
                except:
                    # Если кнопка не найдена, просто ждем
                    await asyncio.sleep(2)

            # Ждем начала генерации ответа
            await self._wait_for_response_start()

            # Ждем окончания генерации
            answer = await self._wait_for_response_complete()

            return answer

        except Exception as e:
            print(f"Ошибка при отправке запроса: {e}")
            return f"Ошибка: {str(e)}"

    async def _wait_for_response_start(self):
        """Ждет начала генерации ответа"""
        if not self.page:
            return

        try:
            # Ждем появления индикатора генерации
            await self.page.wait_for_selector(
                '[data-testid*="typing"]', timeout=WAIT_TIMEOUT
            )
        except:
            # Если индикатор не найден, просто ждем немного
            await asyncio.sleep(2)

    async def _wait_for_response_complete(self):
        """Ждет окончания генерации ответа и возвращает текст"""
        if not self.page:
            return "Ошибка: браузер не инициализирован"

        max_wait_time = 120  # Максимальное время ожидания в секундах
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                # Проверяем, что генерация завершена (нет индикатора typing)
                typing_indicators = await self.page.query_selector_all(
                    '[data-testid*="typing"], .typing-indicator, [class*="typing"]'
                )

                if not typing_indicators:
                    # Ищем ответы ChatGPT разными способами
                    answer_selectors = [
                        '[data-testid*="conversation-turn"] [data-message-author-role="assistant"]',
                        '[data-message-author-role="assistant"]',
                        ".markdown.prose",
                        '[class*="message"]:not([data-message-author-role="user"])',
                        ".result-streaming",
                        ".whitespace-pre-wrap",
                    ]

                    for selector in answer_selectors:
                        try:
                            messages = await self.page.query_selector_all(selector)
                            if messages:
                                last_message = messages[-1]
                                text_content = await last_message.text_content()
                                if text_content and text_content.strip():
                                    print(f"Найден ответ с селектором: {selector}")
                                    return text_content.strip()
                        except:
                            continue

                    # Альтернативный способ: ищем последний добавленный элемент
                    all_elements = await self.page.query_selector_all("div, p, span")
                    if all_elements:
                        # Берем последние несколько элементов и проверяем их текст
                        for element in reversed(all_elements[-10:]):
                            try:
                                text_content = await element.text_content()
                                if (
                                    text_content and len(text_content.strip()) > 10
                                ):  # Минимальная длина ответа
                                    print("Найден ответ через альтернативный метод")
                                    return text_content.strip()
                            except:
                                continue

                await asyncio.sleep(1)

            except Exception as e:
                print(f"Ошибка при ожидании ответа: {e}")
                await asyncio.sleep(1)

        return "Таймаут ожидания ответа"

    async def close(self):
        """Закрывает браузер"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
