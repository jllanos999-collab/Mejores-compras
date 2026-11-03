import os
from datetime import datetime

# Directorio obligatorio para que GitHub Pages lea la web
OUTPUT_DIR = "docs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generar_pagina_web():
    print("Generando página estática automática...")
    
    # Contenido optimizado para conversión y SEO
    keyword = "mejores ofertas y tecnología"
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mejores Compras y Tendencias {datetime.now().strftime("%Y")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; background: #f4f6f8; color: #333; }}
        h1 {{ color: #1a252f; }}
        .card {{ background: white; padding: 25px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        .btn {{ display: inline-block; background: #ff9900; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px; }}
        .btn:hover {{ background: #e88b00; }}
        footer {{ text-align: center; margin-top: 40px; color: #7f8c8d; }}
    </style>
</head>
<body>
    <h1>🔥 Tendencias de Compra Verificadas</h1>
    <p>Sitio actualizado automáticamente el <strong>{datetime.now().strftime("%d/%m/%Y a las %H:%M")}</strong>. Analizamos los productos más demandados en internet.</p>
    
    <div class="card">
        <h2>Oportunidad Destacada: {keyword}</h2>
        <p>Selección automática basada en intenciones de búsqueda de alta conversión para compradores.</p>
        <!-- En el futuro aquí irá tu enlace de afiliado con tu Tag de Amazon -->
        <a href="https://amazon.es" class="btn" target="_blank">Ver Producto en Amazon</a>
    </div>
    
    <footer>
        <p><small>Sistema autónomo de ingresos pasivos en ejecución continua.</small></p>
    </footer>
</body>
</html>"""
    
    # Guardar dentro de la carpeta docs como index.html
    ruta_archivo = os.path.join(OUTPUT_DIR, "index.html")
    with open(ruta_archivo, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Página principal creada con éxito en {ruta_archivo}")

if __name__ == "__main__":
    generar_pagina_web()
