from PIL import Image
import os

def crear_pixel_transparente(ruta: str = "static/pixel.png") -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    if not os.path.isfile(ruta):
        imagen = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        imagen.save(ruta)
        print(f"Imagen creada en: {ruta}")
    else:
        print(f"Imagen ya existente en: {ruta}")

if __name__ == "__main__":
    crear_pixel_transparente()