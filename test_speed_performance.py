#!/usr/bin/env python3
"""
Тест производительности для измерения скорости ответов GPT Bridge API
"""

import asyncio
import json
import time
from typing import List, Tuple

import aiohttp


class SpeedPerformanceTester:
    def __init__(self, base_url: str = "http://localhost:8010"):
        self.base_url = base_url
        self.results = []

    async def test_single_request(
        self, session: aiohttp.ClientSession, prompt: str, request_id: int
    ) -> Tuple[float, str]:
        """Тестирует один запрос и возвращает время выполнения и ответ"""
        start_time = time.time()

        try:
            async with session.post(
                f"{self.base_url}/ask",
                json={"prompt": prompt},
                timeout=120,  # 2 минуты таймаут
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    end_time = time.time()
                    response_time = end_time - start_time

                    answer = data.get("answer", "No answer received")
                    print(
                        f"✅ Запрос {request_id}: {response_time:.2f} сек - {prompt[:50]}..."
                    )

                    return response_time, answer
                else:
                    end_time = time.time()
                    response_time = end_time - start_time
                    print(
                        f"❌ Запрос {request_id}: Ошибка {response.status} - {response_time:.2f} сек"
                    )
                    return response_time, f"Ошибка: {response.status}"

        except asyncio.TimeoutError:
            end_time = time.time()
            response_time = end_time - start_time
            print(f"⏰ Запрос {request_id}: Таймаут - {response_time:.2f} сек")
            return response_time, "Таймаут"
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            print(f"💥 Запрос {request_id}: Ошибка {str(e)} - {response_time:.2f} сек")
            return response_time, f"Ошибка: {str(e)}"

    async def run_performance_test(
        self, prompts: List[str], delay_between_requests: float = 1.0
    ):
        """Запускает тест производительности с заданными промптами"""
        print(f"🚀 Запуск теста производительности с {len(prompts)} запросами")
        print(f"⏱️  Задержка между запросами: {delay_between_requests} сек")
        print("-" * 80)

        async with aiohttp.ClientSession() as session:
            tasks = []

            for i, prompt in enumerate(prompts, 1):
                # Добавляем задержку между запросами
                if i > 1:
                    await asyncio.sleep(delay_between_requests)

                task = self.test_single_request(session, prompt, i)
                tasks.append(task)

            # Запускаем все задачи параллельно
            results = await asyncio.gather(*tasks)

            # Сохраняем результаты
            for i, (response_time, answer) in enumerate(results, 1):
                self.results.append(
                    {
                        "request_id": i,
                        "prompt": prompts[i - 1],
                        "response_time": response_time,
                        "answer_preview": answer[:100] + "..."
                        if len(answer) > 100
                        else answer,
                    }
                )

        self._print_summary()

    def _print_summary(self):
        """Выводит сводку результатов тестирования"""
        print("\n" + "=" * 80)
        print("📊 СВОДКА РЕЗУЛЬТАТОВ ТЕСТИРОВАНИЯ")
        print("=" * 80)

        if not self.results:
            print("❌ Нет результатов для анализа")
            return

        successful_requests = [
            r
            for r in self.results
            if "Ошибка" not in r["answer_preview"]
            and "Таймаут" not in r["answer_preview"]
        ]
        failed_requests = [
            r
            for r in self.results
            if "Ошибка" in r["answer_preview"] or "Таймаут" in r["answer_preview"]
        ]

        response_times = [r["response_time"] for r in successful_requests]

        if response_times:
            avg_time = sum(response_times) / len(response_times)
            min_time = min(response_times)
            max_time = max(response_times)

            print(
                f"✅ Успешных запросов: {len(successful_requests)}/{len(self.results)}"
            )
            print(f"❌ Неудачных запросов: {len(failed_requests)}/{len(self.results)}")
            print(f"📈 Среднее время ответа: {avg_time:.2f} сек")
            print(f"⚡ Минимальное время: {min_time:.2f} сек")
            print(f"🐌 Максимальное время: {max_time:.2f} сек")

            print("\n📋 Детали по запросам:")
            for result in self.results:
                status = (
                    "✅"
                    if "Ошибка" not in result["answer_preview"]
                    and "Таймаут" not in result["answer_preview"]
                    else "❌"
                )
                print(
                    f"  {status} Запрос {result['request_id']}: {result['response_time']:.2f} сек - {result['prompt'][:40]}..."
                )
        else:
            print("❌ Нет успешных запросов для анализа")

    def save_results_to_file(self, filename: str = "performance_results.json"):
        """Сохраняет результаты в JSON файл"""
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Результаты сохранены в файл: {filename}")


async def main():
    """Основная функция для запуска теста производительности"""

    # Тестовые вопросы о разных странах
    test_prompts = [
        "Какие основные достопримечательности Франции?",
        "Какая кухня популярна во Франции?",
        "Какие основные достопримечательности Мадрида?",
        "Какая кухня популярна в Испании?",
    ]

    # Создаем тестер и запускаем тест
    tester = SpeedPerformanceTester()

    try:
        await tester.run_performance_test(
            prompts=test_prompts,
            delay_between_requests=1.0,  # 1 секунда между запросами
        )

        # Сохраняем результаты
        tester.save_results_to_file()

    except Exception as e:
        print(f"💥 Ошибка при запуске теста: {e}")


if __name__ == "__main__":
    print("🎯 Тест производительности GPT Bridge API")
    print("⚠️  Убедитесь, что сервер запущен на http://localhost:8010")
    print()

    asyncio.run(main())
