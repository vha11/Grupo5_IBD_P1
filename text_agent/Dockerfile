FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY text_agent.py .
RUN mkdir -p /data
CMD ["python", "text_agent.py"]
