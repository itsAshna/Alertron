FROM python:3.11-slim

WORKDIR /app
COPY service/requirements.txt /app/service/requirements.txt
RUN pip install --no-cache-dir -r /app/service/requirements.txt

COPY artifacts /app/artifacts
COPY service /app/service

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
