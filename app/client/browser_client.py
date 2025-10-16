import asyncio
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

            # Запрашиваем email у пользователя
            email = input("Введите ваш логин/email для доступа к аккаунту GPT: ")
            if not email:
                raise ValueError("Email не может быть пустым")

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
                    if continue_button:
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

            # Запрашиваем пароль у пользователя
            import getpass

            password = getpass.getpass("Введите пароль от вашего аккаунта: ")
            if not password:
                raise ValueError("Пароль не может быть пустым")

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

        # Проверяем, не требуется ли ввод кода подтверждения
        await self._handle_verification_code()

        print("Аутентификация успешно завершена")

    async def _handle_verification_code(self):
        """Обрабатывает ввод кода подтверждения с почты, если требуется"""
        if not self.page:
            return

        try:
            # Проверяем, появилось ли сообщение о необходимости ввода кода
            verification_selectors = [
                "input[type='text'][placeholder*='Code']",
                "input[type='text'][placeholder*='код']",
                "input[name='code']",
                "input[data-testid*='code']",
                "input[placeholder*='Enter code']",
                "input[placeholder*='Введите код']",
            ]

            code_input = None
            for selector in verification_selectors:
                try:
                    code_input = await self.page.wait_for_selector(
                        selector, timeout=5000
                    )
                    print(
                        f"Найдено поле для ввода кода подтверждения с селектором: {selector}"
                    )
                    break
                except:
                    continue

            if code_input:
                # Запрашиваем код подтверждения у пользователя
                verification_code = input(
                    "Введите ваш код подтверждения с вашей почты: "
                )
                if not verification_code:
                    print("Код подтверждения не введен, пропускаем")
                    return

                await code_input.fill(verification_code)
                print("Введен код подтверждения")
                await asyncio.sleep(1)

                # Ищем кнопку Continue для кода подтверждения
                continue_selectors = [
                    "button:has-text('Continue')",
                    "button:has-text('Продолжить')",
                    "button[type='submit']",
                    "button[data-testid*='continue']",
                ]

                continue_button = None
                for selector in continue_selectors:
                    try:
                        continue_button = await self.page.wait_for_selector(
                            selector, timeout=5000
                        )
                        print(
                            f"Найдена кнопка Continue для кода подтверждения с селектором: {selector}"
                        )
                        break
                    except:
                        continue

                if continue_button:
                    await continue_button.click()
                    print("Нажата кнопка Continue после кода подтверждения")
                    await asyncio.sleep(3)  # Ждем завершения проверки
                else:
                    print("Кнопка Continue не найдена, пробуем нажать Enter")
                    await code_input.press("Enter")
                    await asyncio.sleep(3)

        except Exception as e:
            print(f"Ошибка при обработке кода подтверждения: {e}")
            # Если не нашли поле для кода, значит он не требуется
            pass

    async def send_and_get_answer(self, prompt: str) -> str:
        """Отправляет запрос и получает ответ (исправленная версия)"""
        if not self.page:
            return "Ошибка: браузер не инициализирован"

        try:
            # Очищаем предыдущий ответ перед отправкой нового запроса
            await self._clear_previous_response()

            # Находим поле ввода
            input_element = await self._find_input_element()
            if not input_element:
                return "Ошибка: не найдено поле ввода"

            # Быстрая очистка и ввод
            await input_element.click()
            await input_element.fill("")
            await input_element.type(prompt, delay=10)  # Минимальная задержка

            # Отправка
            await input_element.press("Enter")
            print("Запрос отправлен, ожидаем ответ...")

            # ДОБАВЛЯЕМ ЗАДЕРЖКУ 5 СЕКУНД после отправки запроса
            print("Ждем 5 секунд перед началом проверки ответа...")
            await asyncio.sleep(5)

            # Ждем завершения генерации
            answer = await self._wait_for_response_complete()
            return answer

        except Exception as e:
            print(f"Ошибка при отправке запроса: {e}")
            return f"Ошибка: {str(e)}"

    async def _clear_previous_response(self):
        """Очищает область с предыдущим ответом для надежности"""
        try:
            # Прокручиваем к низу чтобы видеть поле ввода
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.1)
        except:
            pass

    async def _find_input_element(self):
        """Находит поле ввода сообщения"""
        input_selectors = [
            "textarea",
            "[contenteditable='true']",
            "[placeholder*='Ask']",
            "[placeholder*='Message']",
            "input[type='text']",
        ]

        for selector in input_selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=10000)
                print(f"Найдено поле ввода с селектором: {selector}")
                return element
            except:
                continue
        return None

    async def _wait_for_response_complete(self):
        """Ждет окончания генерации ответа и возвращает текст (оптимизированная версия)"""
        if not self.page:
            return "Ошибка: браузер не инициализирован"

        max_wait_time = 180
        start_time = time.time()
        last_answer = ""
        stable_count = 0  # Счетчик стабильных проверок
        required_stable = 2  # Требуется 2 стабильных проверки подряд

        print("Ожидаем завершения генерации ответа...")

        while time.time() - start_time < max_wait_time:
            try:
                # Получаем текущий текст ответа
                current_answer = await self._get_latest_assistant_message()

                if current_answer and current_answer != last_answer:
                    # Текст изменился - генерация продолжается
                    last_answer = current_answer
                    stable_count = 0
                    print(f"Получена часть ответа ({len(current_answer)} символов)")
                elif current_answer and current_answer == last_answer:
                    # Текст стабилен - увеличиваем счетчик
                    stable_count += 1
                    print(f"Ответ стабилен ({stable_count}/{required_stable})")

                    # Если текст стабилен в течение нескольких проверок - считаем завершенным
                    if stable_count >= required_stable:
                        print("Генерация ответа завершена!")
                        return current_answer
                else:
                    # Ответ еще не начался или не найден
                    stable_count = 0

                # Проверяем индикаторы typing как дополнительный сигнал
                is_typing = await self._is_chatgpt_typing()
                if not is_typing and current_answer and stable_count >= 1:
                    # Нет индикатора typing + есть ответ + одна стабильная проверка
                    print("Индикатор typing исчез, ответ готов!")
                    return current_answer

                # Увеличиваем интервал проверки в зависимости от состояния
                if not current_answer:
                    # Ответ еще не начался - проверяем реже
                    await asyncio.sleep(0.5)
                elif stable_count > 0:
                    # Ответ стабилен - проверяем реже
                    await asyncio.sleep(0.3)
                else:
                    # Активная генерация - проверяем чаще
                    await asyncio.sleep(0.2)

            except Exception as e:
                print(f"Ошибка при ожидании ответа: {e}")
                await asyncio.sleep(0.5)

        # Если вышли по таймауту, возвращаем последний найденный ответ
        return last_answer if last_answer else "Таймаут ожидания ответа"

    async def _get_latest_assistant_message(self):
        """Получает последнее сообщение ассистента"""
        if not self.page:
            return ""

        try:
            # Более надежные селекторы для сообщений ассистента
            assistant_selectors = [
                '[data-message-author-role="assistant"]',
                '[data-testid*="conversation-turn"]:last-child [data-message-author-role="assistant"]',
                '.group:has([data-message-author-role="assistant"])',
            ]

            for selector in assistant_selectors:
                try:
                    messages = await self.page.query_selector_all(selector)
                    if messages:
                        last_message = messages[-1]
                        text_content = await last_message.text_content()
                        if text_content and text_content.strip():
                            return text_content.strip()
                except:
                    continue

            return ""
        except Exception:
            return ""

    async def _is_chatgpt_typing(self):
        """Проверяет, показывает ли ChatGPT индикатор набора текста"""
        if not self.page:
            return False

        try:
            # Селекторы индикаторов typing
            typing_selectors = [
                '[data-testid*="typing"]',
                ".typing-indicator",
                '[class*="typing"]',
                '[aria-label*="typing"]',
                '[data-testid*="stop-button"]',  # Кнопка остановки генерации
            ]

            for selector in typing_selectors:
                elements = await self.page.query_selector_all(selector)
                # Проверяем видимость элементов
                for element in elements:
                    if await element.is_visible():
                        return True

            return False
        except Exception:
            return False

    async def close(self):
        """Закрывает браузер"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


# Пример использования
async def main():
    client = BrowserClient()
    try:
        await client.initialize()
        await client.open_chatgpt()

        # Тестовый запрос
        answer = await client.send_and_get_answer("Напиши короткий рассказ про кота")
        print("Ответ:", answer)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
