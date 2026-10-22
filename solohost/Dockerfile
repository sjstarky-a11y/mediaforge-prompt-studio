FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app/main.py /app/main.py
COPY app/serve.py /app/serve.py
COPY app/startup.html /app/startup.html
COPY app/fidelity_concepts.py /app/fidelity_concepts.py
COPY app/model_catalog.py /app/model_catalog.py
COPY app/runtime_status.py /app/runtime_status.py
COPY app/index.html /app/index.html
COPY app/assets /app/assets
COPY models /models

EXPOSE 8080

CMD ["python", "serve.py"]
