FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PRIORIZA_DATA_DIR=/var/lib/prioriza

WORKDIR /app
COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt waitress==3.0.2 \
    && useradd --system --no-create-home prioriza \
    && mkdir -p /var/lib/prioriza \
    && chown prioriza:prioriza /var/lib/prioriza

COPY app.py imagens.py multimodal.py storage.py triagem.py ./
COPY frontend/ ./frontend/
COPY modelo/arvore.json ./modelo/arvore.json
RUN chmod -R a+rX /app

USER prioriza
EXPOSE 5000
VOLUME ["/var/lib/prioriza"]
CMD ["waitress-serve", "--listen=0.0.0.0:5000", "--max-request-body-size=6291456", "app:app"]
