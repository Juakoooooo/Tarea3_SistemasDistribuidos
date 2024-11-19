from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StringType, IntegerType
from cassandra.cluster import Cluster
import requests
import json

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

create_keyspace_and_table()

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

kafka_brokers = "localhost:9092"
topic_name = "waze-alerts"

alert_schema = StructType() \
    .add("country", StringType()) \
    .add("city", StringType()) \
    .add("type", StringType()) \
    .add("street", StringType()) \
    .add("confidence", IntegerType()) \
    .add("reliability", IntegerType())

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

create_elasticsearch_index()

kafka_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", kafka_brokers) \
    .option("subscribe", topic_name) \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .load()

alert_df = kafka_df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), alert_schema).alias("data")) \
    .select("data.*") \
    .filter(col("country").isNotNull() & 
            col("city").isNotNull() & 
            col("type").isNotNull() & 
            col("street").isNotNull() & 
            col("confidence").isNotNull() & 
            col("reliability").isNotNull())

def write_to_cassandra(df, epoch_id):
    df.write \
        .format("org.apache.spark.sql.cassandra") \
        .mode("append") \
        .options(table="alerts", keyspace="waze_keyspace") \
        .save()

alert_df.writeStream \
    .foreachBatch(write_to_cassandra) \
    .outputMode("append") \
    .start()

es_options = {
    "es.nodes": "localhost",
    "es.port": "9200",
    "es.resource": "waze/_doc",
    "es.nodes.wan.only": "true"
}

def write_to_elasticsearch(df, epoch_id):
    print("Datos a enviar a Elasticsearch:")
    df.show() 
    df.write \
        .format("org.elasticsearch.spark.sql") \
        .mode("append") \
        .options(**es_options) \
        .save()

alert_df.writeStream \
    .foreachBatch(write_to_elasticsearch) \
    .outputMode("append") \
    .start()

query_console = alert_df \
    .writeStream \
    .outputMode("append") \
    .format("console") \
    .start()

query_console.awaitTermination()