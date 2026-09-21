# Gerador de chamados — Serviços de Software 2026-1

Aplicação em dois containers Docker:

- **frontend**: interface Gradio (porta 7860)
- **backend**: API REST FastAPI (porta 8080)

## Funcionalidade

O usuário descreve um problema de TI por **voz** ou **texto**. O frontend envia o relato ao backend via API REST. O backend:

1. transcreve o áudio com o **Whisper da Groq** (ou o Whisper local no container);
2. redige o chamado em inglês com um **serviço de IA de terceiros** (Groq ou Gemini);
3. devolve título e descrição no formato INC ou SR, prontos para colar.

Se a chave da API não estiver configurada, o backend usa regras locais só como reserva.

## Chave do serviço de IA

Crie um arquivo `.env` na raiz do projeto (veja `.env.example`) com **uma** destas chaves gratuitas:

- Groq: https://console.groq.com/keys
- Gemini: https://aistudio.google.com/apikey

```sh
GROQ_API_KEY=sua_chave_aqui
```

## Como rodar com Docker

Com o Docker Desktop aberto:

```sh
docker compose up --build
```

- Interface: http://localhost:7860
- API: http://localhost:8080

## Como rodar sem Docker

Útil para desenvolver e testar o fluxo de texto. O Whisper continua no `Dockerfile` do backend para a entrega em containers.

Terminal 1:

```sh
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install fastapi pydantic uvicorn python-multipart python-dotenv
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Terminal 2:

```sh
cd frontend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Sem Whisper instalado, envie o relato pelo campo de texto.
