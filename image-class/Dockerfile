FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY image-class.py .

CMD ["python", "image-class.py"]