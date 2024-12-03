# 🚦 Proyecto: Sistema Distribuido para el Monitoreo de Tráfico en Tiempo Real

Este proyecto implementa un sistema distribuido que monitorea el tráfico en tiempo real utilizando datos de la plataforma Waze. Combina diversas tecnologías como Apache Kafka, Spark, Cassandra, Elasticsearch y Kibana para procesar, almacenar y visualizar alertas de tráfico de manera eficiente.

## 🛠️ Requisitos del Sistema

- 🐋 Docker y Docker Compose
- 🐍 Python 3.11 (Spark no es compatible con otras versiones de Python)
- 📦 Node.js v16 o superior

## 📦 Instalación de Dependencias

Asegúrate de que todos los requisitos del sistema estén instalados antes de continuar.

### ⚙️ Configuración del entorno

1. Clonamos el repositorio y nos dirigimos a la carpeta raíz del proyecto.

    ```bash
    git clone https://github.com/Juakoooooo/Tarea3_SistemasDistribuidos.git
    cd Tarea3_SistemasDistribuidos
    ```

2. Levantamos los contenedores con Docker Compose.

    ```bash
    sudo docker-compose up -d
    ```

3. Para detener y limpiar los contenedores, recomendamos usar el siguiente comando para evitar errores con los volúmenes de Kafka:

    ```bash
    sudo docker-compose down --volumes --rmi all --remove-orphans
    ```

## 🚀 Ejecución del proyecto

Sigue estos pasos en el orden indicado para ejecutar el proyecto:

### 1. Ejecutar el Scrapper 🧹

El scrapper se encarga de capturar las alertas de tráfico desde Waze y enviarlas al tópico de Kafka.

```bash
cd waze-scraper
node scraper.js
```

### 2. Ejecutar el Consumer de Spark ⚙️

El consumidor de Spark procesa las alertas en tiempo real, calcula la latencia y almacena los datos en Cassandra y Elasticsearch.

```bash
cd spark
python3.11 spark-consumer.py
```

### 3. Verificar los datos en Cassandra 🔍

Accede al shell de Cassandra para verificar los datos almacenados:
```bash
sudo docker exec -it tarea3_sistemasdistribuidos-cassandra-1 cqlsh
```

Dentro del shell de Cassandra, utiliza los siguientes comandos:
```bash
USE waze_keyspace;
SELECT * FROM alerts LIMIT 10;
```

### 4. Consultar los datos en Kibana 📊

Accede a Kibana desde tu navegador en el puerto 5601: http://localhost:5601. (INSTRUCCIONES MÁS DETALLADAS EN EL README DE LA TAREA 2)


#### Comandos útiles para Apache Kafka 🐋

Listar los tópicos disponibles:
```bash
docker exec -it tarea3_sistemasdistribuidos-kafka-1 kafka-topics.sh --list --bootstrap-server localhost:9092
```

Describir el tópico waze-alerts:
```bash
docker exec -it tarea3_sistemasdistribuidos-kafka-1 kafka-topics.sh --describe --bootstrap-server localhost:9092 --topic waze-alerts
```
Leer mensajes del tópico waze-alerts desde el principio:
```bash
docker exec -it tarea3_sistemasdistribuidos-kafka-1 kafka-console-consumer.sh --bootst
```

### ✉️ Verificación de Resultados

#### Cassandra

Puedes consultar los datos almacenados en Cassandra utilizando las instrucciones proporcionadas previamente. Deberías observar las alertas con campos como:

- `country`: País donde se generó la alerta.
- `city`: Ciudad asociada con la alerta.
- `type`: Tipo de incidente (por ejemplo, `ROAD_CLOSED`, `HAZARD`, `ACCIDENT`).
- `latency_ms`: Latencia calculada en milisegundos.
- `generated_at`: Marca de tiempo de generación de la alerta.
- `processed_at`: Marca de tiempo de procesamiento de la alerta.

#### Kibana

1. Accede a Kibana en [http://localhost:5601](http://localhost:5601).
2. Crea un **index pattern** para Elasticsearch con el nombre `waze`.
3. Visualiza los datos en tiempo real mediante gráficos y dashboards interactivos:
   - Gráficos de barras para la cantidad de alertas procesadas por segundo.
   - Dashboards para analizar la latencia y los tipos de incidentes.

#### Latencia

La latencia del sistema se calcula como el tiempo transcurrido desde que una alerta es generada por el scrapper hasta que es procesada por Spark y almacenada en Cassandra o Elasticsearch. Estas métricas se pueden visualizar en Kibana mediante gráficos de barras o líneas que muestran la cantidad de alertas procesadas por segundo.

---

### 📚 Referencias

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/) 🐋
- [Apache Spark Documentation](https://spark.apache.org/documentation.html) ⚡
- [Elasticsearch Documentation](https://www.elastic.co/guide/en/elasticsearch/) 🔍
- [Cassandra Documentation](https://cassandra.apache.org/doc/latest/) 📦
- [Kibana Documentation](https://www.elastic.co/guide/en/kibana/) 📊
