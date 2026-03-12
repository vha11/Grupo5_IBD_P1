import pika
import json
import uuid
import time
import os
import random
import logging

logging.basicConfig(level=logging.INFO, format='[PRODUCER] %(message)s')

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin")
TASK_RATE     = float(os.getenv("TASK_RATE", "1"))   # tareas por segundo

TASK_TYPES = ["text_analysis", "image_classification"]

def connect_rabbitmq():
    """Conecta a RabbitMQ con reintentos."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300
    )
    while True:
        try:
            connection = pika.BlockingConnection(params)
            logging.info(f"Conectado a RabbitMQ en {RABBITMQ_HOST}")
            return connection
        except Exception as e:
            logging.warning(f"No se pudo conectar, reintentando en 3s... ({e})")
            time.sleep(3)

def setup_queues(channel):
    """Declara las queues como durable=True para que sobrevivan reinicios."""
    channel.queue_declare(queue='text_tasks',  durable=True)
    channel.queue_declare(queue='image_tasks', durable=True)
    logging.info("Queues declaradas: text_tasks, image_tasks")

def publish_task(channel, task_type, content):
    """Publica una tarea en la queue correspondiente."""
    task = {
        "task_id": str(uuid.uuid4()),
        "type":    task_type,
        "content": content
    }

    # routing_key = nombre de la queue
    queue_name = "text_tasks" if task_type == "text_analysis" else "image_tasks"

    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(task),
        properties=pika.BasicProperties(
            delivery_mode=2  # persistente: el mensaje sobrevive restart de RabbitMQ
        )
    )
    logging.info(f"Publicada tarea {task['task_id'][:8]}... → {queue_name}")
    return task


TEXT_SAMPLES = [
    "This product is amazing! I love it.",
    "Terrible experience, never buying again.",
    "It was okay, nothing special.",
    "Absolutely fantastic, exceeded expectations!",
    "Not worth the money at all.",
    "Pretty decent, would recommend to a friend."
]

IMAGE_SAMPLES = [
    "image_001.jpg", "image_002.jpg", "image_003.jpg",
    "photo_cat.png", "photo_dog.png", "photo_bird.jpg"
]

def main():
    connection = connect_rabbitmq()
    channel = connection.channel()
    setup_queues(channel)

    interval = 1.0 / TASK_RATE   # segundos entre tareas
    task_count = 0

    logging.info(f"Iniciando producción: {TASK_RATE} tarea(s)/segundo")

    try:
        while True:
            # Alternar entre tipos de tarea
            task_type = random.choice(TASK_TYPES)

            if task_type == "text_analysis":
                content = random.choice(TEXT_SAMPLES)
            else:
                content = random.choice(IMAGE_SAMPLES)

            publish_task(channel, task_type, content)
            task_count += 1

            if task_count % 10 == 0:
                logging.info(f"Total tareas publicadas: {task_count}")

            time.sleep(interval)

    except KeyboardInterrupt:
        logging.info("Producer detenido.")
    finally:
        connection.close()

if __name__ == "__main__":
    main()
