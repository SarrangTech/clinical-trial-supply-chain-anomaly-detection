FROM python:3.11-slim

WORKDIR /opt/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline ./pipeline
COPY api ./api

ENV PYTHONPATH=/opt/app

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
