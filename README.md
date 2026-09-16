# Projeto — Serviços de Software 2026-1

Aplicação em dois containers Docker:

- **frontend**: interface Gradio (porta 7860)
- **backend**: API REST FastAPI (porta 8080)

Por enquanto o backend transcreve áudio com Whisper (modelo de terceiros). A funcionalidade ligada ao trabalho ainda será definida.

## Como rodar

Com o Docker Desktop aberto:

```sh
docker compose up --build
```

- Interface: http://localhost:7860
- API: http://localhost:8080
