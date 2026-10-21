#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI-помощник: python3 cli.py "вопрос"  |  интерактивный режим без аргументов."""
import sys

from assistant.answer import answer, format_reply


def main():
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(format_reply(answer(q)))
        return
    print("Помощник первокурсника ИВТ МИЭМ. Введите вопрос (пустая строка или 'выход' — завершить):")
    while True:
        try:
            q = input("\nВопрос> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("выход", "exit", "quit"):
            break
        print(format_reply(answer(q)))


if __name__ == "__main__":
    main()
