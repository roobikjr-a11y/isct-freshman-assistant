# -*- coding: utf-8 -*-
"""Основной конвейер помощника: вопрос -> поиск -> краткий ответ + источники."""
import re

from .corpus import tokenize, stem_tokens, normalize
from .retrieval import search, detect_course, get_index, get_section_hints
from .llm import ask_llm, llm_available

SYSTEM = (
    "Ты — помощник первокурсника ИВТ МИЭМ НИУ ВШЭ. Отвечай ТОЛЬКО на основе "
    "приведённых фрагментов официальных программ дисциплин. Формулируй краткий "
    "ответ на русском (2-5 предложений). Если во фрагментах нет ответа — честно "
    "скажи, что данных нет. Не придумывай факты."
)

CITATION_RE = re.compile(
    r" - 978-|znanium\.ru|e\.lanbook|urait|\.ru/book|ISBN|[А-ЯЁ]\.\s?[А-ЯЁ]\.|, (19|20)\d{2}\b|Т\.\s?\d")
META_LABEL_RE = re.compile(
    r"^(Кредиты|Статус|Когда читается|Учебный год|Язык|Дисциплина|Преподаватели):")
ASSESS_SECTIONS = ("элементы контроля", "промежуточная аттестация", "assessment elements")
LISTY_SECTIONS = ("содержание учебной дисциплины", "course contents",
                  "планируемые результаты обучения", "expected learning outcomes")


def _is_citation(line: str) -> bool:
    return bool(CITATION_RE.search(line))


def _line_score(line: str, q_stems: set) -> int:
    stems = set(stem_tokens(tokenize(line)))
    overlap = len(stems & q_stems)
    bonus = 1 if re.search(r"\d|[«\"]", line) else 0
    return overlap + bonus


def _extractive_answer(query: str, hits: list[dict]) -> str:
    q_stems = set(stem_tokens(tokenize(query)))
    q_norm = normalize(query)
    wants_literature = any(w in q_norm for w in
                           ("литератур", "книг", "учебник", "почитать", "читать", "источник"))
    courses = detect_course(query)
    base_courses = {c for c in courses if not c.endswith("(углубленный курс)")}
    hints = get_section_hints(query)
    candidates = []
    seen = set()
    for h in hits[:5]:
        section_norm = normalize(h["section"])
        listy = any(section_norm.startswith(s) for s in LISTY_SECTIONS)
        hinted = any(hn == section_norm or hn in section_norm for hn in hints)
        for line in h["text"].split("\n"):
            line = line.strip(" |").strip()
            meta_line = bool(META_LABEL_RE.match(line))
            min_len = 9 if listy else 25
            if (len(line) < min_len and not meta_line) or len(line) > 400 or line in seen:
                continue
            if "→" in line or line.lower() in ("неблокирующий", "блокирующий", "не блокируется"):
                continue
            # библиографические записи показываем только когда спрашивают литературу
            if not wants_literature and _is_citation(line):
                continue
            if wants_literature and not _is_citation(line) and "литератур" in section_norm:
                continue
            seen.add(line)
            score = _line_score(line, q_stems)
            # строка из запрошенного базового курса — приоритет
            if base_courses and h["course"] in base_courses:
                score += 2
            # строка из раздела, на который указывает вопрос (Авторы, Содержание и т.п.)
            if hinted:
                score += 3
            # вопрос про людей — поднимаем список преподавателей
            if line.startswith("Преподаватели:") and any(
                    hn in ("о курсе", "авторы") for hn in hints):
                score += 3
            if score > 0:
                candidates.append((score, len(line), line))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    best = [c[2] for c in candidates[:4]]
    if not best:
        best = [hits[0]["text"][:300]]
    return "\n".join("• " + b for b in best)


def _assessment_answer(query: str, hits: list[dict]) -> str | None:
    """Для вопросов про оценивание: собираем элементы контроля и формулы."""
    courses = detect_course(query)
    assess_hits = [h for h in hits if normalize(h["section"]) in
                   (normalize(s) for s in ASSESS_SECTIONS)]
    if courses:
        only = [h for h in assess_hits if h["course"] in courses]
        assess_hits = only or assess_hits
    if not assess_hits:
        return None
    formulas, elements, seen = [], [], set()
    for h in assess_hits[:3]:
        for line in h["text"].split("\n"):
            line = line.strip(" |").strip()
            if not line or line in seen or len(line) > 300:
                continue
            seen.add(line)
            if re.match(r"^\d+(\.\d+)?\s*\*", line):
                formulas.append(f"{h['course']}: {line}")
            elif 12 < len(line) < 120 and not _is_citation(line) \
                    and line.lower() not in ("неблокирующий", "блокирующий") \
                    and not re.match(r"^(19|20)\d{2}", line) \
                    and not line.startswith(("Устный", "Письменный")):
                elements.append(line)
            elif line.startswith(("Устный", "Письменный")):
                if elements:
                    elements[-1] += f" ({line.lower()})"
    clean = [re.sub(r"\s*(неблокирующий|блокирующий|не блокируется)\.?\s*$", "", e)
             for e in elements]
    clean = [e for e in clean if len(e) > 10]
    out = []
    if clean:
        out.append("Элементы контроля: " + ", ".join(dict.fromkeys(clean[:8])) + ".")
    if formulas:
        out.append("Формулы оценки:\n" + "\n".join("• " + f for f in dict.fromkeys(formulas[:4])))
    return "\n".join(out) if out else None


def _course_list_answer(query: str) -> str | None:
    """Вопросы вида «какие дисциплины…» — перечисляем дисциплины корпуса."""
    q = normalize(query)
    if re.search(r"какие\s+(дисциплин|курс|предмет|занят)", q) or "список дисциплин" in q:
        _, chunks = get_index()
        titles = sorted({c["course"] for c in chunks})
        return "На 1 курсе ИВТ в 2026/2027 году:\n" + "\n".join("• " + t for t in titles)
    return None


def answer(question: str, top_k: int = 6, use_llm: bool = True) -> dict:
    """Главная функция: возвращает {answer, sources, mode, hits}."""
    question = question.strip()

    # вопросы о перечне дисциплин отвечаем сразу списком
    listing = _course_list_answer(question)
    if listing:
        _, chunks = get_index()
        url = chunks[0]["url"].rsplit("/", 1)[0]
        return {"answer": listing,
                "sources": [{"course": "Каталог курсов 1 курса ИВТ 2026/2027",
                             "section": "Перечень дисциплин", "url": url + "?year=2026"}],
                "mode": "extractive", "hits": []}

    hits = search(question, top_k=top_k)
    if not hits:
        return {"answer": "Не нашёл релевантного материала в программах дисциплин. "
                          "Переформулируйте вопрос — например, укажите название дисциплины.",
                "sources": [], "mode": "extractive", "hits": []}

    sources, seen = [], set()
    for h in hits:
        key = (h["course"], h["section"])
        if key not in seen:
            seen.add(key)
            sources.append({"course": h["course"], "section": h["section"], "url": h["url"]})

    # составление ответа
    mode = "extractive"
    hints = get_section_hints(question)
    assess_intent = any(normalize(s) in hints for s in
                        ("элементы контроля", "промежуточная аттестация", "assessment elements"))
    if assess_intent:
        text = _assessment_answer(question, hits) or _extractive_answer(question, hits)
    else:
        text = _extractive_answer(question, hits)

    if use_llm and llm_available():
        context = "\n\n".join(
            f"[Источник {i+1}: {h['course']} — {h['section']}]\n{h['text']}"
            for i, h in enumerate(hits))
        user = (f"Фрагменты программ:\n{context}\n\nВопрос студента: {question}\n\n"
                "Ответь кратко по-русски только на основе фрагментов. Источники не перечисляй.")
        llm_text = ask_llm(SYSTEM, user)
        if llm_text:
            text, mode = llm_text, "llm"

    # при слабом поиске честно предупреждаем
    if hits[0]["score"] < 2.0:
        text = "⚠️ Уверенность в релевантности низкая — материал мог быть найден неточно.\n" + text

    return {"answer": text, "sources": sources[:5], "mode": mode,
            "hits": [{"course": h["course"], "section": h["section"], "score": h["score"]}
                     for h in hits]}


def format_reply(res: dict) -> str:
    lines = [res["answer"], "", "Источники:"]
    for s in res["sources"]:
        lines.append(f"• {s['course']} — {s['section']}: {s['url']}")
    return "\n".join(lines)
