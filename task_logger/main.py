from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from collections import Counter
import logging
import csv
import os
import pika
import json
import threading
import time

logging.basicConfig(level=logging.INFO, format='[TASK-LOGGER] %(message)s')

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "grupo5")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "cbadenes")

app = FastAPI(
    title="Task Logger — IBD Práctica 1",
    description="API central agentes de IA",
    version="2.0.0"
)

results_db: list[dict] = []
CSV_PATH = "/data/tasks_log.csv"

class TaskResult(BaseModel):
    task_id:    str
    timestamp:  Optional[str] = None
    agent_id:   Optional[str] = None
    sentiment:  Optional[str] = None
    confidence: Optional[float] = None
    label:      Optional[str] = None

def init_csv():
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "task_id", "agent", "result", "confidence", "timestamp"
            ])
            writer.writeheader()

def append_to_csv(entry: dict):
    result_value = entry.get("sentiment") if entry.get("sentiment") is not None else entry.get("label")
    row = {
        "task_id": entry["task_id"],
        "agent": entry.get("agent_id", "unknown"),
        "result": result_value,
        "confidence": entry.get("confidence"),
        "timestamp": entry["timestamp"]
    }
    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "task_id", "agent", "result", "confidence", "timestamp"
        ])
        writer.writerow(row)

def load_csv():
    if not os.path.exists(CSV_PATH):
        return
    with open(CSV_PATH, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry = {
                "task_id":    row["task_id"],
                "agent_id":   row["agent"],
                "timestamp":  row["timestamp"],
                "confidence": float(row["confidence"]) if row["confidence"] else None,
                "sentiment":  row["result"] if row["result"] in ("positive", "negative", "neutral") else None,
                "label":      row["result"] if row["result"] not in ("positive", "negative", "neutral", "") else None,
            }
            results_db.append(entry)
    logging.info(f"CSV cargado: {len(results_db)} registros previos restaurados")

def connect_rabbitmq():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials, heartbeat=600)
    while True:
        try:
            connection = pika.BlockingConnection(params)
            logging.info("Task Logger conectado a RabbitMQ")
            return connection
        except Exception as e:
            logging.warning(f"Esperando RabbitMQ... ({e})")
            time.sleep(3)

def on_result_received(ch, method, properties, body):
    try:
        entry = json.loads(body)
        if not entry.get("timestamp"):
            entry["timestamp"] = datetime.now().isoformat()
        results_db.append(entry)
        append_to_csv(entry)
        logging.info(f"Resultado recibido via RabbitMQ: {entry['task_id'][:8]}... agente={entry.get('agent_id', '?')}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logging.error(f"Error procesando mensaje: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag)

def consume_results():
    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='task_results', durable=True)
    channel.basic_qos(prefetch_count=10)
    channel.basic_consume(queue='task_results', on_message_callback=on_result_received)
    logging.info("Task Logger escuchando en queue 'task_results'...")
    try:
        channel.start_consuming()
    finally:
        connection.close()

@app.on_event("startup")
def startup_event():
    init_csv()
    load_csv()
    thread = threading.Thread(target=consume_results, daemon=True)
    thread.start()

@app.get("/", tags=["Info"])
def root():
    return {
        "service": "Task Logger",
        "status":  "running",
        "docs":    "/docs",
        "total_results": len(results_db)
    }

@app.post("/results", tags=["Resultados"])
def add_result(result: TaskResult):
    entry = result.model_dump()
    if not entry.get("timestamp"):
        entry["timestamp"] = datetime.now().isoformat()

    results_db.append(entry)
    append_to_csv(entry)
    
    logging.info(f"Resultado recibido: {entry['task_id'][:8]}... agente={entry.get('agent_id', '?')}")
    return {"status": "ok", "total": len(results_db)}

@app.get("/results", tags=["Resultados"])
def get_all_results(limit: int = 100, offset: int = 0):
    paginated = results_db[offset: offset + limit]
    return {
        "total":   len(results_db),
        "limit":   limit,
        "offset":  offset,
        "results": paginated
    }

@app.get("/results/{task_id}", tags=["Resultados"])
def get_result_by_id(task_id: str):
    matches = [r for r in results_db if r["task_id"] == task_id]
    if not matches:
        raise HTTPException(status_code=404, detail=f"task_id '{task_id}' no encontrado")
    return matches[0]

@app.get("/stats", tags=["Estadísticas"])
def get_stats():
    if not results_db:
        return {"message": "Sin resultados todavía", "total": 0}

    text_results  = [r for r in results_db if r.get("sentiment") is not None]
    image_results = [r for r in results_db if r.get("label") is not None]
    agents = list(set(r.get("agent_id", "unknown") for r in results_db))
    sentiment_dist = dict(Counter(r["sentiment"] for r in text_results))
    label_dist = dict(Counter(r["label"] for r in image_results))

    avg_confidence = (
        round(sum(r["confidence"] for r in results_db if r.get("confidence") is not None) /
              len([r for r in results_db if r.get("confidence") is not None]), 3)
        if results_db else 0
    )

    return {
        "total_processed": len(results_db),
        "text_tasks": len(text_results),
        "image_tasks": len(image_results),
        "active_agents": agents,
        "num_agents": len(agents),
        "avg_confidence": avg_confidence,
        "sentiment_distribution": sentiment_dist,
        "label_distribution": label_dist,
    }

@app.delete("/results", tags=["Admin"])
def clear_results():
    count = len(results_db)
    results_db.clear()
    init_csv()
    return {"status": "cleared", "deleted": count}