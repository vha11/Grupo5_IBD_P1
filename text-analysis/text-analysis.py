import json
import os
import random
import time
from datetime import datetime

import pika
from pika.exceptions import AMQPConnectionError, ProbableAuthenticationError


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USERNAME = os.getenv("RABBITMQ_USERNAME", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "text_analysis_queue")


POSITIVE_WORDS = ["amazing", "love", "great", "happy", "excellent", "good", "best"]
NEGATIVE_WORDS = ["bad", "worst", "terrible", "not happy", "awful", "poor"]


def connect_to_rabbitmq():
    credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)

    while True:
        try:
            print("Text Analysis intentando conectar a RabbitMQ...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    credentials=credentials,
                    heartbeat=60,
                    blocked_connection_timeout=30
                )
            )
            print("Text Analysis conectado a RabbitMQ")
            return connection

        except ProbableAuthenticationError as e:
            print(f"Error de autenticación en RabbitMQ: {e}")
            print("Reintentando en 5 segundos...")
            time.sleep(5)

        except AMQPConnectionError as e:
            print(f"RabbitMQ aún no está listo para text_analysis: {e}")
            print("Reintentando en 5 segundos...")
            time.sleep(5)

        except Exception as e:
            print(f"Error inesperado en text_analysis: {e}")
            print("Reintentando en 5 segundos...")
            time.sleep(5)


def analyze_sentiment(text):
    text_lower = text.lower()
    positive_score = sum(word in text_lower for word in POSITIVE_WORDS)
    negative_score = sum(word in text_lower for word in NEGATIVE_WORDS)

    if positive_score > negative_score:
        return "positive", round(random.uniform(0.75, 0.95), 2)
    elif negative_score > positive_score:
        return "negative", round(random.uniform(0.75, 0.95), 2)
    else:
        return "neutral", round(random.uniform(0.50, 0.70), 2)


def callback(ch, method, properties, body):
    task = json.loads(body)
    print(f"Tarea recibida: {task}")

    processing_time = random.randint(3, 5)
    print(f"Procesando tarea durante {processing_time} segundos...")
    time.sleep(processing_time)

    sentiment, confidence = analyze_sentiment(task.get("content", ""))

    result = {
        "task_id": task.get("task_id"),
        "sentiment": sentiment,
        "confidence": confidence,
        "timestamp": datetime.now().isoformat()
    }

    print(f"Resultado generado: {result}")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def consume_tasks():
    connection = connect_to_rabbitmq()
    channel = connection.channel()

    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

    print(f"Esperando tareas en la cola: {RABBITMQ_QUEUE}")
    channel.start_consuming()


if __name__ == "__main__":
    consume_tasks()