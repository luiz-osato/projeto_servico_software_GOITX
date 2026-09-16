import os

import gradio as gr
import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8080")


def processa_audio(audio_path):
    if audio_path is None:
        return "Nenhum áudio recebido."

    with open(audio_path, "rb") as f:
        files = {"file": ("audio.wav", f, "audio/wav")}
        try:
            response = requests.post(
                f"{BACKEND_URL}/transcrever",
                files=files,
                timeout=120,
            )
            if response.status_code == 200:
                return response.json().get("texto", "Erro ao extrair texto.")
            return f"Erro no servidor: {response.status_code}"
        except Exception as e:
            return f"Erro de conexão com o backend: {str(e)}"


demo = gr.Interface(
    fn=processa_audio,
    inputs=gr.Audio(type="filepath", label="Grave sua voz ou envie um áudio"),
    outputs=gr.Textbox(label="Texto transcrito"),
    title="Assistente de voz (esqueleto do projeto)",
    description=(
        "Esqueleto da avaliação: o frontend envia o áudio para o backend via API REST. "
        "A funcionalidade de negócio ainda será definida."
    ),
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
