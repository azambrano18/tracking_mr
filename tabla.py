import os
import logging
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está definido como variable de entorno")

def crear_tabla_aperturas():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
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
        """)
        conn.commit()
        cur.close()
        conn.close()
        logging.info("Tabla 'aperturas' creada o ya existente.")
    except Exception as e:
        logging.exception("Error al crear la tabla 'aperturas'")