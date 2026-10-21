# -*- coding: utf-8 -*-
"""BM25-поиск по фрагментам программ (чистый Python, без зависимостей)."""
import math
import re
from collections import Counter
from functools import lru_cache

from .corpus import build_chunks, tokenize, stem, stem_tokens, normalize

# Слова-маркеры разделов (сравниваются по стемам, т.е. без окончаний):
ASSESS = ["Элементы контроля", "Промежуточная аттестация", "Assessment Elements"]
LITER = ["литература", "Bibliography", "References"]
CONTENTS = ["Содержание учебной дисциплины", "Course Contents"]
OBJECTIVE = ["Цель освоения дисциплины", "Learning Objectives"]
OUTCOMES = ["Планируемые результаты обучения", "Expected Learning Outcomes"]
ABOUT = ["О курсе"]
AUTHORS = ["Авторы", "Authors"]

SECTION_HINTS = {
    # --- формы контроля и оценивание ---
    "оцен": ASSESS, "экзамен": ASSESS, "зачет": ASSESS, "контроль": ASSESS,
    "контрольн": ASSESS, "коллоквиум": ASSESS, "формул": ASSESS, "сда": ASSESS,
    "пересдач": ASSESS, "балл": ASSESS, "накопительн": ASSESS, "аттестац": ASSESS,
    "аттестаци": ASSESS, "элемент": ASSESS, "вес": ASSESS, "оценива": ASSESS,
    # --- литература ---
    "литератур": LITER, "книг": LITER, "учебник": LITER, "почита": LITER,
    "читать": LITER, "источник": LITER, "пособи": LITER, "справочник": LITER,
    # --- содержание ---
    "содержан": CONTENTS, "тем": CONTENTS, "изуч": CONTENTS, "проход": CONTENTS,
    "раздел": CONTENTS, "предмет": CONTENTS, "лект": CONTENTS, "занима": CONTENTS,
    "семинстр": CONTENTS, "включ": CONTENTS,
    # --- цель / смысл ---
    "цел": OBJECTIVE, "зачем": OBJECTIVE, "смысл": OBJECTIVE, "задач": OBJECTIVE,
    # --- результаты ---
    "результат": OUTCOMES, "умени": OUTCOMES, "навык": OUTCOMES, "компетенц": OUTCOMES,
    "науч": OUTCOMES, "смогу": OUTCOMES, "получ": OUTCOMES,
    # --- кто ведет ---
    "преподавател": ABOUT + AUTHORS, "вед": ABOUT + AUTHORS, "автор": AUTHORS,
    "лектор": AUTHORS, "состав": AUTHORS,
    # --- метаданные ---
    "кредит": ABOUT, "зачетн": ABOUT, "обязательн": ABOUT, "когда": ABOUT,
    "модул": ABOUT, "язык": ABOUT, "статус": ABOUT, "семестр": ABOUT,
    "кафедр": ABOUT, "департамент": ABOUT, "читается": ABOUT, "факультатив": ABOUT,
    # --- связь дисциплин ---
    "связ": ["Аннотация"], "постреквизит": ["Аннотация"], "пререквизит": ["Аннотация"],
    "после": ["Аннотация"], "перед": ["Аннотация"], "дальше": ["Аннотация"],
}


def _hints_by_stem() -> dict[str, set[str]]:
    out = {}
    for key, secs in SECTION_HINTS.items():
        out.setdefault(stem(key), set()).update(normalize(s) for s in secs)
    return out


_HINT_STEMS = _hints_by_stem()


def get_section_hints(query: str) -> set[str]:
    """Нормализованные названия разделов, релевантные вопросу."""
    hints = set()
    for t in tokenize(query):
        st = stem(t)
        # точное и укороченное совпадение по стему
        if st in _HINT_STEMS:
            hints |= _HINT_STEMS[st]
        else:
            for hs, secs in _HINT_STEMS.items():
                if len(st) >= 4 and len(hs) >= 3 and (
                        st.startswith(hs) or hs.startswith(st)):
                    hints |= secs
    return hints


class BM25Index:
    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.docs = [stem_tokens(tokenize(c["text"] + " " + c["course"] + " " + c["section"]))
                     for c in chunks]
        self.doc_len = [len(d) for d in self.docs]
        self.avgdl = sum(self.doc_len) / max(1, len(self.doc_len))
        self.N = len(self.docs)
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def score(self, query_tokens, i: int) -> float:
        s, doc = 0.0, self.docs[i]
        tf = Counter(doc)
        dl = self.doc_len[i] or 1
        for t in set(query_tokens):
            if t not in tf:
                continue
            f = tf[t]
            idf = self.idf.get(t, 0)
            s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s


@lru_cache(maxsize=1)
def get_index() -> tuple[BM25Index, list[dict]]:
    chunks = build_chunks()
    return BM25Index(chunks), chunks


ALIASES = {
    "матан": "Математический анализ", "матанализ": "Математический анализ",
    "математический анализ": "Математический анализ",
    "алгем": "Алгебра и геометрия", "алгебра": "Алгебра и геометрия",
    "дискретка": "Дискретная математика", "дискрет": "Дискретная математика",
    "дискретная математика": "Дискретная математика",
    "физра": "Физическая культура", "физкультура": "Физическая культура",
    "физика": "Физика",
    "инфа": "Информатика", "информатика": "Информатика",
    "прога": "Алгоритмизация и программирование",
    "программирование": "Алгоритмизация и программирование",
    "алгоритмы": "Алгоритмизация и программирование",
    "алгоритмизация": "Алгоритмизация и программирование",
    "python": 'Проектный семинар "Python в науке о данных"',
    "питон": 'Проектный семинар "Python в науке о данных"',
    "английский": "English Language Integrative Exam",
    "история": "История России",
    "орг": "Основы российской государственности",
    "бж": "Безопасность жизнедеятельности",
    "графика": "Компьютерный практикум по инженерной графике",
    "инженерн": "Компьютерный практикум по инженерной графике",
    "специальность": "Введение в специальность",
    "продукт": 'Проектный семинар "Управление продуктами и проектами"',
    "ии": "Независимый экзамен по ИИ-грамотности",
}


def detect_course(query: str) -> list[str]:
    """Дисциплины, упомянутые в вопросе (включая разговорные названия)."""
    _, chunks = get_index()
    q = normalize(query)
    titles = {c["course"] for c in chunks}
    hits = []
    for alias, full in sorted(ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(r"(?<![а-яa-z])" + re.escape(alias) + r"(?![а-яa-z])", q):
            for t in titles:
                if t == full or t.startswith(full):
                    hits.append(t)
            q = q.replace(alias, " ")
    # точное вхождение полного названия
    for t in titles:
        short = normalize(t.replace(" (углубленный курс)", ""))
        if len(short) > 10 and short in q:
            hits.extend(x for x in titles if normalize(x.replace(" (углубленный курс)", "")) == short)
    # совпадение по стемам (склонения: «физической культуре», «алгебре» и т.п.)
    q_stems = set(stem_tokens(tokenize(query)))
    for t in titles:
        t_stems = {x for x in stem_tokens(tokenize(t)) if len(x) > 3}
        if len(t_stems) >= 2 and t_stems <= q_stems:
            hits.append(t)
        elif len(t_stems) == 1:
            # однословные курсы: «Информатика», «Физика» — сравниваем по стему-префиксу
            st = next(iter(t_stems))
            if len(st) > 4 and any(qs == st or qs.startswith(st)
                                   for qs in q_stems if len(qs) > 4):
                hits.append(t)
    return list(dict.fromkeys(hits))


def search(query: str, top_k: int = 6) -> list[dict]:
    """BM25 + буст за упоминание дисциплины и подходящий раздел."""
    idx, chunks = get_index()
    q_tokens = stem_tokens(tokenize(query))
    if not q_tokens:
        return []
    courses = set(detect_course(query))
    hints = get_section_hints(query)
    deep = "углубл" in normalize(query)
    scored = []
    for i in range(idx.N):
        s = idx.score(q_tokens, i)
        if s <= 0:
            continue
        c = chunks[i]
        if courses:
            if c["course"] in courses:
                # базовый курс приоритетнее углублённого, если его явно не спрашивали
                s *= 1.3 if (c["course"].endswith("(углубленный курс)") and not deep) else 2.5
        if hints and any(h in normalize(c["section"]) for h in hints):
            # мультипликативный + аддитивный буст, чтобы всплывали разделы
            # с низким BM25 (например, короткий раздел «Цель»)
            s = s * 2.0 + 15
        scored.append((s, i))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [dict(chunks[i], score=round(s, 2)) for s, i in scored[:top_k]]
