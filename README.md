# Práctica 1 — Infraestructura de Procesamiento de Tareas con Agentes de IA

## Descripción

En esta práctica implementamos una infraestructura distribuida para procesar tareas usando agentes de IA simulados.

El sistema genera tareas automáticamente y las envía a una cola de mensajes. Los agentes consumen esas tareas, las procesan y guardan los resultados.

La arquitectura que usamos es **orientada a eventos**, lo que permite que el sistema funcione de forma **asíncrona** y que los agentes puedan procesar tareas en paralelo.

---

# Arquitectura del sistema

El sistema está compuesto por los siguientes servicios:

- **RabbitMQ** → broker de mensajes  
- **Task Producer** → genera tareas continuamente  
- **Text Agent** → analiza texto (simulación de análisis de sentimiento)  
- **Image Agent** → clasifica imágenes (simulación)  
- **Task Logger** → API central que recibe resultados de los agentes  

Flujo del sistema:

```
Producer → RabbitMQ → Agents → CSV + Logger
```

1. El **producer** genera tareas.  
2. Las tareas se envían a RabbitMQ.  
3. Los agentes consumen las tareas desde la cola.  
4. Cada agente procesa la tarea.  
5. El resultado se guarda en CSV y se envía al logger.  

---

# Justificación de las decisiones

## Arquitectura orientada a eventos

Elegimos una **Event-Driven Architecture** porque el sistema necesita procesar tareas de forma **asíncrona**, como vimos en clase.

El productor genera eventos (tareas) y los agentes reaccionan a esos eventos cuando están disponibles. Esto evita que los servicios dependan directamente unos de otros y permite que el sistema escale fácilmente.

---

## Red Docker

Para la comunicación entre los distintos servicios utilizamos una red Docker llamada `bigdata_net`.

La práctica pide implementar una **infraestructura distribuida basada en contenedores**, reducir posibles **conflictos con otras infraestructuras** y mantener una **comunicación controlada entre servicios**. Esto implica que los contenedores deben poder comunicarse entre sí, pero sin interferir con otros servicios que puedan estar ejecutándose en el host.

Por esta razón utilizamos una red de tipo **bridge**. Este tipo de red permite que los contenedores se comuniquen dentro del mismo host de forma aislada, manteniendo separada la infraestructura del resto del sistema.

Además, usar una red Docker permite que los servicios se descubran entre sí utilizando el nombre definido en Docker Compose (por ejemplo `rabbitmq`), sin necesidad de configurar direcciones IP manualmente.

---

## Uso de RabbitMQ

RabbitMQ se usa como **message broker** para gestionar las tareas.

Las tareas se envían a dos colas:

- `text_tasks`
- `image_tasks`

Estas colas se declaran como **durable=True**, lo que permite que sobrevivan reinicios del broker.

Además, los mensajes se publican como **persistentes** usando:

```python
delivery_mode = 2
```

Esto ayuda a evitar la pérdida de tareas.

---

## Procesamiento asíncrono

Los agentes consumen tareas desde RabbitMQ usando `basic_consume`.

Cada agente procesa las tareas con un tiempo simulado entre **3 y 5 segundos**, como se pide en las instrucciones de la práctica.

```python
time.sleep(random.uniform(3,5))
```

Esto permite probar cómo el sistema maneja colas de tareas cuando el procesamiento tarda más que la generación.

---

## Confirmación de tareas (ACK)

Los agentes solo confirman la tarea después de procesarla correctamente.

Orden de ejecución:

```
guardar resultado → notificar logger → ACK
```

Si el agente falla antes del ACK, RabbitMQ vuelve a enviar la tarea a otro agente.

Esto ayuda a cumplir el requisito de **no perder tareas**.

---

## Persistencia de resultados

Cada agente guarda sus resultados en archivos CSV dentro de un volumen Docker.

Ejemplos:

```
/data/text_agent_results.csv
/data/image_agent_results.csv
```

Esto permite que los resultados **no se pierdan si el contenedor se reinicia**.

Además cada agente incluye su `agent_id` (hostname del contenedor) para poder diferenciar qué instancia procesó cada tarea.

---

## Escalabilidad

La arquitectura permite ejecutar múltiples instancias de agentes.

Ejemplo:

```
docker compose up --scale text-agent=3
```

Esto permite que varios agentes procesen tareas al mismo tiempo, aumentando la capacidad del sistema.

---

# Componentes del sistema

## Producer

Genera tareas automáticamente.

Cada tarea tiene el formato:

```json
{
 "task_id": "...",
 "type": "text_analysis | image_classification",
 "content": "..."
}
```

Las tareas se generan a una frecuencia configurable (`TASK_RATE`).

---

## Text Agent

Procesa tareas de análisis de texto.

Simula un análisis de sentimiento usando reglas simples y genera:

```
task_id
sentiment
confidence
timestamp
agent_id
```

---

## Image Agent

Procesa tareas de clasificación de imágenes.

El agente genera una etiqueta aleatoria y un valor de confianza.

```
task_id
label
confidence
timestamp
agent_id
```

---

## Task Logger

Es una API construida con **FastAPI** que recibe los resultados de los agentes.

Los agentes envían los resultados usando:

```
POST /results
```

El logger mantiene los resultados en memoria y permite consultar estadísticas del sistema.

---

# Cómo ejecutar el sistema

### 1. Clonar el repositorio

```
git clone <repo>
```

### 2. Ir al directorio del proyecto

```
cd Grupo5_IBD_P1
```

### 3. Ejecutar la infraestructura

```
docker compose up --build
```

Esto iniciará:

- RabbitMQ  
- Task Producer  
- Text Agent  
- Image Agent  
- Task Logger  

---

# Interfaz de RabbitMQ

RabbitMQ incluye un panel de administración accesible en:

```
http://localhost:15672
```

Usuario:

```
grupo5
```

Password:

```
cbadenes
```

---

# Cómo probar el sistema

Una vez iniciado el sistema:

1. El producer comenzará a generar tareas automáticamente.  
2. Los agentes consumirán las tareas desde RabbitMQ.  
3. Los resultados se guardarán en los archivos CSV.  
4. El logger recibirá los resultados.  

También se pueden consultar estadísticas del sistema en:

```
http://localhost:8000/stats
```

---

# Estructura del repositorio

```
Grupo5_IBD_P1
│
├ docker-compose.yml
├ README.md
│
├ producer
├ text_agent
├ image_agent
└ task_logger
```

---

La infraestructura desarrollada permite procesar tareas de forma distribuida utilizando una arquitectura orientada a eventos.  
El sistema soporta procesamiento asíncrono, persistencia de resultados y escalabilidad horizontal mediante contenedores Docker.