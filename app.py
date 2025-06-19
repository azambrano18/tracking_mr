import psycopg2
import logging
import os
from flask import Flask, request, send_from_directory
from datetime import datetime
from tabla import crear_tabla_aperturas

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)

PIXEL_PATH = "static"
PIXEL_NAME = "pixel.png"

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está definido como variable de entorno")

def registrar_apertura(remitente, destinatario, enviado, abierto, demora, ip, ua):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO aperturas (remitente, destinatario, enviado, abierto, demora_segundos, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (remitente, destinatario, enviado, abierto, demora, ip, ua))
        conn.commit()
        cur.close()
        conn.close()
        logging.info(f"Apertura registrada: {remitente} -> {destinatario} ({demora} seg.)")
    except Exception:
        logging.exception("Error al registrar apertura")

@app.route("/pixel")
def pixel():
    remitente = request.args.get("from")
    destinatario = request.args.get("to")
    enviado_str = request.args.get("sent")

    if not remitente or not destinatario or not enviado_str:
        logging.warning("Parámetros faltantes.")
        return send_from_directory(PIXEL_PATH, PIXEL_NAME, mimetype="image/png")

    try:
        enviado = datetime.fromisoformat(enviado_str)
    except ValueError:
        enviado = datetime.now()

    abierto = datetime.now()
    demora = int((abierto - enviado).total_seconds())
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0").split(",")[0].strip()
    ua = request.headers.get("User-Agent", "Desconocido")

    registrar_apertura(remitente, destinatario, enviado, abierto, demora, ip, ua)

    return send_from_directory(PIXEL_PATH, PIXEL_NAME, mimetype="image/png")

@app.route("/ver-aperturas")
def ver_aperturas():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT remitente, destinatario, enviado, abierto, demora_segundos
            FROM aperturas ORDER BY id DESC LIMIT 20
        """)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        html = "<h2>Últimas aperturas</h2><ul>"
        for r, d, e, a, s in filas:
            html += f"<li><b>{r}</b> → {d} | Enviado: {e} | Abierto: {a} | Demora: {s} seg</li>"
        html += "</ul>"
        return html
    except Exception as e:
        return f"<p>Error al consultar la tabla: {str(e)}</p>"

if __name__ == "__main__":
    crear_tabla_aperturas()
    port = int(os.environ.get("PORT", 5000))
    print(">>> Flask app iniciado")
    app.run(host="0.0.0.0", port=port)