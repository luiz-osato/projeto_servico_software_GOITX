import os

import gradio as gr
import requests

BACKEND_URL = os.getenv("BACKEND_URL") or (
    "http://backend:8080" if os.path.exists("/.dockerenv") else "http://localhost:8080"
)


def gerar(audio_path, texto, tipo):
    if not audio_path and not (texto or "").strip():
        return "", "", "", "Informe um áudio ou descreva o problema em texto."

    arquivo_aberto = None
    try:
        if audio_path:
            arquivo_aberto = open(audio_path, "rb")
            resposta = requests.post(
                f"{BACKEND_URL}/chamado-audio",
                data={"texto": texto or "", "tipo": tipo},
                files={"file": ("audio.wav", arquivo_aberto, "audio/wav")},
                timeout=120,
            )
        else:
            resposta = requests.post(
                f"{BACKEND_URL}/chamado",
                json={"texto": texto, "tipo": tipo},
                timeout=30,
            )
    except Exception as exc:
        return "", "", "", f"Erro de conexão com o backend: {exc}"
    finally:
        if arquivo_aberto:
            arquivo_aberto.close()

    if resposta.status_code != 200:
        try:
            detalhe = resposta.json().get("detail", resposta.text)
        except ValueError:
            detalhe = resposta.text
        return "", "", "", f"Erro no servidor ({resposta.status_code}): {detalhe}"

    corpo = resposta.json()
    return (
        corpo.get("tipo", ""),
        corpo.get("titulo", ""),
        corpo.get("descricao", ""),
        corpo.get("texto_para_colar", ""),
    )


with gr.Blocks(title="Gerador de chamados") as demo:
    gr.Markdown(
        """
        # Gerador de chamados (INC / SR)

        Descreva o problema por voz ou texto e escolha INC ou SR. O frontend envia
        o relato ao backend via API REST. O backend transcreve o áudio com Whisper
        e devolve título e descrição em inglês, prontos para colar.
        """
    )

    with gr.Row():
        audio = gr.Audio(type="filepath", label="Áudio (opcional)")
        texto = gr.Textbox(
            label="Relato em texto",
            lines=8,
            placeholder=(
                "Ex.: O relatório de vendas não abre desde hoje de manhã. "
                "Aparece erro 500 quando clico em Exportar. Já tentei outro navegador."
            ),
        )

    tipo = gr.Radio(
        choices=["INC", "SR"],
        value="INC",
        label="Tipo do chamado",
    )
    botao = gr.Button("Gerar chamado", variant="primary")

    tipo_saida = gr.Textbox(label="Tipo")
    titulo = gr.Textbox(label="Título (inglês)")
    descricao = gr.Textbox(label="Descrição (inglês)", lines=12)
    colar = gr.Textbox(label="Texto pronto para colar", lines=16)

    botao.click(
        fn=gerar,
        inputs=[audio, texto, tipo],
        outputs=[tipo_saida, titulo, descricao, colar],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
