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

logging.basicConfig(level=logging.INFO, format='[TEXT-AGENT] %(message)s')

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin")
LOGGER_URL    = os.getenv("LOGGER_URL", "http://localhost:8000")
CSV_PATH      = "/data/text_agent_results.csv"


AGENT_ID = socket.gethostname()

def connect_rabbitmq():
    """Conecta a RabbitMQ con reintentos automáticos."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        credentials=credentials,
        heartbeat=600
    )
    while True:
        try:
            connection = pika.BlockingConnection(params)
            logging.info(f"Agente {AGENT_ID} conectado a RabbitMQ")
            return connection
        except Exception as e:
            logging.warning(f"Esperando RabbitMQ... ({e})")
            time.sleep(3)

def init_csv():
    """Crea el CSV con cabeceras si no existe."""
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'task_id', 'sentiment', 'confidence', 'timestamp', 'agent_id'
            ])
            writer.writeheader()
        logging.info(f"CSV creado en {CSV_PATH}")

def simulate_sentiment(content: str) -> tuple[str, float]:
    """
    Simula análisis de sentimiento.
    En producción real aquí iría un modelo de NLP.
    """
    
    positive_words = ['amazing', 'fantastic', 'love', 'great', 'excellent', 'wonderful']
    negative_words = ['terrible', 'awful', 'hate', 'bad', 'worst', 'never']

    content_lower = content.lower()
    pos_count = sum(1 for w in positive_words if w in content_lower)
    neg_count = sum(1 for w in negative_words if w in content_lower)

    if pos_count > neg_count:
        sentiment = "positive"
        confidence = round(random.uniform(0.75, 0.99), 2)
    elif neg_count > pos_count:
        sentiment = "negative"
        confidence = round(random.uniform(0.70, 0.95), 2)
    else:
        sentiment = "neutral"
        confidence = round(random.uniform(0.55, 0.80), 2)

    return sentiment, confidence

def save_to_csv(result: dict):
    """Guarda resultado en CSV. Thread-safe para una sola instancia."""
    with open(CSV_PATH, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'task_id', 'sentiment', 'confidence', 'timestamp', 'agent_id'
        ])
        writer.writerow(result)

def notify_logger(result: dict):
    """Notifica al Task Logger central. No bloquea si el logger no está disponible."""
    try:
        requests.post(
            f"{LOGGER_URL}/results",
            json=result,
            timeout=3
        )
    except Exception as e:
        logging.warning(f"No se pudo notificar al logger: {e}")

def process_task(ch, method, properties, body):
    """
    Callback que se ejecuta por cada tarea recibida.
    ORDEN CRÍTICO: guardar → notificar → ACK
    Si el agente muere antes del ACK, RabbitMQ re-entrega la tarea.
    """
    task = json.loads(body)
    task_id = task['task_id']

    logging.info(f"Procesando tarea {task_id[:8]}... contenido: '{task['content'][:40]}'")

    
    processing_time = random.uniform(3, 5)
    time.sleep(processing_time)

    
    sentiment, confidence = simulate_sentiment(task['content'])
    result = {
        "task_id":    task_id,
        "sentiment":  sentiment,
        "confidence": confidence,
        "timestamp":  datetime.now().isoformat(),
        "agent_id":   AGENT_ID
    }

    # guardamos en CSV 
    save_to_csv(result)
    logging.info(f"Resultado guardado: {task_id[:8]}... → {sentiment} ({confidence})")

    # luego le notificamps al Task Logger
    notify_logger(result)

    # ACK al broker (confirma que procesamos correctamente), esto soolo después de guardar, si falla antes el mensaje se re-entrega
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    init_csv()
    connection = connect_rabbitmq()
    channel = connection.channel()

    # Declarar queue (si ya existe no pasa nada)
    channel.queue_declare(queue='text_tasks', durable=True)

    # prefetch=1: el agente solo recibe UNA tarea a la vez
    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue='text_tasks',
        on_message_callback=process_task
    )

    logging.info(f"Agente {AGENT_ID} escuchando en queue 'text_tasks'...")
    logging.info("Presiona CTRL+C para detener")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()

if __name__ == "__main__":
    main()
