import pika
import json
import csv
import time
import os
import random
import socket
import requests
import logging
import threading
from datetime import datetime
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format='[IMAGE-AGENT] %(message)s')

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "grupo5")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "cbadenes")
LOGGER_URL    = os.getenv("LOGGER_URL", "http://localhost:8000")
CSV_PATH      = "/data/image_agent_results.csv"
HTTP_PORT     = int(os.getenv("HTTP_PORT", "8002"))
AGENT_ID      = socket.gethostname()

IMAGE_LABELS = ["dog", "cat", "bird", "car", "tree", "person", "building", "food"]

app = Flask(__name__)
tasks_db = {}
db_lock = threading.Lock()

def connect_rabbitmq():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials, heartbeat=600)
    while True:
        try:
            connection = pika.BlockingConnection(params)
            logging.info(f"Agente {AGENT_ID} conectado a RabbitMQ")
            return connection
        except Exception as e:
            logging.warning(f"Esperando RabbitMQ... ({e})")
            time.sleep(3)

def init_csv():
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'task_id', 'label', 'confidence', 'timestamp', 'agent_id'
            ])
            writer.writeheader()

def save_to_csv(result: dict):
    with open(CSV_PATH, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'task_id', 'label', 'confidence', 'timestamp', 'agent_id'
        ])
        writer.writerow(result)

def notify_logger(result: dict):
    try:
        requests.post(f"{LOGGER_URL}/results", json=result, timeout=3)
    except Exception as e:
        logging.warning(f"No se pudo notificar al logger: {e}")

def process_image_task(task: dict):
    task_id = task['task_id']

    with db_lock:
        tasks_db[task_id] = {
            "task_id": task_id,
            "type": "image_classification",
            "content": task["content"],
            "status": "processing",
            "result": None
        }

    logging.info(f"Clasificando imagen {task_id[:8]}... archivo: '{task['content']}'")

    time.sleep(random.uniform(3, 5))

    result = {
        "task_id":    task_id,
        "label":      random.choice(IMAGE_LABELS),
        "confidence": round(random.uniform(0.65, 0.99), 2),
        "timestamp":  datetime.now().isoformat(),
        "agent_id":   AGENT_ID
    }

    save_to_csv(result)
    notify_logger(result)

    with db_lock:
        tasks_db[task_id]["status"] = "done"
        tasks_db[task_id]["result"] = result

    logging.info(f"Clasificado: {task_id[:8]}... → {result['label']} ({result['confidence']})")

def process_task(ch, method, properties, body):
    task = json.loads(body)
    process_image_task(task)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def consume_tasks():
    init_csv()
    connection = connect_rabbitmq()
    channel = connection.channel()

    channel.queue_declare(queue='image_tasks', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='image_tasks', on_message_callback=process_task)

    logging.info(f"Agente {AGENT_ID} escuchando en queue 'image_tasks'...")

    try:
        channel.start_consuming()
    finally:
        connection.close()

@app.get("/")
def root():
    return {
        "agent": "image-agent",
        "agent_id": AGENT_ID,
        "status": "running",
        "endpoints": ["/tasks", "/tasks/<task_id>"]
    }

@app.post("/tasks")
def create_task():
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "Falta campo 'content'"}), 400

    task_id = f"img-{int(time.time()*1000)}-{random.randint(1000,9999)}"
    task = {
        "task_id": task_id,
        "type": "image_classification",
        "content": data["content"]
    }

    with db_lock:
        tasks_db[task_id] = {
            "task_id": task_id,
            "type": "image_classification",
            "content": data["content"],
            "status": "accepted",
            "result": None
        }

    thread = threading.Thread(target=process_image_task, args=(task,), daemon=True)
    thread.start()

    return jsonify({
        "message": "Tarea aceptada",
        "task_id": task_id,
        "status": "accepted"
    }), 202

@app.get("/tasks")
def get_tasks():
    with db_lock:
        return jsonify(list(tasks_db.values()))

@app.get("/tasks/<task_id>")
def get_task(task_id):
    with db_lock:
        task = tasks_db.get(task_id)

    if not task:
        return jsonify({"error": f"task_id '{task_id}' no encontrado"}), 404

    return jsonify(task)

if __name__ == "__main__":
    consumer_thread = threading.Thread(target=consume_tasks, daemon=True)
    consumer_thread.start()

    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False)