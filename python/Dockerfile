FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Sem root: a aplicação só lê os arquivos da imagem (o PDF é gerado em memória).
RUN useradd --system --no-create-home app
USER app
# Um processo só: o rate limit fica em memória (ver app.py), então rode uma
# única instância do contêiner.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 60 app:app
