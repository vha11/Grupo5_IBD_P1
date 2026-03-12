import json
import os
import time
import uuid

import pika
from pika.exceptions import AMQPConnectionError, ProbableAuthenticationError


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USERNAME = os.getenv("RABBITMQ_USERNAME", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "text_analysis_queue")


TEXTS = [
    "This product is amazing!",
    "I love this service",
    "The movie was great",
    "This was a bad experience",
    "I am not happy with the result",
    "The quality is excellent",
    "This is the worst product I have bought",
    "It was okay, nothing special",
    "I would buy it again",
    "The service was terrible"
]


def connect_to_rabbitmq():
    credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)

    while True:
        try:
            print("Intentando conectar a RabbitMQ...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    credentials=credentials,
                    heartbeat=60,
                    blocked_connection_timeout=30
                )
            )
            print("Conectado a RabbitMQ")
            return connection

        except ProbableAuthenticationError as e:
            print(f"Error de autenticación en RabbitMQ: {e}")
            print("Revisando de nuevo en 5 segundos...")
            time.sleep(5)

        except AMQPConnectionError as e:
            print(f"RabbitMQ aún no está listo: {e}")
            print("Reintentando en 5 segundos...")
            time.sleep(5)

        except Exception as e:
            print(f"Error inesperado al conectar con RabbitMQ: {e}")
            print("Reintentando en 5 segundos...")
            time.sleep(5)


def publish_tasks():
    connection = connect_to_rabbitmq()
    channel = connection.channel()

    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    print(f"Cola declarada: {RABBITMQ_QUEUE}")

    index = 0

    while True:
        task = {
            "task_id": str(uuid.uuid4()),
            "type": "text_analysis",
            "content": TEXTS[index % len(TEXTS)]
        }

        channel.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(task),
            properties=pika.BasicProperties(delivery_mode=2)
        )

        print(f"Tarea enviada: {task}")
        index += 1
        time.sleep(1)


if __name__ == "__main__":
    publish_tasks()