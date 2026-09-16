FROM python:3.11.5

ARG GRADIO_SERVER_PORT=7860
ENV GRADIO_SERVER_PORT=${GRADIO_SERVER_PORT}

WORKDIR /work

COPY requirements.txt app.py /work/

RUN pip install --no-cache-dir -r /work/requirements.txt

EXPOSE 7860

CMD ["python", "/work/app.py"]
