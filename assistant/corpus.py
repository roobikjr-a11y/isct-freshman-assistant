# -*- coding: utf-8 -*-
"""Загрузка корпуса и построение фрагментов (чанков) для поиска."""
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSES_JSON = os.path.join(HERE, "data", "courses.json")

CHUNK_SIZE = 900   # символов
OVERLAP = 150

STOPWORDS = set("""и в во не что он на я с со как а то все она так его но да ты к у же
вы за бы по только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг
ли если уже или ни быть был него до вас нибудь опять уж вам сказал ведь там потом себя
ничей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто человек
чего раз тоже себе под жизнь будет ж тогда кто этот говорил того потому этого какой
совсем ним здесь этом один почти мой тем чтобы нее кажется сейчас были куда зачем
скажет всех никогда сегодня можно при наконец два об другой хоть после над больше тот
через эти нас про всего них какая много сказала три эту моя впрочем хорошо свою
этой перед иногда лучше чуть том нельзя такой им более всегда конечно всю между это
""".split())


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    return text


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[а-яa-z0-9]+", normalize(text))
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def stem(word: str) -> str:
    """Лёгкая нормализация окончаний (без внешних зависимостей)."""
    for suf in ("ованиями", "ированию", "ениями", "ациями", "ическому", "ическому",
                "ениями", "ениями", "ациях", "ации", "ацией", "ому", "его", "ого",
                "ыми", "ими", "ая", "яя", "ое", "ее", "ые", "ие", "ов", "ев", "ам",
                "ям", "ах", "ях", "ой", "ей", "ом", "ем", "ы", "и", "а", "я", "у",
                "ю", "е", "о"):
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[: -len(suf)]
    return word


def stem_tokens(tokens: list[str]) -> list[str]:
    return [stem(t) for t in tokens]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Режет длинный текст на фрагменты по границам строк/предложений."""
    junk = ("буквышка", "шрифты hse", "сведения о доходах", "обратная связь",
            "получение образования", "о вышке", "свидетельство", "лиценз",
            "версия для слабовидящих", "cookie", "персонифицированных страниц",
            "людям с ограниченными", "личный кабинет", "поиск по сайту", "вход",
            "учебные курсы", "образовательная программа", "тип материала")
    lines = [l for l in text.split("\n")
             if l.strip() and not any(j in l.lower() for j in junk) and "→" not in l]
    # склейка предложений, разорванных переносами строк
    merged = []
    for line in lines:
        if merged and merged[-1].rstrip()[-1:] not in ".!?:;»)>—|0123456789" \
                and (line[:1].islower() or line[:1] in "(«"):
            merged[-1] = merged[-1].rstrip() + " " + line
        else:
            merged.append(line)
    lines = merged
    chunks, buf = [], ""
    for line in lines:
        # очень длинную строку (таблицу) тоже режем
        while len(line) > size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(line[:size])
            line = line[size - overlap:]
        if len(buf) + len(line) + 1 <= size:
            buf = (buf + "\n" + line) if buf else line
        else:
            if buf:
                chunks.append(buf)
            buf = line
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c.strip()) > 40]


def build_chunks() -> list[dict]:
    """Возвращает список фрагментов с метаданными источника."""
    courses = json.load(open(COURSES_JSON, encoding="utf-8"))
    chunks = []
    for course in courses:
        for section, body in course.get("sections", {}).items():
            for piece in chunk_text(body):
                chunks.append({
                    "course_id": course["id"],
                    "course": course["title"],
                    "section": section,
                    "url": course["url"],
                    "text": piece,
                })
        # строка с метаданными курса целиком (лекторы, шапка)
        meta = ["Дисциплина: %s." % course["title"],
                "Преподаватели: %s." % ", ".join(course.get("lecturers", [])[:10])]
        meta += course.get("header_info", [])
        chunks.append({
            "course_id": course["id"], "course": course["title"], "section": "О курсе",
            "url": course["url"], "text": "\n".join(meta),
        })
    return chunks


if __name__ == "__main__":
    ch = build_chunks()
    print("Курсов:", len({c['course'] for c in ch}), "| фрагментов:", len(ch))
