"""Gera INC/SR com um serviço de IA de terceiros (Groq ou Gemini)."""

from __future__ import annotations

import json
import os
import re
import uuid
import urllib.error
import urllib.request

SYSTEM_PROMPT = """You write IT support tickets in English, ready to paste.

Rules:
- Always write title and description in English, even if the user wrote in another language.
- Use only facts from the user. Do not invent systems, error codes, URLs, or case IDs.
- If the user selected INC or SR, keep that type. Otherwise choose INC for errors/failures and SR for improvements.
- Title: one specific searchable line. Do not prefix with tags like [SAP] or [OCV]. Do not start with narrative fluff such as "My team told me that".
- Do not use markdown bold (**).
- If case/order IDs appear in the text, list them in Cases / Examples. If none, use [TBD].

INC description format exactly:
## Summary
[1-2 factual sentences: what is wrong]

## Request
[What should be done]

## Cases / Examples
[IDs, or [TBD]]

SR description format exactly:
## 1. Problem and expected impact
[...]

## 2. Expected benefits
[...]

## 3. Expected result after implementation
[...]

Return ONLY valid JSON:
{"tipo":"INC","titulo":"...","descricao":"..."}
"""


def transcrever_com_groq(caminho: str, nome_arquivo: str = "audio.wav") -> str:
    chave = os.getenv("GROQ_API_KEY", "").strip()
    if not chave:
        return ""

    with open(caminho, "rb") as arquivo:
        audio = arquivo.read()
    if not audio:
        return ""

    boundary = uuid.uuid4().hex
    modelo = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")
    corpo = b"".join(
        [
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{nome_arquivo}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
            + audio
            + b"\r\n",
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="model"\r\n\r\n'
                f"{modelo}\r\n"
            ).encode(),
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="language"\r\n\r\n'
                "pt\r\n"
            ).encode(),
            f"--{boundary}--\r\n".encode(),
        ]
    )
    requisicao = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=corpo,
        headers={
            "Authorization": f"Bearer {chave}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "gerador-chamados/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=60) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        return (dados.get("text") or "").strip()
    except urllib.error.HTTPError as exc:
        detalhe = exc.read().decode("utf-8", "replace")[:300]
        print(f"Groq transcrição indisponível: HTTP {exc.code} {detalhe}")
        return ""
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        print(f"Groq transcrição indisponível: {exc}")
        return ""


def gerar_com_llm(relato: str, tipo_forcado: str | None = None) -> dict | None:
    tipo = f" The ticket type must be {tipo_forcado}." if tipo_forcado in {"INC", "SR"} else ""
    user = f"User report:\n{relato.strip()}{tipo}"

    bruto = _chamar_groq(user) or _chamar_gemini(user)
    if not bruto:
        return None
    return _parsear(bruto, relato)


def _chamar_groq(user: str) -> str:
    chave = os.getenv("GROQ_API_KEY", "").strip()
    if not chave:
        return ""

    corpo = {
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    requisicao = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {chave}",
            "User-Agent": "gerador-chamados/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=30) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        return dados["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        detalhe = exc.read().decode("utf-8", "replace")[:300]
        print(f"Groq indisponível: HTTP {exc.code} {detalhe}")
        return ""
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
        print(f"Groq indisponível: {exc}")
        return ""


def _chamar_gemini(user: str) -> str:
    chave = os.getenv("GEMINI_API_KEY", "").strip()
    if not chave:
        return ""

    modelo = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{modelo}:generateContent?key={chave}"
    )
    corpo = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    requisicao = urllib.request.Request(
        url,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "gerador-chamados/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=30) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        return dados["candidates"][0]["content"]["parts"][0]["text"]
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
        print(f"Gemini indisponível: {exc}")
        return ""


def _parsear(bruto: str, relato: str) -> dict | None:
    texto = bruto.strip()
    bloco = re.search(r"\{.*\}", texto, flags=re.S)
    if not bloco:
        return None
    try:
        dados = json.loads(bloco.group(0))
    except json.JSONDecodeError:
        return None

    tipo = str(dados.get("tipo", "INC")).upper()
    if tipo not in {"INC", "SR"}:
        tipo = "INC"
    titulo = " ".join(str(dados.get("titulo", "")).split())
    descricao = str(dados.get("descricao", "")).strip()
    if not titulo or not descricao:
        return None

    return {
        "tipo": tipo,
        "titulo": titulo,
        "descricao": descricao,
        "texto_origem": relato.strip(),
        "fonte": "llm",
        "texto_para_colar": (
            f"Type: {tipo}\n\nTitle:\n{titulo}\n\nDescription:\n{descricao}"
        ),
    }
