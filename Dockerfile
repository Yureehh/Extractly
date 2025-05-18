# Use official Python image
FROM python:3.11-slim
WORKDIR /app

# Install system deps for OCR and PDF processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      poppler-utils \
      tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV OPENAI_API_KEY=""
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]