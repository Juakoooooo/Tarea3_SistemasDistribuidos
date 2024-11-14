from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StringType, IntegerType
from cassandra.cluster import Cluster
import requests
import json

# Función para crear el keyspace y la tabla en Cassandra
def create_keyspace_and_table():
    cluster = Cluster(['localhost'], port=9042)
    session = cluster.connect()
    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS waze_keyspace
        WITH REPLICATION = { 'class': 'SimpleStrategy', 'replication_factor': 1 }
    """)
    session.execute("""
        CREATE TABLE IF NOT EXISTS waze_keyspace.alerts (
            country TEXT,
            city TEXT,
            type TEXT,
            street TEXT,
            confidence INT,
            reliability INT,
            PRIMARY KEY (country, city, type)
        )
    """)
    cluster.shutdown()

# Llamar a la función para crear el keyspace y la tabla
create_keyspace_and_table()

# Configuración de Spark
spark = SparkSession \
    .builder \
    .appName("WazeAlertsConsumer") \
    .config("spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0,"
            "com.datastax.spark:spark-cassandra-connector_2.12:3.2.0,"
            "org.elasticsearch:elasticsearch-spark-30_2.12:8.1.0") \
    .config("spark.sql.streaming.checkpointLocation", "/tmp/checkpoints") \
    .config("spark.cassandra.connection.host", "localhost") \
    .config("spark.cassandra.connection.port", "9042") \
    .getOrCreate()

# Configuración para conectarse a Kafka
kafka_brokers = "localhost:9092"
topic_name = "waze-alerts"

# Esquema de los datos de alerta
alert_schema = StructType() \
    .add("country", StringType()) \
    .add("city", StringType()) \
    .add("type", StringType()) \
    .add("street", StringType()) \
    .add("confidence", IntegerType()) \
    .add("reliability", IntegerType())

# Crear el índice en Elasticsearch
def create_elasticsearch_index():
    url = "http://localhost:9200/waze"
    headers = {"Content-Type": "application/json"}
    data = {
        "mappings": {
            "properties": {
                "country": {"type": "keyword"},
                "city": {"type": "keyword"},
                "type": {"type": "keyword"},
                "street": {"type": "text"},
                "confidence": {"type": "integer"},
                "reliability": {"type": "integer"}
            }
        }
    }
    try:
        response = requests.put(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            print("Índice creado en Elasticsearch.")
        elif response.status_code == 400 and "resource_already_exists_exception" in response.text:
            print("El índice ya existe en Elasticsearch.")
        else:
            print(f"Error al crear el índice en Elasticsearch: {response.text}")
    except requests.ConnectionError:
        print("No se pudo conectar a Elasticsearch. Verifica que esté en ejecución.")

# Llamar a la función de creación de índice
create_elasticsearch_index()

# Leer los datos de Kafka
kafka_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", kafka_brokers) \
    .option("subscribe", topic_name) \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .load()

# Convertir JSON a columnas y aplicar el filtro para evitar valores NULL en todas las columnas
alert_df = kafka_df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), alert_schema).alias("data")) \
    .select("data.*") \
    .filter(col("country").isNotNull() & 
            col("city").isNotNull() & 
            col("type").isNotNull() & 
            col("street").isNotNull() & 
            col("confidence").isNotNull() & 
            col("reliability").isNotNull())

# Configuración para escribir en Cassandra
def write_to_cassandra(df, epoch_id):
    df.write \
        .format("org.apache.spark.sql.cassandra") \
        .mode("append") \
        .options(table="alerts", keyspace="waze_keyspace") \
        .save()

# Enviar los datos a Cassandra
alert_df.writeStream \
    .foreachBatch(write_to_cassandra) \
    .outputMode("append") \
    .start()

# Configuración para escribir en Elasticsearch
es_options = {
    "es.nodes": "localhost",
    "es.port": "9200",
    "es.resource": "waze/_doc",
    "es.nodes.wan.only": "true"
}

# Función para escribir en Elasticsearch con impresión de datos en consola
def write_to_elasticsearch(df, epoch_id):
    # Mostrar los datos en consola para depuración
    print("Datos a enviar a Elasticsearch:")
    df.show()  # Esto imprimirá los datos en la consola

    # Intentar enviar los datos a Elasticsearch
    df.write \
        .format("org.elasticsearch.spark.sql") \
        .mode("append") \
        .options(**es_options) \
        .save()

# Enviar los datos a Elasticsearch
alert_df.writeStream \
    .foreachBatch(write_to_elasticsearch) \
    .outputMode("append") \
    .start()

# Mostrar los datos en consola (opcional para ver el flujo en tiempo real)
query_console = alert_df \
    .writeStream \
    .outputMode("append") \
    .format("console") \
    .start()

query_console.awaitTermination()