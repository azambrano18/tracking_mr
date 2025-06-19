# crear_pixel.py
from PIL import Image
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def crear_pixel_transparente(ruta: str = "static/pixel.png") -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    if not os.path.isfile(ruta):
        imagen = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        imagen.save(ruta)
        logging.info(f"Imagen creada en: {ruta}")
    else:
        logging.info(f"Imagen ya existe en: {ruta}")

if __name__ == "__main__":
    crear_pixel_transparente()
