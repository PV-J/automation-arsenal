FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY invoice_pipeline.py .
RUN mkdir -p /app/results /app/logs /app/sample_data
CMD ["python", "invoice_pipeline.py"]
