# -*- coding: utf-8 -*-
"""
Скрейпер программ дисциплин 1 курса ИВТ МИЭМ НИУ ВШЭ (2026/2027).

Скачивает страницы каталога курсов и парсит их в data/courses.json.
Запуск:  python3 scraper.py
"""
import json
import os
import re
import html as htmllib
import time
import urllib.request

BASE = "https://www.hse.ru/ba/isct/courses"
YEAR = 2026
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}
HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(HERE, "data", "raw")
OUT = os.path.join(HERE, "data", "courses.json")

LIST_URLS = [
    f"{BASE}?course=1.1.1.4&page=1&year={YEAR}",
    f"{BASE}/page2.html?course=1.1.1.4&year={YEAR}",
]


def strip_tags(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</(p|div|li|tr|h[1-6]|ul|ol|table)>", "\n", s)
    s = re.sub(r"<td[^>]*>", " | ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmllib.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def discover_course_ids() -> dict[int, str]:
    """Собирает {id: название} со обеих страниц каталога."""
    courses = {}
    for url in LIST_URLS:
        html = fetch(url)
        for m in re.finditer(r'href="[^"]*/ba/isct/courses/(\d+)\.html"[^>]*>([^<]+)</a>', html):
            cid, title = int(m.group(1)), m.group(2).strip()
            if cid not in courses:
                courses[cid] = title
    return courses


def cut_footer(body: str) -> str:
    """Обрезает служебное меню сайта в конце раздела (футер)."""
    markers = ("О ВЫШКЕ", "Министерство науки", "Сведения об образовательной организации",
               "Политика обработки", "Книжный магазин", "Обратная связь",
               "Внешние научно-информационные", "Версия для слабовидящих",
               "Людям с ограниченными", "Личный кабинет", "Шрифты HSE",
               "Сведения о доходах", "Получение образования")
    lines, cut = body.split("\n"), len(body) + 1
    for i, line in enumerate(lines):
        if any(line.strip().startswith(m) for m in markers):
            cut = i
            break
    return "\n".join(lines[:cut])


def parse_course(cid: int, fallback_title: str) -> dict:
    path = os.path.join(RAW_DIR, f"{cid}.html")
    html = open(path, encoding="utf-8").read()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    doc = {
        "id": cid,
        "title": strip_tags(m.group(1)) if m else fallback_title,
        "url": f"{BASE}/{cid}.html",
    }
    # метаданные из шапки: учебный год, кредиты, статус, модули
    header = re.search(r'<div class="b-program__header-info.*?(?=<h)', html, re.S)
    if header:
        raw = [x.strip() for x in re.sub(r"<[^>]+>", "|", header.group(0)).split("|")]
        raw = [x for x in raw if x and "→" not in x]
        pairs, label = [], ""
        for x in raw:
            if x.endswith(":"):
                label = x
            elif label:
                pairs.append(f"{label} {x}")
                label = ""
            elif x == "Кредиты":
                label = "Кредиты:"
            elif x.isdigit():
                pairs.append(f"Кредиты: {x}")
            elif x.startswith("20") and "/" in x:
                pairs.append(f"Учебный год: {x}")
            elif x in ("RUS", "ENG"):
                pairs.append("Язык: русский" if x == "RUS" else "Язык: английский")
        doc["header_info"] = pairs[:8]
    # разделы программы по заголовкам h4
    parts = re.split(r'<h4[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h4>', html, flags=re.S)
    sections = {}
    for i in range(1, len(parts), 2):
        name = strip_tags(parts[i])
        body = strip_tags(parts[i + 1]) if i + 1 < len(parts) else ""
        if name and body and len(name) < 90:
            sections[name] = cut_footer(body)
    doc["sections"] = sections
    # преподаватели = авторы программы (раздел "Авторы")
    authors = re.findall(r'<li class="pud__list-item pud__list-item_authors">.*?</li>', html, re.S)
    doc["lecturers"] = [strip_tags(a) for a in authors if strip_tags(a)][:15]
    return doc


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    ids = discover_course_ids()
    print(f"Найдено дисциплин: {len(ids)}")
    out = []
    for cid, title in ids.items():
        path = os.path.join(RAW_DIR, f"{cid}.html")
        if not (os.path.exists(path) and os.path.getsize(path) > 5000):
            open(path, "w", encoding="utf-8").write(fetch(f"{BASE}/{cid}.html"))
            time.sleep(0.4)
        out.append(parse_course(cid, title))
        print(f"  ok: {out[-1]['title']}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Сохранено {len(out)} дисциплин -> {OUT}")


if __name__ == "__main__":
    main()
