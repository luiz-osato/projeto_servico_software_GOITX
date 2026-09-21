"""Monta chamados INC/SR em inglês a partir de um relato livre.

Prefere um serviço de IA de terceiros. Se a API não estiver
configurada ou falhar, usa regras locais como reserva.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from app.ticket_llm import gerar_com_llm

INC_KEYWORDS = (
    "erro",
    "error",
    "bug",
    "falha",
    "falhou",
    "quebra",
    "quebrou",
    "travou",
    "travando",
    "lento",
    "timeout",
    "indisponivel",
    "indisponível",
    "fora do ar",
    "crash",
    "exception",
    "nao funciona",
    "não funciona",
    "nao abre",
    "não abre",
    "nao carrega",
    "não carrega",
    "cannot",
    "can't",
    "unable",
    "unexpected",
    "failed",
    "broken",
    "down",
    "not being created",
    "not generated",
    "not created",
)

SR_KEYWORDS = (
    "melhoria",
    "melhorar",
    "gostaria",
    "seria bom",
    "adicionar",
    "incluir",
    "implementar",
    "automatizar",
    "sugestao",
    "sugestão",
    "enhancement",
    "improvement",
    "feature",
    "would like",
    "please add",
    "novo recurso",
)

PT_HINTS = (
    "não",
    "nao",
    "que",
    "uma",
    "para",
    "quando",
    "está",
    "esta",
    "erro",
    "falha",
    "gostaria",
    "melhoria",
    "chamado",
    "sistema",
    "relatório",
    "relatorio",
)

_NARRATIVA = re.compile(
    r"^\s*(?:"
    r"(?:but|and)\s+|"
    r"my team (?:told|said|informed)(?:\s+me)? that|"
    r"the team (?:told|said)(?:\s+me)? that|"
    r"(?:my|our) team(?:'s)? (?:feedback|update) is that|"
    r"(?:my|our) team (?:is|are|told me)\s+|"
    r"i was told that|"
    r"they told me that|"
    r"i have been (?:having|seeing|facing)(?:\s+an?)?(?:\s+\w+)?|"
    r"i(?:'m| am) (?:having|seeing|facing)|"
    r"please note that|"
    r"i would like(?: an improvement)? to\s+|"
    r"here are examples[^,.]*[,.]"
    r")\s*",
    re.I,
)

_TEMPO_INICIO = re.compile(
    r"^\s*(?:since|from|starting(?:\s+from)?)\s+"
    r"(?:today(?:\s+in\s+the\s+morning)?|yesterday|this morning|this afternoon|"
    r"last night|the morning)\s*,?\s*",
    re.I,
)

_QUANDO = re.compile(
    r"\b(?:since|from)\s+(today in the morning|this morning|yesterday|today|this afternoon)\b",
    re.I,
)

_PROBLEMA = re.compile(
    r"("
    r"[A-Za-z][^.]*?\s+(?:are|is|were|was)\s+not\s+(?:being\s+)?\w+[^.]*?|"
    r"[A-Za-z][^.]*?\s+(?:do not|does not|don't|doesn't)\s+\w+[^.]*?|"
    r"(?:unable|not able|cannot|can'?t|failed)\s+to\s+[^.]+|"
    r"[A-Za-z][^.]*?\s+not\s+(?:created|generated|opened|working|available)[^.]*"
    r")",
    re.I,
)

_ONDE_INTERFACE = re.compile(
    r"interface between\s+([^.,;]+?)(?=\s+(?:since|from|today|yesterday|this|last)|\s*[.,;!]|$)",
    re.I,
)

_IDS = re.compile(
    r"\b(?:INC|SR|CHG)[- ]?\d+\b|\b[A-Z]{2,}[-_]\d+\b|#\d+\b|\b\d{6,}\b",
    re.I,
)


def gerar_chamado(relato: str, tipo_forcado: str | None = None) -> dict:
    texto = " ".join((relato or "").split())
    gerado = gerar_com_llm(texto, tipo_forcado)
    if gerado:
        return gerado

    tipo = _classificar(texto, tipo_forcado)
    ingles = _para_ingles(texto)
    fatos = _extrair_fatos(ingles, texto)
    titulo = fatos["titulo"]
    descricao = _descricao_inc(fatos) if tipo == "INC" else _descricao_sr(fatos, ingles)

    return {
        "tipo": tipo,
        "titulo": titulo,
        "descricao": descricao,
        "texto_origem": relato.strip(),
        "fonte": "regras",
        "texto_para_colar": (
            f"Type: {tipo}\n\nTitle:\n{titulo}\n\nDescription:\n{descricao}"
        ),
    }


def _classificar(texto: str, tipo_forcado: str | None) -> str:
    if tipo_forcado in {"INC", "SR"}:
        return tipo_forcado

    normalizado = _normalizar(texto)
    tem_inc = any(palavra in normalizado for palavra in INC_KEYWORDS)
    tem_sr = any(palavra in normalizado for palavra in SR_KEYWORDS)
    if tem_inc:
        return "INC"
    if tem_sr:
        return "SR"
    return "INC"


def _para_ingles(texto: str) -> str:
    if not texto or _parece_ingles(texto):
        return texto
    traduzido = _traduzir(texto)
    return traduzido or texto


def _parece_ingles(texto: str) -> bool:
    minusculo = texto.lower()
    if any(hint in minusculo for hint in PT_HINTS) or any(
        letra in texto for letra in "ãáàâçéêíóôõú"
    ):
        return False
    return True


def _traduzir(texto: str) -> str:
    partes = _partir(texto, 450)
    blocos = []
    for parte in partes:
        bloco = _traduzir_bloco(parte)
        if not bloco:
            return ""
        blocos.append(bloco)
    return " ".join(blocos).strip()


def _traduzir_bloco(texto: str) -> str:
    query = urllib.parse.urlencode({"q": texto, "langpair": "pt|en"})
    url = f"https://api.mymemory.translated.net/get?{query}"
    try:
        with urllib.request.urlopen(url, timeout=8) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
        return (dados.get("responseData") or {}).get("translatedText", "").strip()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return ""


def _partir(texto: str, limite: int) -> list[str]:
    if len(texto) <= limite:
        return [texto]

    partes: list[str] = []
    atual = ""
    for pedaco in re.split(r"(?<=[.!?])\s+", texto):
        candidato = f"{atual} {pedaco}".strip()
        if atual and len(candidato) > limite:
            partes.append(atual)
            atual = pedaco
        else:
            atual = candidato
    if atual:
        partes.append(atual)
    return partes


def _extrair_fatos(ingles: str, original: str) -> dict:
    limpo = _limpar_relato(ingles)
    casos = _exemplos(original, ingles)
    problema = _extrair_problema(_sem_ids(limpo))
    onde = _extrair_onde(limpo)
    quando = _extrair_quando(ingles)
    titulo = _montar_titulo(problema, onde, limpo)
    resumo = _montar_resumo(problema, onde, quando, limpo)
    pedido = _montar_pedido(limpo, casos)
    return {
        "titulo": titulo,
        "resumo": resumo,
        "pedido": pedido,
        "casos": casos or "[TBD]",
        "limpo": limpo,
    }


def _limpar_relato(texto: str) -> str:
    atual = _corrigir_typos(texto)
    mudou = True
    while mudou:
        seguinte = _NARRATIVA.sub("", atual)
        seguinte = _TEMPO_INICIO.sub("", seguinte)
        seguinte = seguinte.lstrip(" ,.-")
        mudou = seguinte != atual
        atual = seguinte
    return re.sub(r"\s+", " ", atual).strip(" .")


def _corrigir_typos(texto: str) -> str:
    texto = re.sub(r"\breturns orders\b", "return orders", texto, flags=re.I)
    texto = re.sub(r"\breturn order\b", "return orders", texto, flags=re.I)
    return texto


def _sem_ids(texto: str) -> str:
    return _IDS.sub("", texto)


def _extrair_problema(texto: str) -> str:
    candidatos = []
    for frase in re.split(r"(?<=[.!?])\s+|,(?=\s+[A-Za-z])", texto):
        frase = _limpar_relato(frase)
        if not frase or len(frase.split()) < 3:
            continue
        if _PROBLEMA.search(frase) or re.search(
            r"\bnot\b|\bunable\b|\berror\b|\bfail", frase, re.I
        ):
            candidatos.append(frase.strip(" ."))
    if not candidatos:
        return ""
    return max(candidatos, key=_pontuar_problema)


def _pontuar_problema(frase: str) -> int:
    pontos = len(frase)
    if re.search(r"\bnot being (?:created|generated|opened)\b", frase, re.I):
        pontos += 40
    if re.search(r"\bunable to\b|\bcannot\b|\bdoes not\b", frase, re.I):
        pontos += 30
    if re.search(r"\b(create|created|generate|generated|open|opened)\b", frase, re.I):
        pontos += 20
    if re.search(r"\b[A-Z]{2,}\b", frase):
        pontos += 15
    if re.match(r"^(but|and|here)\b", frase, re.I):
        pontos -= 40
    if len(frase.split()) < 5:
        pontos -= 20
    return pontos


def _extrair_onde(texto: str) -> str:
    padrao = _ONDE_INTERFACE.search(texto)
    if not padrao:
        return ""
    partes = re.split(r"\s+and\s+", padrao.group(1).strip(), flags=re.I)
    if len(partes) == 2:
        return f"the {partes[0].strip()}-{partes[1].strip()} interface"
    return f"the {padrao.group(1).strip()} interface"


def _extrair_quando(texto: str) -> str:
    padrao = _QUANDO.search(texto)
    if not padrao:
        return ""
    valor = padrao.group(1).lower()
    if valor in {"today in the morning", "the morning"}:
        valor = "this morning"
    return f"since {valor}"


def _montar_titulo(problema: str, onde: str, limpo: str) -> str:
    base = problema or limpo
    base = _compactar_titulo(base)
    if onde and "interface" not in base.lower():
        base = f"{base} in {onde}"
    return _capitalizar(_cortar(base, 90)) or "Support ticket"


def _compactar_titulo(texto: str) -> str:
    texto = re.sub(r"\b(are|is|were|was)\s+not\s+being\s+", "not ", texto, flags=re.I)
    texto = re.sub(r"\b(are|is|were|was)\s+not\s+", "not ", texto, flags=re.I)
    texto = re.sub(r"\bthe\s+([A-Z]{2,})\b", r"\1", texto)
    texto = re.sub(r"\bhere are examples.+$", "", texto, flags=re.I)
    texto = _QUANDO.sub("", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .,")
    return texto


def _montar_resumo(problema: str, onde: str, quando: str, limpo: str) -> str:
    frase = (problema or limpo).rstrip(".")
    frase = re.sub(r"\bhere are examples.+$", "", frase, flags=re.I).strip(" .,")
    if onde and "interface" not in frase.lower():
        frase = f"{frase} in {onde}"
    if quando and quando not in frase.lower():
        frase = f"{frase} {quando}"
    return _capitalizar(frase) + "."


def _montar_pedido(limpo: str, casos: str) -> str:
    if casos and re.search(r"not (?:being )?(?:created|generated)", limpo, re.I):
        return (
            "Please investigate why the listed cases are not generating orders "
            "and apply the necessary correction."
        )
    return "Please investigate the reported issue and apply the necessary correction."


def _descricao_inc(fatos: dict) -> str:
    return (
        f"## Summary\n{fatos['resumo']}\n\n"
        f"## Request\n{fatos['pedido']}\n\n"
        f"## Cases / Examples\n{fatos['casos']}"
    )


def _descricao_sr(fatos: dict, ingles: str) -> str:
    impacto = fatos["resumo"]
    return (
        f"## 1. Problem and expected impact\n{impacto}\n\n"
        f"## 2. Expected benefits\n[TBD]\n\n"
        f"## 3. Expected result after implementation\n[TBD]"
    )


def _exemplos(*textos: str) -> str:
    juntos = " ".join(textos)
    achados = _IDS.findall(juntos)
    return ", ".join(dict.fromkeys(achados))


def _cortar(titulo: str, limite: int) -> str:
    titulo = re.sub(r"\s+", " ", titulo).strip(" .")
    if len(titulo) > limite:
        return titulo[:limite].rsplit(" ", 1)[0]
    return titulo


def _capitalizar(titulo: str) -> str:
    if not titulo:
        return ""
    return titulo[0].upper() + titulo[1:]


def _normalizar(texto: str) -> str:
    return (
        texto.lower()
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
