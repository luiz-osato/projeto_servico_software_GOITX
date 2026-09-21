import os
import shutil

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.ticket import gerar_chamado
from app.ticket_llm import transcrever_com_groq

try:
    from pathlib import Path

    from dotenv import load_dotenv

    _raiz = Path(__file__).resolve().parents[2]
    load_dotenv(_raiz / ".env")
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="Gerador de chamados")

_modelo_whisper = None


def _carregar_whisper():
    global _modelo_whisper
    if _modelo_whisper is not None:
        return _modelo_whisper
    try:
        import whisper
    except ImportError:
        return None

    nome = os.getenv("WHISPER_MODEL", "tiny")
    print(f"Carregando modelo de IA (Whisper {nome})...")
    _modelo_whisper = whisper.load_model(nome)
    print("Modelo carregado.")
    return _modelo_whisper


def _transcrever(arquivo: UploadFile) -> str:
    caminho_temp = f"temp_{arquivo.filename or 'audio.wav'}"
    with open(caminho_temp, "wb") as buffer:
        shutil.copyfileobj(arquivo.file, buffer)
    try:
        texto = transcrever_com_groq(caminho_temp, arquivo.filename or "audio.wav")
        if texto:
            return texto

        modelo = _carregar_whisper()
        if modelo is None:
            raise HTTPException(
                status_code=503,
                detail="Não foi possível transcrever o áudio. Envie o relato em texto.",
            )
        resultado = modelo.transcribe(caminho_temp, language="pt")
        return (resultado.get("text") or "").strip()
    finally:
        if os.path.exists(caminho_temp):
            os.remove(caminho_temp)


@app.get("/")
def raiz():
    return {"status": "ok", "servico": "gerador-de-chamados"}


@app.post("/transcrever")
async def transcrever_audio(file: UploadFile = File(...)):
    texto = _transcrever(file)
    return {"texto": texto}


class ChamadoTexto(BaseModel):
    texto: str
    tipo: str = Field(default="auto")


def _tipo_forcado(tipo: str) -> str | None:
    valor = (tipo or "auto").upper()
    return valor if valor in {"INC", "SR"} else None


def _montar_chamado(relato: str, tipo: str) -> dict:
    if not relato.strip():
        raise HTTPException(
            status_code=400,
            detail="Envie um áudio ou um texto descrevendo o problema.",
        )
    return gerar_chamado(relato, _tipo_forcado(tipo))


@app.post("/chamado")
async def criar_chamado(body: ChamadoTexto):
    return _montar_chamado(body.texto, body.tipo)


@app.post("/chamado-audio")
async def criar_chamado_audio(
    file: UploadFile = File(...),
    texto: str = Form(default=""),
    tipo: str = Form(default="auto"),
):
    transcrito = _transcrever(file)
    relato = f"{texto.strip()}\n{transcrito}".strip() if texto.strip() else transcrito
    return _montar_chamado(relato, tipo)
