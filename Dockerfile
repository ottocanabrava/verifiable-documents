FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Um processo só: o rate limit fica em memória (ver app.py) e o serviço roda
# com no máximo 1 instância no Cloud Run.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 60 app:app
