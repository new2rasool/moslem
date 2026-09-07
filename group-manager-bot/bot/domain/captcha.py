"""
تولید و تصدیق CAPTCHA ریاضی (دامنهٔ خالص).

برای «متن پیام + گزینه‌های دکمه»: یک جمع تصادفی دو عددی می‌سازد؛ پاسخ‌های
غلطِ پرت به‌عنوان گزینه اضافه می‌شوند تا حدس تصادفی سخت باشد.
"""

from __future__ import annotations

import random


def generate(rand: random.Random | None = None) -> tuple[str, int, list[int]]:
    """
    ساخت چالش.

    خروجی: (متن پرسش، پاسخ درست، فهرست گزینه‌های پیشنهادی برای دکمه‌ها)
    """
    rng = rand or random
    a = rng.randint(2, 12)
    b = rng.randint(2, 12)
    answer = a + b
    options: set[int] = {answer}
    while len(options) < 4:
        options.add(answer + rng.randint(-3, 3))
    options_list = list(options)
    rng.shuffle(options_list)
    return f"{a} + {b} = ?", answer, options_list


def verify(answer: int, given: int) -> bool:
    return answer == given
