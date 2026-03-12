import pika
import json
import csv
import time
import os
import random
import socket
import requests
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='[IMAGE-AGENT] %(message)s')

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin")
LOGGER_URL    = os.getenv("LOGGER_URL", "http://localhost:8000")
CSV_PATH      = "/data/image_agent_results.csv"
AGENT_ID      = socket.gethostname()

IMAGE_LABELS  = ["dog", "cat", "bird", "car", "tree", "person", "building", "food"]

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

def process_task(ch, method, properties, body):
    task = json.loads(body)
    task_id = task['task_id']

    logging.info(f"Clasificando imagen {task_id[:8]}... archivo: '{task['content']}'")

    
    time.sleep(random.uniform(3, 5)) # aqupi puse lo del requsiito de que la tarea tarde de entre 3 a 5 segundos

    result = {
        "task_id":    task_id,
        "label":      random.choice(IMAGE_LABELS),
        "confidence": round(random.uniform(0.65, 0.99), 2),
        "timestamp":  datetime.now().isoformat(),
        "agent_id":   AGENT_ID
    }

    save_to_csv(result)
    logging.info(f"Clasificado: {task_id[:8]}... → {result['label']} ({result['confidence']})")

    notify_logger(result)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    init_csv()
    connection = connect_rabbitmq()
    channel = connection.channel()

    channel.queue_declare(queue='image_tasks', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='image_tasks', on_message_callback=process_task)

    logging.info(f"Agente {AGENT_ID} escuchando en queue 'image_tasks'...")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()

if __name__ == "__main__":
    main()
