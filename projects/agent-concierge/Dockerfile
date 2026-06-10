FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY concierge.py .
ENV PYTHONPATH=/app
CMD ["python", "concierge.py"]
