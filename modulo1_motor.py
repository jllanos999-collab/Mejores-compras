#!/usr/bin/env python3
"""
MÓDULO 1 v3 - Motor autónomo: keywords + selección diaria de productos + web estilo tienda de diseñador.

Cada ejecución:
  1. Captura keywords reales (Google Trends + autocompletado) y las guarda en SQLite.
     (con tope de tiempo y "cortacircuitos": si Google no responde, NO se cuelga)
  2. Elige 5 productos distintos del catálogo (distintos a los de ayer).
  3. Genera index.html + páginas SEO + sitemap.xml + robots.txt + ideas.csv.

Dependencias: pip install requests
Ejecutar:     python modulo1_motor.py     (salida en ./docs)
"""
import csv
import datetime as dt
import html
import random
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote_plus

import requests

# ============================ CONFIGURACIÓN ============================
CONFIG = {
    "SITE_NAME": "Mejores Compras Hoy",
    "SITE_URL": "https://TU_USUARIO.github.io/TU_REPO",   # cámbialo al publicar
    "LANG": "es",
    "GEO": "ES",
    "AMAZON_DOMAIN": "amazon.es",
    "AMAZON_TAG": "TU_TAG-21",          # <-- TU ID DE AMAZON AFILIADOS (obligatorio)
    "NICHE_SEEDS": ["auriculares inalámbricos", "robot aspirador", "freidora de aire",
                    "monitor gaming", "teclado mecánico"],
    "NICHE_FILTER": ["auricular", "aspirador", "freidora", "monitor", "teclado"],
    "MODIFIERS": ["mejor", "comprar", "barato", "opiniones"],
    "DAILY_PICKS": 5,                   # productos distintos cada día
    "MAX_NEW_PAGES_PER_RUN": 10,
    "OUT_DIR": "docs",                  # carpeta publicada en GitHub Pages
    "DB_FILE": "keywords.db",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrendBot/2.1)"}
COMMERCIAL_WORDS = {"mejor", "mejores", "comprar", "barato", "opiniones",
                    "vs", "precio", "oferta", "calidad"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# ============================ CATÁLOGO ============================
# (icono, categoría, nombre, gancho, [3 beneficios], "ideal si...", búsqueda en Amazon)
CATALOG = [
    ("🎧", "Audio", "Silencio total: auriculares con cancelación de ruido",
     "Apaga el mundo en el metro, la oficina o el avión.",
     ["Cancelación activa de ruido", "Más de 30 h de batería", "Micrófono para llamadas nítidas"],
     "viajas a diario o trabajas en espacios ruidosos", "auriculares cancelación de ruido"),
    ("🔊", "Audio", "Altavoz bluetooth resistente al agua",
     "Música potente en la ducha, la playa o la terraza.",
     ["Resistencia IPX7", "Sonido estéreo con graves", "Hasta 20 h de autonomía"],
     "quieres música sin cables a cualquier sitio", "altavoz bluetooth resistente al agua"),
    ("🤖", "Hogar inteligente", "Robot aspirador con mapeo láser",
     "Tu casa limpia mientras tú haces otra cosa.",
     ["Mapea y evita obstáculos", "Control desde el móvil", "Aspira y friega en una pasada"],
     "no quieres perder tiempo limpiando", "robot aspirador mapeo láser"),
    ("🍟", "Cocina", "Freidora de aire de gran capacidad",
     "Cocina crujiente con una fracción del aceite.",
     ["Hasta 80 % menos de aceite", "Cestas fáciles de limpiar", "Programas automáticos"],
     "cocinas para varios y quieres comer más ligero", "freidora de aire 6 litros"),
    ("🖥️", "Gaming", "Monitor gaming de 144 Hz",
     "Imagen fluida que se nota en cada partida.",
     ["Frecuencia de 144 Hz", "Respuesta de 1 ms", "Panel con colores vivos"],
     "juegas en PC y quieres ventaja real", "monitor gaming 144hz"),
    ("⌨️", "Periféricos", "Teclado mecánico inalámbrico",
     "Escribir se vuelve un placer: tacto preciso y silencioso.",
     ["Conexión bluetooth y 2.4 GHz", "Interruptores intercambiables", "Retroiluminación personalizable"],
     "escribes muchas horas o juegas", "teclado mecánico inalámbrico"),
    ("🖱️", "Periféricos", "Ratón ergonómico vertical",
     "Alivia la muñeca y trabaja más cómodo.",
     ["Postura natural de la mano", "Sensor de alta precisión", "Batería recargable"],
     "pasas el día frente al ordenador", "ratón ergonómico vertical"),
    ("⌚", "Wearables", "Smartwatch con GPS y control de salud",
     "Entrena, duerme y mide tu progreso desde la muñeca.",
     ["GPS integrado", "Seguimiento de sueño y pulso", "Notificaciones del móvil"],
     "quieres controlar tu actividad", "smartwatch gps"),
    ("🔋", "Energía", "Powerbank de 20.000 mAh con carga rápida",
     "Nunca más sin batería fuera de casa.",
     ["Hasta 4 cargas de móvil", "Carga rápida USB-C", "Carga varios dispositivos a la vez"],
     "viajas o pasas muchas horas fuera", "powerbank 20000mah carga rápida"),
    ("⚡", "Energía", "Cargador GaN de 65 W para todo",
     "Un solo cargador pequeño para móvil, tablet y portátil.",
     ["Tamaño compacto", "Varios puertos USB-C", "Carga rápida segura"],
     "quieres aligerar la mochila", "cargador gan 65w"),
    ("💾", "Almacenamiento", "SSD externo portátil de 1 TB",
     "Lleva tus archivos a la velocidad del rayo.",
     ["Lectura ultrarrápida", "Cabe en el bolsillo", "Compatible con PC, Mac y móvil"],
     "te quedas sin espacio o haces copias de seguridad", "ssd externo 1tb portátil"),
    ("📷", "Trabajo remoto", "Webcam 4K con enfoque automático",
     "Que te vean con calidad profesional en cada reunión.",
     ["Resolución 4K", "Enfoque automático", "Micrófonos con reducción de ruido"],
     "haces videollamadas o streaming", "webcam 4k"),
    ("💡", "Hogar inteligente", "Bombillas LED inteligentes WiFi",
     "Cambia el ambiente de casa con la voz o el móvil.",
     ["Millones de colores", "Compatible con Alexa y Google", "Programación horaria"],
     "quieres un hogar más cómodo y eficiente", "bombillas inteligentes wifi"),
    ("🔌", "Hogar inteligente", "Enchufe inteligente con medidor de consumo",
     "Controla y ahorra en la factura de la luz.",
     ["Mide el consumo real", "Apagado programado", "Control desde el móvil"],
     "quieres ahorrar energía en casa", "enchufe inteligente medidor consumo"),
    ("🛡️", "Seguridad", "Cámara de seguridad WiFi para interior",
     "Mira tu casa desde cualquier lugar, en tiempo real.",
     ["Visión nocturna", "Avisos de movimiento en el móvil", "Audio bidireccional"],
     "quieres tranquilidad al salir de casa", "cámara seguridad wifi interior"),
    ("💻", "Trabajo remoto", "Soporte ajustable para portátil",
     "Mejora tu postura y tu productividad en minutos.",
     ["Altura y ángulo regulables", "Aluminio resistente", "Plegable para viajar"],
     "trabajas con el portátil muchas horas", "soporte portátil ajustable aluminio"),
    ("🔗", "Trabajo remoto", "Hub USB-C 8 en 1",
     "Todos los puertos que le faltan a tu portátil.",
     ["HDMI 4K, USB y lector de tarjetas", "Carga pass-through", "Diseño compacto"],
     "tu portátil se quedó sin puertos", "hub usb-c 8 en 1"),
    ("🎮", "Gaming", "Auriculares gaming con micrófono",
     "Escucha los pasos antes que tu rival.",
     ["Sonido envolvente", "Micrófono con cancelación", "Almohadillas cómodas"],
     "juegas online en equipo", "auriculares gaming micrófono"),
    ("📍", "Accesorios", "Localizador de objetos para llaves y mochila",
     "Encuentra lo que pierdes con una pulsación.",
     ["Alcance bluetooth", "Alarma sonora", "Batería de larga duración"],
     "pierdes llaves, cartera o maletas", "localizador de objetos bluetooth"),
    ("📱", "Tablets", "Tablet para estudiar, leer y trabajar",
     "Tu oficina y tu biblioteca en 500 gramos.",
     ["Pantalla nítida", "Batería para todo el día", "Compatible con lápiz digital"],
     "estudias, lees o tomas notas a mano", "tablet 11 pulgadas"),
    ("📽️", "Entretenimiento", "Proyector portátil mini",
     "Cine en casa en cualquier pared.",
     ["Imagen de hasta 100 pulgadas", "Conexión inalámbrica con el móvil", "Altavoz integrado"],
     "quieres ver películas en grande", "mini proyector portátil"),
    ("🌬️", "Salud y hogar", "Purificador de aire con filtro HEPA",
     "Respira mejor en casa, sobre todo si tienes alergias.",
     ["Filtro HEPA H13", "Funcionamiento silencioso", "Sensor de calidad del aire"],
     "tienes alergias o mascotas", "purificador de aire hepa"),
    ("🪥", "Cuidado personal", "Cepillo eléctrico sónico",
     "Una limpieza dental más completa en dos minutos.",
     ["Temporizador de 2 minutos", "Varios modos de cepillado", "Semanas de batería"],
     "quieres mejorar tu higiene bucal", "cepillo eléctrico sónico"),
    ("🎙️", "Creadores", "Micrófono USB para podcast y streaming",
     "Voz clara de estudio sin complicarte con la técnica.",
     ["Conexión plug and play", "Patrón cardioide", "Control de volumen integrado"],
     "grabas podcasts, vídeos o directos", "micrófono usb podcast"),
]


# ============================ CAPTURA DE DATOS ============================
START = time.time()
MAX_SECONDS = 420        # presupuesto total de red: 7 minutos
MAX_CONSEC_FAILS = 6     # cortacircuitos: tras 6 fallos seguidos, se deja de intentar
_consec_fails = 0


def http_get(url, **kw):
    """GET rápido, sin reintentos largos, con tope global y cortacircuitos.
    Devuelve None si algo falla: el sitio se genera igual con el catálogo."""
    global _consec_fails
    if time.time() - START > MAX_SECONDS or _consec_fails >= MAX_CONSEC_FAILS:
        return None
    try:
        r = requests.get(url, headers=HEADERS, timeout=(5, 8), **kw)
        if r.status_code == 200:
            _consec_fails = 0
            return r
    except requests.RequestException:
        pass
    _consec_fails += 1
    return None


def fetch_trends(geo):
    """Temas en tendencia (RSS público de Google Trends)."""
    r = http_get(f"https://trends.google.com/trending/rss?geo={geo}")
    if not r:
        return []
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return []
    return [i.findtext("title", "").strip().lower()
            for i in root.iter("item") if i.findtext("title")]


def autocomplete(query):
    """Sugerencias reales de búsqueda de Google (long-tail)."""
    r = http_get("https://suggestqueries.google.com/complete/search",
                 params={"client": "firefox", "hl": CONFIG["LANG"], "q": query})
    try:
        return [s.lower() for s in r.json()[1]] if r else []
    except (ValueError, IndexError, TypeError):
        return []


def score(kw, is_trend):
    words = kw.split()
    s = 2 * len(COMMERCIAL_WORDS.intersection(words))
    s += 1 if 3 <= len(words) <= 6 else 0
    s += 3 if is_trend else 0
    return s


def collect_keywords():
    found = {}
    trends = fetch_trends(CONFIG["GEO"])
    niche_trends = [t for t in trends if any(f in t for f in CONFIG["NICHE_FILTER"])]
    for seed in CONFIG["NICHE_SEEDS"] + niche_trends:
        for q in [seed] + [f"{m} {seed}" for m in CONFIG["MODIFIERS"]]:
            if _consec_fails >= MAX_CONSEC_FAILS or time.time() - START > MAX_SECONDS:
                print("Google no responde a tiempo: se continúa sin nuevas keywords.")
                return found
            for kw in autocomplete(q):
                found[kw] = max(found.get(kw, 0), score(kw, seed in niche_trends))
            time.sleep(0.3)
    return found


# ============================ BASE DE DATOS ============================
def init_db():
    db = sqlite3.connect(CONFIG["DB_FILE"])
    db.execute("""CREATE TABLE IF NOT EXISTS keywords(
        kw TEXT PRIMARY KEY, score INTEGER, published INTEGER DEFAULT 0, created TEXT)""")
    db.execute("CREATE TABLE IF NOT EXISTS picks(day TEXT, name TEXT)")
    return db


def save_keywords(db, found):
    today = dt.date.today().isoformat()
    for kw, sc in found.items():
        db.execute("INSERT OR IGNORE INTO keywords(kw, score, created) VALUES(?,?,?)",
                   (kw, sc, today))
    db.commit()


def daily_picks(db):
    """5 productos distintos cada día, sin repetir los de ayer. Estable dentro del mismo día."""
    today = dt.date.today().isoformat()
    saved = [r[0] for r in db.execute("SELECT name FROM picks WHERE day=?", (today,))]
    by_name = {p[2]: p for p in CATALOG}
    if len(saved) >= CONFIG["DAILY_PICKS"] and all(n in by_name for n in saved):
        return [by_name[n] for n in saved]
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    recent = {r[0] for r in db.execute("SELECT name FROM picks WHERE day=?", (yesterday,))}
    pool = [p for p in CATALOG if p[2] not in recent] or CATALOG
    picks = random.Random(today).sample(pool, min(CONFIG["DAILY_PICKS"], len(pool)))
    db.execute("DELETE FROM picks WHERE day=?", (today,))
    db.executemany("INSERT INTO picks(day, name) VALUES(?,?)", [(today, p[2]) for p in picks])
    db.commit()
    return picks


# ============================ DISEÑO ============================
# Colores de acento por categoría: cada producto "ilumina" su tarjeta con su propio color.
ACCENTS = {
    "Audio": ("#8b5cff", "#00d4ff"), "Hogar inteligente": ("#00e0a4", "#00b3ff"),
    "Cocina": ("#ff8a3d", "#ff3d81"), "Gaming": ("#ff3d81", "#8b5cff"),
    "Periféricos": ("#4d8dff", "#b26bff"), "Wearables": ("#00e0a4", "#9cff6b"),
    "Energía": ("#ffd23d", "#ff7a3d"), "Almacenamiento": ("#3dd6ff", "#5b7cff"),
    "Trabajo remoto": ("#5b7cff", "#00d4ff"), "Seguridad": ("#ff5e5e", "#ff9a3d"),
    "Accesorios": ("#c06bff", "#ff4ecd"), "Tablets": ("#3dc9ff", "#8b5cff"),
    "Entretenimiento": ("#ff4ecd", "#ffb03d"), "Salud y hogar": ("#3dffb0", "#00c2ff"),
    "Cuidado personal": ("#6bffe0", "#4d8dff"), "Creadores": ("#ff6b6b", "#ffcf3d"),
}

# FOTOS REALES (opcional): pega aquí la URL de una foto tuya o libre de derechos.
# Ejemplo: IMAGES = {"Monitor gaming de 144 Hz": "https://tudominio.com/monitor.jpg"}
# Si un producto no está en la lista, se muestra su escenario animado por defecto.
IMAGES = {}

CSS = """
:root{--bg:#07070d;--txt:#f3f1ff;--mut:#a29fc4;--line:rgba(255,255,255,.12);--glass:rgba(255,255,255,.05);
--a:#8b5cff;--b:#00d4ff}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth}
body{font-family:'Sora',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:var(--txt);line-height:1.6;
min-height:100vh;overflow-x:hidden;padding-bottom:calc(92px + env(safe-area-inset-bottom));
background:radial-gradient(60vmax 40vmax at 90% -10%,rgba(139,92,255,.3),transparent 60%),
radial-gradient(50vmax 40vmax at -10% 45%,rgba(0,212,255,.14),transparent 60%),var(--bg)}
a{color:inherit}
.wrap{width:min(1180px,100% - 32px);margin-inline:auto}
nav{position:sticky;top:0;z-index:20;padding:12px 0;-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);
background:rgba(7,7,13,.6);border-bottom:1px solid var(--line)}
nav .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;text-decoration:none;letter-spacing:-.03em}
.logo b{width:32px;height:32px;border-radius:10px;display:grid;place-items:center;
background:linear-gradient(135deg,#8b5cff,#00d4ff);box-shadow:0 0 24px rgba(139,92,255,.6)}
.live{font-size:.76rem;color:var(--mut)}
.hero{position:relative;isolation:isolate;display:grid;gap:20px;align-items:center;padding:clamp(24px,6vw,72px) 0}
.hero::before{content:"";position:absolute;z-index:-1;width:75vmin;height:75vmin;border-radius:50%;
background:var(--a);filter:blur(120px);opacity:.25;right:-12vmin;top:-4vmin;pointer-events:none}
.hero-v{order:-1;width:min(78vw,360px);margin-inline:auto;animation:pop 1.1s cubic-bezier(.2,.8,.2,1) both}
.hero-t>*{animation:rise .9s cubic-bezier(.2,.8,.2,1) both}
.hero-t>*:nth-child(2){animation-delay:.1s}.hero-t>*:nth-child(3){animation-delay:.2s}
.hero-t>*:nth-child(4){animation-delay:.3s}.hero-t>*:nth-child(5){animation-delay:.4s}
@keyframes rise{from{opacity:0;transform:translateY(24px)}}
@keyframes pop{from{opacity:0;transform:scale(.8) translateY(30px)}}
@media(min-width:860px){.hero{grid-template-columns:1.1fr .9fr;gap:48px}.hero-v{order:0;width:100%;max-width:520px}}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 14px;border-radius:99px;border:1px solid var(--line);
background:var(--glass);font-size:.8rem;color:var(--mut)}
.pill::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--a);box-shadow:0 0 12px var(--a);
animation:blink 2s infinite}
@keyframes blink{50%{opacity:.35}}
.hero h1{margin-top:16px;font-size:clamp(2.4rem,10vw,5rem);line-height:1;letter-spacing:-.05em;font-weight:800;text-wrap:balance}
.hero h1 small{display:block;margin-top:12px;font-size:clamp(1rem,4vw,1.5rem);letter-spacing:-.02em;font-weight:600;color:var(--mut)}
.lead{margin-top:14px;color:var(--mut);font-size:clamp(1rem,3.8vw,1.15rem);max-width:46ch}
.hl{list-style:none;display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
.hl li{padding:8px 14px;border-radius:99px;background:var(--glass);border:1px solid var(--line);font-size:.86rem}
.cta{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}
.btn,.ghost{position:relative;overflow:hidden;display:inline-flex;align-items:center;justify-content:center;
min-height:52px;padding:0 26px;border-radius:16px;font-weight:700;font-size:.98rem;text-decoration:none;
transition:transform .3s,box-shadow .3s}
.btn{color:#07070d;background:linear-gradient(135deg,var(--a),var(--b));box-shadow:0 14px 34px -12px var(--a)}
.btn::after{content:"";position:absolute;top:0;left:-120%;width:60%;height:100%;
background:linear-gradient(100deg,transparent,rgba(255,255,255,.55),transparent);transform:skewX(-20deg);transition:left .7s}
.btn:hover{transform:translateY(-2px);box-shadow:0 20px 44px -12px var(--b)}
.btn:hover::after{left:140%}
.btn:active,.ghost:active{transform:scale(.97)}
.ghost{border:1px solid var(--line);background:var(--glass);color:var(--txt)}
.ghost:hover{border-color:var(--a)}
@media(max-width:560px){.cta .btn,.cta .ghost{width:100%}}
.stage{position:relative;aspect-ratio:1/1;display:grid;place-items:center;isolation:isolate}
.glow{position:absolute;inset:10%;border-radius:50%;z-index:-1;filter:blur(30px);opacity:.8;
background:radial-gradient(circle at 50% 40%,var(--a),transparent 68%);animation:breathe 5s ease-in-out infinite}
.ring{position:absolute;border-radius:50%;border:1px solid var(--line)}
.r1{inset:4%;border-top-color:var(--a);border-right-color:var(--a);animation:spin 14s linear infinite}
.r2{inset:18%;border-bottom-color:var(--b);border-left-color:var(--b);animation:spin 20s linear infinite reverse}
.emo{font-size:clamp(4.2rem,20vw,7rem);line-height:1;filter:drop-shadow(0 26px 28px rgba(0,0,0,.55));
animation:float 6s ease-in-out infinite}
.stage.big .emo{font-size:clamp(7rem,36vw,12.5rem)}
.pimg{width:78%;height:78%;object-fit:contain;filter:drop-shadow(0 26px 28px rgba(0,0,0,.55));animation:float 6s ease-in-out infinite}
.shade{position:absolute;bottom:9%;left:32%;right:32%;height:5%;border-radius:50%;background:rgba(0,0,0,.65);
filter:blur(10px);animation:shade 6s ease-in-out infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes float{50%{transform:translateY(-14px) rotate(-2.5deg)}}
@keyframes shade{50%{transform:scaleX(.75);opacity:.55}}
@keyframes breathe{50%{opacity:.5;transform:scale(1.08)}}
.marq{overflow:hidden;border-block:1px solid var(--line);margin:8px 0;padding:14px 0;
-webkit-mask:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent);mask:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)}
.marq div{display:flex;gap:28px;width:max-content;animation:marq 38s linear infinite;color:var(--mut);font-weight:600;
font-size:clamp(1rem,4vw,1.4rem);letter-spacing:-.02em}
.marq b{color:var(--a)}
@keyframes marq{to{transform:translateX(-50%)}}
h2.sec{font-size:clamp(1.5rem,6vw,2.3rem);letter-spacing:-.04em;margin:clamp(40px,8vw,72px) 0 6px;line-height:1.1}
p.sub{color:var(--mut);margin-bottom:22px;max-width:60ch}
.rail{display:flex;gap:14px;overflow-x:auto;scroll-snap-type:x mandatory;margin-inline:-16px;padding:8px 16px 26px;
scrollbar-width:none}
.rail::-webkit-scrollbar{display:none}
.rail .pc{flex:0 0 80%;scroll-snap-align:center}
@media(min-width:760px){.rail{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));overflow:visible;margin:0;padding:8px 0}
.rail .pc{flex:none}}
.pc{position:relative;overflow:hidden;display:flex;flex-direction:column;gap:10px;padding:18px;border-radius:28px;
background:var(--glass);border:1px solid var(--line);-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px);
box-shadow:0 14px 44px -14px rgba(0,0,0,.7),inset 0 1px 0 rgba(255,255,255,.08);
transform:perspective(900px) translateY(var(--ty,0)) rotateX(var(--rx,0deg)) rotateY(var(--ry,0deg))}
.pc.rv{transition:opacity .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms),translate .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms),
transform .25s ease-out,box-shadow .4s,border-color .4s}
.pc::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .35s;
background:radial-gradient(380px circle at var(--mx,50%) var(--my,0%),rgba(255,255,255,.1),transparent 60%)}
.pc:hover{--ty:-6px;border-color:var(--a);box-shadow:0 30px 60px -18px var(--a),inset 0 1px 0 rgba(255,255,255,.14)}
.pc:hover::after{opacity:1}
.pc .stage{width:88%;margin:0 auto}
.tag{align-self:flex-start;font-size:.74rem;padding:4px 12px;border-radius:99px;color:#fff;
background:rgba(255,255,255,.08);border:1px solid var(--line)}
.pc h3{font-size:1.2rem;line-height:1.25;letter-spacing:-.03em}
.hook{color:var(--mut);font-size:.93rem}
.ben{list-style:none;display:grid;gap:7px}
.ben li{display:flex;gap:10px;font-size:.9rem;align-items:flex-start}
.ben li::before{content:"✓";flex:none;width:19px;height:19px;border-radius:50%;display:grid;place-items:center;
font-size:.68rem;color:#07070d;background:linear-gradient(135deg,var(--a),var(--b));margin-top:2px}
.pc .btn{width:100%;margin-top:auto}
.chips{display:flex;flex-wrap:wrap;gap:10px}
.chip{padding:10px 16px;border-radius:99px;background:var(--glass);border:1px solid var(--line);text-decoration:none;
font-size:.9rem;min-height:44px;display:inline-flex;align-items:center;transition:transform .3s,background .3s,border-color .3s}
.chip:hover{transform:translateY(-3px);background:rgba(139,92,255,.2);border-color:var(--a)}
.trust{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr))}
.box{padding:22px;border-radius:24px;background:var(--glass);border:1px solid var(--line);
-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px)}
.box strong{display:block;margin-bottom:6px;letter-spacing:-.02em}
.box span{color:var(--mut);font-size:.92rem}
.box .ben{margin-top:12px}
footer{margin-top:64px;padding:28px 0;border-top:1px solid var(--line);color:var(--mut);font-size:.8rem}
footer p{max-width:70ch;margin-bottom:8px}
.sticky{position:fixed;left:0;right:0;bottom:0;z-index:30;padding:12px 16px calc(12px + env(safe-area-inset-bottom));
background:rgba(10,10,22,.74);-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px);border-top:1px solid var(--line)}
.sticky .wrap{display:flex;gap:12px;align-items:center;justify-content:space-between}
.sticky span{font-size:.82rem;color:var(--mut);line-height:1.3}
.sticky span b{color:var(--txt);display:block;font-size:.92rem}
.sticky .btn{min-height:48px;padding:0 20px;white-space:nowrap}
@media(max-width:560px){.sticky span{display:none}.sticky .btn{width:100%}}
.rv{opacity:0;translate:0 28px;transition:opacity .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms),translate .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms)}
.rv.in{opacity:1;translate:0 0}
a:focus-visible{outline:3px solid var(--b);outline-offset:3px}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}
.rv{opacity:1;translate:0 0}}
"""

JS = """
(function(){
var io=new IntersectionObserver(function(es){es.forEach(function(e){
if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:.1});
document.querySelectorAll('.rv').forEach(function(el){io.observe(el)});
if(matchMedia('(hover:hover) and (pointer:fine)').matches){
document.querySelectorAll('.pc').forEach(function(c){
c.addEventListener('pointermove',function(e){var r=c.getBoundingClientRect(),
x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;
c.style.setProperty('--ry',(x*10)+'deg');c.style.setProperty('--rx',(-y*10)+'deg');
c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')});
c.addEventListener('pointerleave',function(){c.style.setProperty('--rx','0deg');c.style.setProperty('--ry','0deg')})})}
var par=document.querySelectorAll('[data-par]'),tick=false;
function onScroll(){if(tick)return;tick=true;requestAnimationFrame(function(){var y=window.scrollY;
par.forEach(function(el){el.style.transform='translate3d(0,'+(y*parseFloat(el.dataset.par))+'px,0)'});tick=false})}
if(par.length&&!matchMedia('(prefers-reduced-motion:reduce)').matches){addEventListener('scroll',onScroll,{passive:true})}
})();
"""

SHELL = """<!doctype html><html lang="%%LANG%%"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07070d">
<title>%%TITLE%%</title><meta name="description" content="%%DESC%%">
<link rel="canonical" href="%%CANON%%">
<meta property="og:title" content="%%TITLE%%"><meta property="og:description" content="%%DESC%%">
<meta property="og:type" content="website"><meta property="og:url" content="%%CANON%%">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>%%CSS%%</style>
<noscript><style>.rv{opacity:1;translate:0 0}</style></noscript></head>
<body>
<nav><div class="wrap"><a class="logo" href="index.html"><b>⚡</b>%%SITE%%</a>
<span class="live">Actualizado %%DATE%%</span></div></nav>
%%BODY%%
<footer><div class="wrap">
<p>Como Afiliado de Amazon, obtengo ingresos por las compras adscritas que cumplen los requisitos aplicables.
Los precios y la disponibilidad se muestran en Amazon en el momento de la compra.</p>
<p>&copy; %%YEAR%% %%SITE%%. Selección automática basada en búsquedas reales.</p></div></footer>
<div class="sticky"><div class="wrap"><span><b>%%STICKY_T%%</b>Precio actualizado en Amazon</span>
<a class="btn" href="%%STICKY_URL%%" rel="sponsored nofollow noopener" target="_blank">Ver ofertas</a></div></div>
<script>%%JS%%</script></body></html>"""


# ============================ RENDER ============================
esc = html.escape


def slugify(text):
    text = text.lower()
    for a, b in zip("áéíóúñü", "aeiounu"):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def affiliate_url(query):
    """Enlace de afiliado: usa AMAZON_TAG del bloque CONFIG."""
    return (f"https://www.{CONFIG['AMAZON_DOMAIN']}/s?k={quote_plus(query)}"
            f"&tag={CONFIG['AMAZON_TAG']}")


def date_es(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def accent(p):
    a, b = ACCENTS.get(p[1], ("#8b5cff", "#00d4ff"))
    return f"--a:{a};--b:{b}"


def stage(p, big=False):
    """Escenario del producto: foto (si hay en IMAGES) o icono flotante con anillos y luz."""
    img = IMAGES.get(p[2])
    visual = (f'<img class="pimg" src="{esc(img)}" alt="{esc(p[2])}" loading="lazy">' if img
              else f'<span class="emo" role="img" aria-label="{esc(p[2])}">{p[0]}</span>')
    return (f'<div class="stage{" big" if big else ""}"><i class="ring r1"></i><i class="ring r2"></i>'
            f'<i class="glow"></i>{visual}<i class="shade"></i></div>')


def page(title, desc, canon, body, sticky_title, sticky_url):
    today = dt.date.today()
    out = SHELL
    for k, v in {
        "%%LANG%%": CONFIG["LANG"], "%%TITLE%%": esc(title), "%%DESC%%": esc(desc),
        "%%CANON%%": canon, "%%CSS%%": CSS, "%%JS%%": JS, "%%SITE%%": esc(CONFIG["SITE_NAME"]),
        "%%DATE%%": date_es(today), "%%YEAR%%": str(today.year), "%%STICKY_T%%": esc(sticky_title),
        "%%STICKY_URL%%": sticky_url, "%%BODY%%": body,
    }.items():
        out = out.replace(k, v)
    return out


def product_card(p, idx=0):
    icon, cat, name, hook, benefits, ideal, query = p
    items = "".join(f"<li>{esc(b)}</li>" for b in benefits)
    return (f'<article class="pc rv" style="--d:{idx * 90}ms;{accent(p)}">{stage(p)}'
            f'<span class="tag">{esc(cat)}</span><h3>{esc(name)}</h3><p class="hook">{esc(hook)}</p>'
            f'<ul class="ben">{items}</ul>'
            f'<a class="btn" href="{affiliate_url(query)}" rel="sponsored nofollow noopener" '
            f'target="_blank">Ver precio actual en Amazon</a></article>')


def marquee():
    cats = sorted({p[1] for p in CATALOG})
    item = "".join(f"<span>{esc(c)}</span><b>✦</b>" for c in cats)
    return f'<div class="marq" aria-hidden="true"><div>{item}{item}</div></div>'


def split_name(name):
    if ": " in name:
        a, b = name.split(": ", 1)
        return a, b[:1].upper() + b[1:]
    return name, ""


TRUST = """<div class="trust">
<div class="box rv"><strong>Nueva selección cada día</strong><span>Los productos cambian a diario según lo que la gente busca.</span></div>
<div class="box rv" style="--d:90ms"><strong>Sin ruido</strong><span>Cinco opciones a la vez, con lo esencial para decidir.</span></div>
<div class="box rv" style="--d:180ms"><strong>Compra en Amazon</strong><span>Precio, stock y devoluciones los gestiona Amazon.</span></div></div>"""


def render_index(db, picks, out):
    hero_p, rest = picks[0], picks[1:]
    title, subt = split_name(hero_p[2])
    small = f"<small>{esc(subt)}</small>" if subt else ""
    hl = "".join(f"<li>{esc(b)}</li>" for b in hero_p[4])
    pub = db.execute("SELECT kw FROM keywords WHERE published=1 "
                     "ORDER BY created DESC, score DESC LIMIT 16").fetchall()
    chips = "".join(f'<a class="chip" href="{slugify(k)}.html">{esc(k)}</a>' for (k,) in pub)
    trends = (f'<h2 class="sec">Lo que se busca ahora</h2>'
              f'<p class="sub">Guías rápidas sobre las búsquedas de compra más activas.</p>'
              f'<div class="chips">{chips}</div>') if chips else ""
    cards = "".join(product_card(p, i) for i, p in enumerate(rest))
    body = (f'<main class="wrap"><section class="hero" style="{accent(hero_p)}">'
            f'<div class="hero-t"><span class="pill">Destacado de hoy</span>'
            f'<h1>{esc(title)}{small}</h1><p class="lead">{esc(hero_p[3])}</p>'
            f'<ul class="hl">{hl}</ul>'
            f'<div class="cta"><a class="btn" href="{affiliate_url(hero_p[6])}" '
            f'rel="sponsored nofollow noopener" target="_blank">Ver precio actual en Amazon</a>'
            f'<a class="ghost" href="#mas">Más selecciones</a></div></div>'
            f'<div class="hero-v" data-par=".05">{stage(hero_p, big=True)}</div></section>'
            f'{marquee()}'
            f'<h2 class="sec" id="mas">Más selecciones de hoy</h2>'
            f'<p class="sub">{date_es(dt.date.today())}. Productos nuevos cada día, sin repetir los de ayer.</p>'
            f'<div class="rail">{cards}</div>{trends}'
            f'<h2 class="sec">Cómo funciona</h2>{TRUST}</main>')
    (out / "index.html").write_text(page(
        f"{CONFIG['SITE_NAME']}: tecnología recomendada hoy",
        "Selección diaria de productos tecnológicos con las mejores opciones para comprar hoy.",
        f"{CONFIG['SITE_URL']}/index.html", body,
        title[:34], affiliate_url(hero_p[6])), encoding="utf-8")


def render_keyword_page(kw, picks_pool, out):
    related = [r for r in autocomplete(kw) if r != kw][:8]
    chips = "".join(f'<a class="chip" rel="sponsored nofollow noopener" target="_blank" '
                    f'href="{affiliate_url(r)}">{esc(r)}</a>' for r in related)
    rel_html = (f'<h2 class="sec">Búsquedas relacionadas</h2><div class="chips">{chips}</div>'
                if chips else "")
    sample = random.Random(kw).sample(picks_pool, 4)
    cards = "".join(product_card(p, i) for i, p in enumerate(sample[1:]))
    year = dt.date.today().year
    body = (f'<main class="wrap"><section class="hero" style="{accent(sample[0])}">'
            f'<div class="hero-t"><span class="pill">Guía rápida</span>'
            f'<h1>{esc(kw.capitalize())}</h1>'
            f'<p class="lead">Qué mirar antes de comprar y dónde comparar precios actualizados.</p>'
            f'<span></span><div class="cta"><a class="btn" href="{affiliate_url(kw)}" '
            f'rel="sponsored nofollow noopener" target="_blank">Ver ofertas de {esc(kw)}</a></div></div>'
            f'<div class="hero-v" data-par=".05">{stage(sample[0], big=True)}</div></section>'
            f'<div class="box rv"><strong>Qué revisar antes de comprar</strong><ul class="ben">'
            f'<li>Valoraciones reales y número de opiniones.</li>'
            f'<li>Relación calidad-precio frente a alternativas.</li>'
            f'<li>Garantía, devoluciones y plazo de entrega.</li>'
            f'<li>Historial de precio: compara antes de decidir.</li></ul></div>'
            f'{rel_html}<h2 class="sec">También te puede interesar</h2>'
            f'<div class="rail">{cards}</div></main>')
    (out / f"{slugify(kw)}.html").write_text(page(
        f"{kw.capitalize()}: guía y ofertas ({year})",
        f"Guía rápida para elegir {kw}: qué mirar y dónde comprar al mejor precio.",
        f"{CONFIG['SITE_URL']}/{slugify(kw)}.html", body,
        kw.capitalize()[:34], affiliate_url(kw)), encoding="utf-8")


def build_site(db, picks):
    out = Path(CONFIG["OUT_DIR"])
    out.mkdir(exist_ok=True)
    pending = db.execute("SELECT kw FROM keywords WHERE published=0 ORDER BY score DESC LIMIT ?",
                         (CONFIG["MAX_NEW_PAGES_PER_RUN"],)).fetchall()
    for (kw,) in pending:
        render_keyword_page(kw, CATALOG, out)
        db.execute("UPDATE keywords SET published=1 WHERE kw=?", (kw,))
    db.commit()

    render_index(db, picks, out)

    pub = [r[0] for r in db.execute("SELECT kw FROM keywords WHERE published=1")]
    urls = f"<url><loc>{CONFIG['SITE_URL']}/index.html</loc></url>" + "".join(
        f"<url><loc>{CONFIG['SITE_URL']}/{slugify(k)}.html</loc></url>" for k in pub)
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
        encoding="utf-8")
    (out / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {CONFIG['SITE_URL']}/sitemap.xml\n")
    with open(out / "ideas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["keyword", "score"])
        w.writerows(db.execute("SELECT kw, score FROM keywords ORDER BY score DESC"))
    return len(pending)


# ============================ MAIN ============================
def main():
    if "TU_TAG" in CONFIG["AMAZON_TAG"]:
        print("AVISO: configura AMAZON_TAG con tu ID de afiliado o no cobrarás comisiones.")
    db = init_db()
    try:
        found = collect_keywords()
    except Exception as e:  # la captura nunca debe tumbar el sitio
        print("Captura de keywords falló, se continúa:", e)
        found = {}
    print(f"Keywords capturadas: {len(found)}")
    save_keywords(db, found)
    picks = daily_picks(db)
    n = build_site(db, picks)
    print(f"Productos de hoy: {len(picks)} | páginas SEO nuevas: {n} | salida: '{CONFIG['OUT_DIR']}'")


if __name__ == "__main__":
    main()

