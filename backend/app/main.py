import os
import shutil

import whisper
from fastapi import FastAPI, File, UploadFile

app = FastAPI(title="Backend do projeto")

# tiny = mais leve no PC; depois podemos trocar para base se quiser mais qualidade
modelo_nome = os.getenv("WHISPER_MODEL", "tiny")
print(f"Carregando modelo de IA (Whisper {modelo_nome})...")
model = whisper.load_model(modelo_nome)
print("Modelo carregado.")


@app.get("/")
def raiz():
    return {"status": "ok", "servico": "backend"}


@app.post("/transcrever")
async def transcrever_audio(file: UploadFile = File(...)):
    """Placeholder: transcreve áudio. A regra de negócio do trabalho entra depois."""
    caminho_temp = f"temp_{file.filename}"
    with open(caminho_temp, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        resultado = model.transcribe(caminho_temp, language="pt")
        texto = resultado["text"].strip()
    finally:
        if os.path.exists(caminho_temp):
            os.remove(caminho_temp)

    return {"texto": texto}
