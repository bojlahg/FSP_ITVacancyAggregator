"""Пять тестовых резюме разных форматов (§7, T15) и PDF из них без внешних библиотек рендеринга.

PDF собирается через pypdfium2 (идёт вместе с pdfplumber) со шрифтом JetBrains Mono из ассетов PDF-профиля:
так фикстуры с кириллицей генерируются кодом и одинаково работают на Windows и в CI.
"""

import ctypes
import io
from functools import lru_cache

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from fontTools.ttLib import TTFont

from app.modules.resume.pdf import ASSETS_DIR

PAGE_WIDTH, PAGE_HEIGHT = 595, 842
MARGIN, LINE_HEIGHT, FONT_SIZE = 40, 14, 9.0

ANNA = """Кузнецова Анна Сергеевна
Backend-разработчик
Москва, готова к переезду
+7 (916) 123-45-67 · anna.kuznetsova@example.com · Telegram: @anna_backend
Желаемая зарплата: от 250 000 ₽
Формат работы: гибрид или удалённо
Опыт работы — 4 года 6 месяцев

Опыт работы
Январь 2022 — настоящее время
ООО «Финтех Плюс»
Backend-разработчик
Разрабатывала платёжные сервисы для банка на Python и FastAPI, PostgreSQL, Redis, Kafka.
Март 2020 — Декабрь 2021
АО «Ритейл Тех»
Junior Python-разработчик
Поддержка интернет-магазина на Django, тесты на pytest.

Ключевые навыки
Python, FastAPI, Django, PostgreSQL, Redis, Kafka, Docker, Git, pytest, Tarantool

О себе
Ответственная, люблю работать в команде, занимаюсь наставничеством джунов.
"""

ILYA = """Ilya Smirnov
Frontend Developer
St. Petersburg | ilya.smirnov@example.com | +7 921 555 12 34 | t.me/ilya_front
Expected salary: 120 000 RUB
Remote only

Skills
JavaScript, TypeScript, React, Redux, HTML, CSS, Webpack, Jest, Storybook

Experience
06.2024 – present
Frontend Developer, Studio Pixel
Built SPA with React and TypeScript, covered components with Jest.

About
Fast learner, good communication skills.
"""

MARIA = """Мария Волкова
DevOps-инженер
Город: Казань
Email: maria.volkova@example.com
Телефон: 8 (843) 200-30-40
Опыт работы: 7 лет

Навыки
Kubernetes, Docker, Terraform, Ansible, Prometheus, Grafana, Linux, GitLab CI, Bash, Python

Опыт работы
DevOps Lead, Телеком Регион
2021 — н.в.
Строила платформу на Kubernetes, мониторинг на Prometheus и Grafana.
Site Reliability Engineer, Облако Про
2017 — 2021
Автоматизация инфраструктуры на Terraform и Ansible.
"""

DMITRY = """Петров Дмитрий
Data Scientist
Новосибирск · удалённо · dmitry.petrov@example.com · @dpetrov_ml
Ожидания: 200 000 – 260 000 руб.

О себе
Строю модели машинного обучения для промышленности. Критическое мышление, самостоятельность.

Технические навыки
Python, pandas, NumPy, scikit-learn, PyTorch, SQL, Airflow, Spark, MLflow, Optuna

Опыт работы
Июнь 2023 — по настоящее время
Senior Data Scientist, Энерго Аналитика
Модели прогноза потребления электроэнергии.
Сентябрь 2019 — Май 2023
Data Scientist — Завод Север
Прогноз отказов оборудования на производстве.
"""

ELENA = """Резюме
Сидорова Елена Викторовна
Инженер по тестированию (QA)
Екатеринбург
elena.sidorova@example.com, +7-912-000-11-22
Опыт 3 года

Навыки
Ручное тестирование, автотесты на Python, Selenium, Playwright, Postman, SQL, Jira, Allure, TestRail

Опыт работы
02.2022 — 10.2026
QA-инженер
Медтех Онлайн
Тестирование API и веб-интерфейса телемедицинской платформы.
"""

SAMPLES = {"anna": ANNA, "ilya": ILYA, "maria": MARIA, "dmitry": DMITRY, "elena": ELENA}


@lru_cache
def _font_bytes() -> bytes:
    font = TTFont(ASSETS_DIR / "fonts" / "JetBrainsMono-Regular.woff2")
    font.flavor = None
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()


def make_pdf(text: str) -> bytes:
    """Текстовый PDF: каждая строка — отдельный текстовый объект; переносы страниц по высоте."""
    document = pdfium.PdfDocument.new()
    data = _font_bytes()
    font_buffer = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
    font = pdfium_raw.FPDFText_LoadFont(
        document.raw, font_buffer, len(data), pdfium_raw.FPDF_FONT_TRUETYPE, True
    )
    page = None
    y = 0.0
    for line in text.splitlines():
        if page is None or y < MARGIN:
            if page is not None:
                pdfium_raw.FPDFPage_GenerateContent(page.raw)
            page = document.new_page(PAGE_WIDTH, PAGE_HEIGHT)
            y = PAGE_HEIGHT - MARGIN
        if line.strip():
            item = pdfium_raw.FPDFPageObj_CreateTextObj(document.raw, font, FONT_SIZE)
            encoded = ctypes.create_string_buffer((line + "\0").encode("utf-16-le"))
            pdfium_raw.FPDFText_SetText(item, ctypes.cast(encoded, ctypes.POINTER(pdfium_raw.FPDF_WCHAR)))
            pdfium_raw.FPDFPageObj_Transform(item, 1, 0, 0, 1, MARGIN, y)
            pdfium_raw.FPDFPage_InsertObject(page.raw, item)
        y -= LINE_HEIGHT
    if page is not None:
        pdfium_raw.FPDFPage_GenerateContent(page.raw)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def make_scan_pdf() -> bytes:
    """PDF без текстового слоя — как скан."""
    document = pdfium.PdfDocument.new()
    document.new_page(PAGE_WIDTH, PAGE_HEIGHT)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()
