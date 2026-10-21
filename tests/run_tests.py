# -*- coding: utf-8 -*-
"""Прогон тестовых вопросов: python3 tests/run_tests.py -> docs/test_results.md"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from assistant.answer import answer  # noqa: E402


def main():
    questions = json.load(open(os.path.join(HERE, "tests", "questions.json"), encoding="utf-8"))
    lines = [
        "# Результаты тестирования помощника первокурсника ИВТ",
        "",
        "Прогнано вопросов: %d (из них демонстрируют корректную работу: %d, "
        "демонстрируют ограничения: %d)." % (
            len(questions),
            sum(1 for q in questions if q["type"] == "good"),
            sum(1 for q in questions if q["type"] == "bad")),
        "",
    ]
    for q in questions:
        res = answer(q["question"])
        src = "; ".join(f"[{s['course']} — {s['section']}]({s['url']})" for s in res["sources"][:3]) or "—"
        lines += [
            "---",
            "",
            f"### Вопрос {q['id']} ({'✅ корректная работа' if q['type']=='good' else '⚠️ демонстрация ограничения'}): {q['question']}",
            "",
            f"**Ожидание:** {q['expect']}",
            "",
            f"**Ответ помощника** (режим: {res['mode']}):",
            "",
            "> " + res["answer"].replace("\n", "\n> "),
            "",
            f"**Источники:** {src}",
            "",
        ]
    out = os.path.join(HERE, "docs", "test_results.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Сохранено:", out)


if __name__ == "__main__":
    main()
