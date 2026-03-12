# Práctica 1 — Infraestructura de Procesamiento de Tareas con Agentes de IA

**Infraestructuras de Big Data · UPM**

## Arquitectura

Sistema distribuido basado en **Event-Driven Architecture (EDA)** con los siguientes componentes:

```
Task Producer(s) → RabbitMQ → Text Agent(s)  → CSV + Task Logger
                           → Image Agent(s) → CSV + Task Logger
```

| Componente     | Tecnología       | Puerto | Descripción                                 |
|----------------|------------------|--------|---------------------------------------------|
| RabbitMQ       | rabbitmq:3-mgmt  | 5672 / 15672 | Broker de mensajes, 2 queues          |
| Task Producer  | Python + pika    | —      | Genera 1 tarea/seg, escalable               |
| Text Agent     | Python + pika    | —      | Análisis de sentimiento, escalable          |
| Image Agent    | Python + pika    | —      | Clasificación de imágenes (bonus)           |
| Task Logger    | FastAPI          | 8000   | API HTTP central de resultados              |

**Red:** bridge `bigdata_net` — aislada para evitar colisiones con otras infraestructuras.  
**Persistencia:** Docker Volumes para CSVs + `durable=True` + `delivery_mode=2` en mensajes.

## Despliegue

### Requisitos

- Docker >= 24.0
- Docker Compose >= 2.0

### Arranque básico

```bash
# Clonar el repositorio
git clone <URL_REPO>
cd practica1

# Levantar toda la infraestructura
docker compose up -d --build

# Ver logs en tiempo real
docker compose logs -f
```

### Verificar que todo funciona

```bash
# Estado de los contenedores
docker compose ps

# Logs del producer
docker compose logs -f task-producer

# Logs de los agentes
docker compose logs -f text-agent
docker compose logs -f image-agent
```

## Ejecutar los agentes

### Escalar agentes (escalado horizontal)

```bash
# 4 agentes de texto en paralelo (recomendado para estabilidad)
docker compose up -d --scale text-agent=4

# 2 producers + 8 agentes
docker compose up -d --scale task-producer=2 --scale text-agent=8
```

### Cálculo de instancias necesarias

- **Input rate:** 1 tarea/segundo por producer
- **Capacidad por agente:** 0.25 tareas/segundo (tarda 3-5s, media 4s)
- **Fórmula:** `N_agentes = ceil(producers × 1.0 / 0.25) = producers × 4`
- **Recomendación:** `--scale text-agent=4` con 1 producer

## Probar el funcionamiento

### API HTTP del Task Logger

```bash
# Ver todos los resultados
curl http://localhost:8000/results | python -m json.tool

# Estadísticas globales del sistema
curl http://localhost:8000/stats | python -m json.tool

# Buscar resultado por ID
curl http://localhost:8000/results/<task_id>

# Swagger UI (documentación interactiva)
# Abrir en navegador: http://localhost:8000/docs
```

### RabbitMQ Management UI

```
URL:      http://localhost:15672
Usuario:  admin
Password: admin
```

Desde aquí puedes ver:
- Mensajes en cada queue en tiempo real
- Tasa de publicación y consumo
- Número de consumers conectados

### Verificar CSVs de resultados

```bash
# Ver resultados del text agent
docker compose exec text-agent cat /data/text_agent_results.csv

# Ver resultados del image agent
docker compose exec image-agent cat /data/image_agent_results.csv
```

## Detener el sistema

```bash
# Detener sin borrar volúmenes (datos persistidos)
docker compose down

# Detener Y borrar datos
docker compose down -v
```

## Estructura del repositorio

```
practica1/
├── docker-compose.yml        # Orquestación de todos los servicios
├── producer/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── producer.py           # Genera tareas → RabbitMQ
├── text_agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── text_agent.py         # Análisis de sentimiento
├── image_agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── image_agent.py        # Clasificación de imágenes (bonus)
└── task_logger/
    ├── Dockerfile
    ├── requirements.txt
    └── main.py               # FastAPI — API HTTP central
```

## Decisiones de diseño

- **2 queues separadas** (`text_tasks`, `image_tasks`): routing limpio y escalado independiente por tipo
- **`prefetch_count=1`**: fair dispatch entre múltiples instancias del mismo agente
- **ACK después de guardar**: garantía de no pérdida si el agente muere durante procesamiento
- **`delivery_mode=2` + `durable=True`**: mensajes y queues sobreviven restart del broker
- **Red bridge personalizada**: aísla el tráfico y evita colisiones de puertos con otras infraestructuras
