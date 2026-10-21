# -*- coding: utf-8 -*-
"""Опциональный вызов внешней LLM через любой OpenAI-совместимый API.

Настраивается переменными окружения:
  LLM_BASE_URL — например https://api.openai.com/v1 или https://open.bigmodel.cn/api/paas/v4
  LLM_API_KEY  — ключ API
  LLM_MODEL    — имя модели (по умолчанию gpt-4o-mini)

Если переменные не заданы или запрос не удался — ассистент работает
в офлайн-режиме (экстрактивные ответы, см. answer.py).
"""
import json
import os
import urllib.request


def llm_available() -> bool:
    return bool(os.environ.get("LLM_API_KEY") and os.environ.get("LLM_BASE_URL"))


def ask_llm(system: str, user: str, max_tokens: int = 400) -> str | None:
    if not llm_available():
        return None
    url = os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ["LLM_API_KEY"],
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001 — офлайн-режим при любой ошибке
        print(f"[llm] запрос не удался, работаем офлайн: {e}")
        return None
