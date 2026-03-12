from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from collections import Counter
import logging

logging.basicConfig(level=logging.INFO, format='[TASK-LOGGER] %(message)s')

app = FastAPI(
    title="Task Logger — Big Data Práctica 1",
    description="API central de registro de resultados de agentes de IA",
    version="1.0.0"
)

# Almacenamiento en memoria (suficiente para la práctica)
results_db: list[dict] = []

# ── MODELOS ───────────────────────────────────────────────────────

class TaskResult(BaseModel):
    task_id:    str
    timestamp:  Optional[str] = None
    agent_id:   Optional[str] = None
    # Campos texto
    sentiment:  Optional[str] = None
    confidence: Optional[float] = None
    # Campos imagen
    label:      Optional[str] = None

# ── ENDPOINTS ─────────────────────────────────────────────────────

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
    """Los agentes llaman a este endpoint cuando terminan una tarea."""
    entry = result.model_dump()
    if not entry.get("timestamp"):
        entry["timestamp"] = datetime.now().isoformat()

    results_db.append(entry)
    logging.info(f"Resultado recibido: {entry['task_id'][:8]}... agente={entry.get('agent_id', '?')}")
    return {"status": "ok", "total": len(results_db)}

@app.get("/results", tags=["Resultados"])
def get_all_results(limit: int = 100, offset: int = 0):
    """Devuelve todos los resultados procesados por todos los agentes."""
    paginated = results_db[offset: offset + limit]
    return {
        "total":   len(results_db),
        "limit":   limit,
        "offset":  offset,
        "results": paginated
    }

@app.get("/results/{task_id}", tags=["Resultados"])
def get_result_by_id(task_id: str):
    """Busca un resultado por su task_id."""
    matches = [r for r in results_db if r["task_id"] == task_id]
    if not matches:
        raise HTTPException(status_code=404, detail=f"task_id '{task_id}' no encontrado")
    return matches[0]

@app.get("/stats", tags=["Estadísticas"])
def get_stats():
    """
    Estadísticas globales del sistema.
    Este endpoint diferencia tu práctica — muestra comprensión del sistema completo.
    """
    if not results_db:
        return {"message": "Sin resultados todavía", "total": 0}

    # Separar por tipo
    text_results  = [r for r in results_db if r.get("sentiment") is not None]
    image_results = [r for r in results_db if r.get("label") is not None]

    # Agentes activos
    agents = list(set(r.get("agent_id", "unknown") for r in results_db))

    # Distribución de sentimientos
    sentiment_dist = dict(Counter(r["sentiment"] for r in text_results))

    # Distribución de labels
    label_dist = dict(Counter(r["label"] for r in image_results))

    # Confianza promedio
    avg_confidence = (
        round(sum(r["confidence"] for r in results_db if r.get("confidence")) /
              len([r for r in results_db if r.get("confidence")]), 3)
        if results_db else 0
    )

    return {
        "total_processed":    len(results_db),
        "text_tasks":         len(text_results),
        "image_tasks":        len(image_results),
        "active_agents":      agents,
        "num_agents":         len(agents),
        "avg_confidence":     avg_confidence,
        "sentiment_distribution": sentiment_dist,
        "label_distribution":     label_dist,
    }

@app.delete("/results", tags=["Admin"])
def clear_results():
    """Limpia todos los resultados (útil para testing)."""
    count = len(results_db)
    results_db.clear()
    return {"status": "cleared", "deleted": count}
