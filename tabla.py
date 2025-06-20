import os
import logging
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está definido como variable de entorno")

def obtener_conexion():
    return psycopg2.connect(DATABASE_URL)

def crear_tabla_aperturas():
    query = """
    CREATE TABLE IF NOT EXISTS aperturas (
        id SERIAL PRIMARY KEY,
        remitente TEXT NOT NULL,
        destinatario TEXT NOT NULL,
        enviado TIMESTAMP NOT NULL,
        abierto TIMESTAMP NOT NULL,
        demora_segundos INTEGER NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        registrado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
        logging.info("Tabla 'aperturas' creada o ya existente.")
    except Exception:
        logging.exception("Error al crear la tabla 'aperturas'")

def crear_indices():
    queries = [
        "CREATE INDEX IF NOT EXISTS idx_destinatario ON aperturas(destinatario);",
        "CREATE INDEX IF NOT EXISTS idx_enviado ON aperturas(enviado);",
        "CREATE INDEX IF NOT EXISTS idx_abierto ON aperturas(abierto);"
    ]
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                for query in queries:
                    cur.execute(query)
        logging.info("Índices creados correctamente.")
    except Exception:
        logging.exception("Error al crear índices en la tabla 'aperturas'")
