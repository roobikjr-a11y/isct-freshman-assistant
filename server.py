#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Веб-интерфейс помощника. Запуск: python3 server.py [порт] (по умолчанию 8000)."""
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from assistant.answer import answer

PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Помощник первокурсника ИВТ МИЭМ</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--text:#e6edf3;--dim:#8b949e;--accent:#58a6ff}
*{box-sizing:border-box;margin:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);display:flex;flex-direction:column;height:100vh}
header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px}
header .logo{width:34px;height:34px;border-radius:8px;background:linear-gradient(135deg,#58a6ff,#bc8cff);display:flex;align-items:center;justify-content:center;font-size:19px}
header h1{font-size:17px;font-weight:600}
header p{font-size:12px;color:var(--dim)}
#chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:14px}
.msg{max-width:78%;padding:12px 16px;border-radius:14px;line-height:1.5;font-size:14.5px;white-space:pre-wrap}
.user{align-self:flex-end;background:#1f6feb;color:#fff;border-bottom-right-radius:4px}
.bot{align-self:flex-start;background:var(--card);border:1px solid var(--line);border-bottom-left-radius:4px}
.bot .src{margin-top:10px;padding-top:10px;border-top:1px dashed var(--line);font-size:12.5px;color:var(--dim)}
.bot .src a{color:var(--accent);text-decoration:none;display:block;margin-top:3px}
.badge{display:inline-block;font-size:10.5px;color:var(--dim);border:1px solid var(--line);border-radius:20px;padding:1px 8px;margin-bottom:6px}
form{display:flex;gap:10px;padding:14px 20px;border-top:1px solid var(--line);background:var(--card)}
input{flex:1;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px 14px;color:var(--text);font-size:15px;outline:none}
input:focus{border-color:var(--accent)}
button{background:#1f6feb;border:none;color:#fff;border-radius:10px;padding:12px 22px;font-size:15px;cursor:pointer}
button:hover{background:#388bfd}
.hint{align-self:center;font-size:12.5px;color:var(--dim)}
</style></head><body>
<header><div class="logo">🎓</div>
<div><h1>Помощник первокурсника ИВТ МИЭМ НИУ ВШЭ</h1>
<p>Ответы по программам 25 дисциплин 1 курса 2026/2027 · поиск по официальным syllabus</p></div></header>
<div id="chat"><div class="hint">Примеры: «Как сдаётся математический анализ?», «Что изучают в информатике?», «Литература по дискретной математике», «Сколько кредитов даёт физика?»</div></div>
<form id="f"><input id="q" placeholder="Спросите про дисциплину, оценивание, литературу…" autocomplete="off"><button>Спросить</button></form>
<script>
const chat=document.getElementById('chat');
function add(cls,html){const d=document.createElement('div');d.className='msg '+cls;d.innerHTML=html;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d}
document.getElementById('f').onsubmit=async e=>{
 e.preventDefault();const q=document.getElementById('q');const text=q.value.trim();if(!text)return;
 q.value='';add('user',text);const b=add('bot','думаю…');
 const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
 try{
  const r=await fetch('/api?q='+encodeURIComponent(text));
  const j=await r.json();
  const mode=j.mode==='llm'?'ответ LLM по найденным фрагментам':'выжимка из программ';
  let src=(j.sources||[]).map(s=>`<a href="${s.url}" target="_blank">📄 ${esc(s.course)} — ${esc(s.section)}</a>`).join('');
  b.innerHTML=`<span class="badge">${mode}</span>\\n${esc(j.answer)}${src?`<div class="src"><b>Источники:</b>${src}</div>`:''}`;
 }catch(err){b.innerHTML='Ошибка: '+err}
};
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif u.path == "/api":
            q = parse_qs(u.query).get("q", [""])[0]
            try:
                res = answer(q)
                self._send(200, json.dumps(res, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001
                self._send(500, json.dumps({"answer": f"Ошибка: {e}", "sources": [], "mode": "error"}))
        else:
            self._send(404, "not found", "text/plain")

    def log_message(self, *args):  # тише в консоли
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Помощник первокурсника: http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
