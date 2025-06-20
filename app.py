import psycopg2
import logging
import os
from flask import Flask, request, redirect
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está definido como variable de entorno")

@app.route("/click")
def redirigir_click():
    remitente = request.args.get("from")
    destinatario = request.args.get("to")
    enviado_str = request.args.get("sent")
    destino_final = request.args.get("url", "https://tusitio.com")

    try:
        enviado = datetime.fromisoformat(enviado_str)
    except:
        enviado = datetime.utcnow()

    clic = datetime.utcnow()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0").split(",")[0].strip()
    ua = request.headers.get("User-Agent", "Desconocido")

    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO clicks (remitente, destinatario, enviado, clic, ip_address, user_agent, url_destino)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (remitente, destinatario, enviado, clic, ip, ua, destino_final))
        logging.info(f"Clic registrado: {remitente} -> {destinatario}")
    except Exception:
        logging.exception("Error al registrar clic")

    return redirect(destino_final)

@app.route("/")
def index():
    return "<h2>Tracking por clic activo</h2><p>Los eventos de clic se registrarán correctamente si visitas desde los enlaces únicos de email.</p>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(">>> Flask app iniciado")
    app.run(host="0.0.0.0", port=port)