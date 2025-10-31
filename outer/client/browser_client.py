import asyncio
import os
from typing import Optional

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
        self.auth_data = {
            "email": os.getenv("EMAIL_ADDRESS", ""),
            "password": os.getenv("PASSWORD", ""),
            "verification_code": "",
        }
        self.auth_status = {
            "status": "not_authenticated",
            "email_provided": False,
            "password_provided": False,
            "code_provided": False,
            "browser_initialized": False,
        }

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

        self.auth_status["browser_initialized"] = True

    async def open_chatgpt(self):
        """Открывает ChatGPT и ждет загрузки"""
        if not self.page:
            raise RuntimeError("Browser page is not initialized")

        await self.page.goto(CHATGPT_URL, wait_until="networkidle")

        # Ждем загрузки страницы
        await self.page.wait_for_load_state("networkidle")

        # Обрабатываем все возможные всплывающие окна
        await self._handle_popups()

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
                await self.page.wait_for_selector(selector, timeout=3000)
                print(f"Найден элемент с селектором: {selector}")
                break
            except Exception:
                continue
        else:
            # Если не нашли стандартные селекторы, попробуем найти любой интерактивный элемент
            try:
                await self.page.wait_for_selector(
                    "button, input, textarea", timeout=3000
                )
                print("Найден интерактивный элемент")
            except Exception as e:
                print(f"Ошибка при загрузке ChatGPT: {e}")
                # Сохраняем скриншот для отладки
                await self.page.screenshot(path="chatgpt_debug.png")
                raise

        print("ChatGPT успешно загружен")

    async def _handle_popups(self):
        """Обрабатывает все возможные всплывающие окна, включая кнопки Enable и крестики"""
        if not self.page:
            return

        print("Проверяем наличие всплывающих окон...")

        # Список селекторов для различных типов всплывающих окон (с приоритетом)
        popup_selectors = [
            # Cookie и согласия (высший приоритет)
            "button:has-text('Accept all')",
            "button:has-text('Принять все')",
            "button:has-text('Accept cookies')",
            "button:has-text('Принять cookies')",
            "button:has-text('I agree')",
            "button:has-text('Я согласен')",
            # Кнопки Enable и активации
            "button:has-text('Enable')",
            "button:has-text('Включить')",
            "button:has-text('Activate')",
            "button:has-text('Активировать')",
            "button:has-text('Allow')",
            "button:has-text('Разрешить')",
            "button:has-text('Accept')",
            "button:has-text('Принять')",
            "button:has-text('Agree')",
            "button:has-text('Согласиться')",
            # Кнопки закрытия (крестики)
            "button[aria-label*='close']",
            "button[aria-label*='закрыть']",
            "button[title*='close']",
            "button[title*='закрыть']",
            "[data-testid*='close']",
            "button:has-text('×')",
            "button:has-text('✕')",
            "button:has-text('X')",
            # Другие кнопки
            "button:has-text('Got it')",
            "button:has-text('Понятно')",
            "button:has-text('OK')",
            "button:has-text('ОК')",
            "button:has-text('Dismiss')",
            "button:has-text('Отклонить')",
            "button:has-text('Not now')",
            "button:has-text('Не сейчас')",
            "button:has-text('Later')",
            "button:has-text('Позже')",
        ]

        handled_popups = 0
        max_attempts = 2  # Уменьшено количество попыток

        for attempt in range(max_attempts):
            popup_found = False

            for selector in popup_selectors:
                try:
                    # Ищем элемент с очень коротким таймаутом
                    element = await self.page.wait_for_selector(selector, timeout=500)

                    if element:
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()

                        if is_visible and is_enabled:
                            print(f"Найдено всплывающее окно с селектором: {selector}")

                            # Кликаем на элемент
                            await element.click()
                            print(f"Нажата кнопка: {selector}")
                            handled_popups += 1
                            popup_found = True

                            # Короткая пауза после клика
                            await asyncio.sleep(0.3)

                            # Прерываем цикл по селекторам и начинаем заново
                            break

                except Exception:
                    # Игнорируем ошибки поиска элементов
                    continue

            # Если в этой попытке не нашли поп-апов, выходим
            if not popup_found:
                break

        if handled_popups > 0:
            print(f"✅ Обработано всплывающих окон: {handled_popups}")
        else:
            print("ℹ️ Всплывающие окна не найдены")

    async def _provide_email(self):
        if not self.page:
            raise RuntimeError("Browser page is not initialized")

        """Вводит email на странице аутентификации"""
        try:
            email_input = await self.page.wait_for_selector(
                "input[type='email'], input[name='email'], input[placeholder*='email'], input[placeholder*='Email']",
                timeout=10000,
            )

            if not self.auth_data["email"] or not email_input:
                print("❌ Email не установлен")
                return False

            await email_input.fill(self.auth_data["email"])
            print("✅ Введен email")
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
                            print(
                                f"✅ Найдена кнопка Continue с селектором: {selector}"
                            )
                            break
                        else:
                            continue_button = None
                except Exception:
                    continue

            if continue_button:
                await continue_button.click()
                print("✅ Нажата кнопка Continue после email")
                await asyncio.sleep(1)
                self.auth_status["email_provided"] = True
                return True
            else:
                print("❌ Кнопка Continue не найдена или не кликабельна")
                return False

        except Exception as e:
            print(f"❌ Ошибка при вводе email: {e}")
            return False

    async def _provide_password(self):
        """Вводит пароль на странице аутентификации"""
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

            if not self.page:
                print("❌ Page object is not initialized")
                return False

            for selector in password_selectors:
                try:
                    password_input = await self.page.wait_for_selector(
                        selector, timeout=3000
                    )
                    print(f"✅ Найдено поле пароля с селектором: {selector}")
                    break
                except Exception:
                    continue

            if not password_input:
                # Если не нашли стандартными селекторами, попробуем найти по XPath
                try:
                    password_input = await self.page.wait_for_selector(
                        "xpath=//input[@type='password' and not(@aria-hidden='true')]",
                        timeout=3000,
                    )
                    print("✅ Найдено поле пароля через XPath")
                except Exception:
                    print("❌ Не удалось найти поле ввода пароля")
                    return False

            if not self.auth_data["password"] or not password_input:
                print("❌ Пароль не установлен")
                return False

            await password_input.fill(self.auth_data["password"])
            print("✅ Введен пароль")
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
                        selector, timeout=3000
                    )
                    print(f"✅ Найдена кнопка Continue с селектором: {selector}")
                    break
                except Exception:
                    continue

            if continue_button:
                await continue_button.click()
                print("✅ Нажата кнопка Continue после пароля")
                await asyncio.sleep(5)  # Ждем завершения аутентификации
            else:
                print("❌ Кнопка Continue не найдена, пробуем нажать Enter")
                await password_input.press("Enter")
                await asyncio.sleep(5)

            self.auth_status["password_provided"] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка при вводе пароля: {e}")
            return False

    async def _handle_verification_code(self):
        """Обрабатывает ввод кода подтверждения с почты, если требуется"""
        if not self.page:
            return False

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
                        selector, timeout=3000
                    )
                    print(
                        f"✅ Найдено поле для ввода кода подтверждения с селектором: {selector}"
                    )
                    break
                except Exception:
                    continue

            if code_input:
                if not self.auth_data["verification_code"]:
                    print("ℹ️ Требуется код подтверждения, но он не установлен")
                    self.auth_status["status"] = "waiting_code"
                    return False

                await code_input.fill(self.auth_data["verification_code"])
                print("✅ Введен код подтверждения")
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
                            f"✅ Найдена кнопка Continue для кода подтверждения с селектором: {selector}"
                        )
                        break
                    except Exception:
                        continue

                if continue_button:
                    await continue_button.click()
                    print("✅ Нажата кнопка Continue после кода подтверждения")
                    await asyncio.sleep(5)  # Ждем завершения проверки
                else:
                    print("❌ Кнопка Continue не найдена, пробуем нажать Enter")
                    await code_input.press("Enter")
                    await asyncio.sleep(5)

                self.auth_status["code_provided"] = True
                self.auth_status["status"] = "completed"
                print("✅ Код подтверждения успешно обработан, авторизация завершена!")
                return True

            # Если поле для кода не найдено, значит код не требуется
            return True

        except Exception as e:
            print(f"ℹ️ Ошибка при обработке кода подтверждения: {e}")
            return False

    async def set_verification_code(self, code: str):
        """Устанавливает код подтверждения для аутентификации"""
        self.auth_data["verification_code"] = code

    async def set_auth_data(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        verification_code: Optional[str] = None,
    ):
        """Устанавливает данные для аутентификации"""
        if email is not None:
            self.auth_data["email"] = email
        if password is not None:
            self.auth_data["password"] = password
        if verification_code is not None:
            self.auth_data["verification_code"] = verification_code

    async def start_authentication_until_code(self):
        """Выполняет авторизацию до этапа получения кода подтверждения"""
        print("🔄 Начинаю авторизацию до этапа кода подтверждения...")

        if not self.auth_data["email"] or not self.auth_data["password"]:
            print("❌ Email или пароль не установлены")
            return False

        try:
            # Ищем кнопку Log In
            login_selectors = [
                "button:has-text('Log in')",
                "button:has-text('Войти')",
                "a:has-text('Log in')",
                "a:has-text('Войти')",
                "[data-testid='mobile-login-button']",
                "[data-testid='login-button']",
            ]

            login_button = None

            if not self.page:
                print("❌ Page object is not initialized")
                return False

            for selector in login_selectors:
                try:
                    login_button = await self.page.wait_for_selector(
                        selector, timeout=3000
                    )
                    if login_button:
                        print(f"✅ Найдена кнопка Log In с селектором: {selector}")
                        break
                except Exception:
                    continue

            if login_button:
                await login_button.click()
                print("✅ Нажата кнопка Log In")
                await asyncio.sleep(1)
            else:
                print(
                    "ℹ️ Кнопка Log In не найдена. Возможно, пользователь уже аутентифицирован"
                )
                self.auth_status["status"] = "completed"
                return True

            # Вводим email
            if await self._provide_email():
                # Вводим пароль
                if await self._provide_password():
                    # Проверяем, появилось ли поле для кода подтверждения
                    code_required = await self._check_if_code_required()
                    if code_required:
                        print("📧 Требуется код подтверждения с почты")
                        print("⏳ Ожидаем код через API эндпоинт /auth/code")
                        self.auth_status["status"] = "waiting_code"
                        return True
                    else:
                        # Если код не требуется, авторизация завершена
                        self.auth_status["status"] = "completed"
                        print("✅ Авторизация завершена успешно!")
                        return True

            return False

        except Exception as e:
            print(f"❌ Ошибка при авторизации: {e}")
            return False

    async def _check_if_code_required(self):
        """Проверяет, требуется ли ввод кода подтверждения"""
        if not self.page:
            return False

        try:
            # Проверяем наличие поля для ввода кода
            verification_selectors = [
                "input[type='text'][placeholder*='Code']",
                "input[type='text'][placeholder*='код']",
                "input[name='code']",
                "input[data-testid*='code']",
                "input[placeholder*='Enter code']",
                "input[placeholder*='Введите код']",
            ]

            for selector in verification_selectors:
                try:
                    code_input = await self.page.wait_for_selector(
                        selector, timeout=3000
                    )
                    if code_input:
                        print(f"✅ Найдено поле для кода подтверждения: {selector}")
                        return True
                except Exception:
                    continue

            return False

        except Exception as e:
            print(f"ℹ️ Ошибка при проверке кода подтверждения: {e}")
            return False

    async def send_and_get_answer(self, prompt: str) -> str:
        """Отправляет запрос и получает ответ"""
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
        if not self.page:
            return "Page object is not initialized"

        try:
            # Прокручиваем к низу чтобы видеть поле ввода
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.1)
        except Exception:
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

        if not self.page:
            print("❌ Page object is not initialized")
            return False

        for selector in input_selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=10000)
                print(f"Найдено поле ввода с селектором: {selector}")
                return element
            except Exception:
                continue
        return None

    async def _wait_for_response_complete(self):
        """Ждет окончания генерации ответа и возвращает текст"""
        import time

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
                except Exception:
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

    async def get_auth_status(self):
        """Возвращает статус аутентификации"""
        return self.auth_status

    async def close(self):
        """Закрывает браузер"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
