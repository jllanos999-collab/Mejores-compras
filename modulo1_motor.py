#!/usr/bin/env python3
"""
MÓDULO 1 v2 - Motor autónomo: keywords + selección diaria de productos + web premium.

Cada ejecución:
  1. Captura keywords reales (Google Trends + autocompletado) y las guarda en SQLite.
  2. Elige 5 productos distintos del catálogo (distintos a los de ayer).
  3. Genera index.html + páginas SEO + sitemap.xml + robots.txt + ideas.csv.

Dependencias: pip install requests
Ejecutar:     python modulo1_motor.py     (salida en ./site)
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
    "MODIFIERS": ["mejor", "mejores", "comprar", "barato", "opiniones", "vs", "calidad precio"],
    "DAILY_PICKS": 5,                   # productos distintos cada día
    "MAX_NEW_PAGES_PER_RUN": 10,
    "OUT_DIR": "site",                  # carpeta publicada en GitHub Pages
    "DB_FILE": "keywords.db",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrendBot/2.0)"}
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
def http_get(url, **kw):
    """GET con reintentos; devuelve None si falla (el sistema nunca se cae)."""
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, **kw)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
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
    except (ValueError, IndexError):
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
            for kw in autocomplete(q):
                found[kw] = max(found.get(kw, 0), score(kw, seed in niche_trends))
            time.sleep(0.4)
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


# ============================ DISEÑO (CSS + JS) ============================
CSS = """
:root{--bg:#06060f;--bg2:#0d0d1f;--txt:#eef0ff;--mut:#9ba1c9;--a:#7c5cff;--b:#00d4ff;--c:#ff4ecd;
--glass:rgba(255,255,255,.055);--line:rgba(255,255,255,.13);--r:24px}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth}
body{font-family:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;background:var(--bg);
color:var(--txt);line-height:1.6;min-height:100vh;overflow-x:hidden;
padding-bottom:calc(92px + env(safe-area-inset-bottom))}
a{color:inherit}
.aurora{position:fixed;inset:0;z-index:-1;overflow:hidden;pointer-events:none}
.aurora i{position:absolute;border-radius:50%;filter:blur(90px);opacity:.55;animation:drift 18s ease-in-out infinite alternate}
.aurora i:nth-child(1){width:55vmax;height:55vmax;background:var(--a);top:-20vmax;left:-15vmax}
.aurora i:nth-child(2){width:45vmax;height:45vmax;background:var(--b);bottom:-18vmax;right:-12vmax;animation-delay:-6s;opacity:.4}
.aurora i:nth-child(3){width:30vmax;height:30vmax;background:var(--c);top:40%;left:55%;animation-delay:-12s;opacity:.28}
@keyframes drift{to{transform:translate3d(6vmax,4vmax,0) scale(1.15)}}
.wrap{width:min(1120px,100% - 32px);margin-inline:auto}
nav{position:sticky;top:0;z-index:20;padding:12px 0;backdrop-filter:blur(16px);
background:rgba(6,6,15,.55);border-bottom:1px solid var(--line)}
nav .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;text-decoration:none;letter-spacing:-.02em}
.logo b{width:32px;height:32px;border-radius:10px;display:grid;place-items:center;
background:linear-gradient(135deg,var(--a),var(--b));box-shadow:0 0 24px rgba(124,92,255,.6)}
.live{font-size:.78rem;color:var(--mut);display:flex;align-items:center;gap:8px}
.live::before{content:"";width:8px;height:8px;border-radius:50%;background:#3dffa0;
box-shadow:0 0 0 0 rgba(61,255,160,.7);animation:pulse 2s infinite}
@keyframes pulse{70%{box-shadow:0 0 0 10px rgba(61,255,160,0)}100%{box-shadow:0 0 0 0 rgba(61,255,160,0)}}
.hero{padding:clamp(40px,9vw,96px) 0 clamp(24px,5vw,48px)}
.hero h1{font-size:clamp(2.2rem,8.5vw,4.6rem);line-height:1.04;letter-spacing:-.04em;font-weight:800;max-width:15ch;
background:linear-gradient(120deg,#fff 20%,#b9a8ff 55%,var(--b));-webkit-background-clip:text;background-clip:text;
color:transparent;animation:rise .9s cubic-bezier(.2,.8,.2,1) both}
.hero p{margin-top:18px;max-width:52ch;color:var(--mut);font-size:clamp(1rem,3.6vw,1.2rem);
animation:rise .9s .15s cubic-bezier(.2,.8,.2,1) both}
.hero .btn{margin-top:26px;animation:rise .9s .3s cubic-bezier(.2,.8,.2,1) both}
@keyframes rise{from{opacity:0;transform:translateY(22px)}}
h2.sec{font-size:clamp(1.4rem,5vw,2rem);letter-spacing:-.03em;margin:clamp(36px,7vw,64px) 0 6px}
p.sub{color:var(--mut);margin-bottom:22px;max-width:60ch}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,290px),1fr))}
.card{position:relative;overflow:hidden;background:var(--glass);border:1px solid var(--line);border-radius:var(--r);
padding:22px;-webkit-backdrop-filter:blur(20px) saturate(150%);backdrop-filter:blur(20px) saturate(150%);
box-shadow:0 10px 40px -12px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.08);
transition:transform .4s cubic-bezier(.2,.8,.2,1),box-shadow .4s,border-color .4s;
display:flex;flex-direction:column;gap:12px}
.card::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .35s;
background:radial-gradient(420px circle at var(--mx,50%) var(--my,0%),rgba(124,92,255,.28),transparent 60%)}
.card:hover{transform:translateY(-8px);border-color:rgba(160,140,255,.5);
box-shadow:0 28px 60px -16px rgba(124,92,255,.45),inset 0 1px 0 rgba(255,255,255,.14)}
.card:hover::after{opacity:1}
.card:active{transform:scale(.985)}
.card.feat{grid-column:1/-1;border:1px solid transparent;
background:linear-gradient(var(--bg2),var(--bg2)) padding-box,linear-gradient(135deg,var(--a),var(--b),var(--c)) border-box;
box-shadow:0 20px 70px -20px rgba(124,92,255,.55)}
.ico{width:56px;height:56px;border-radius:18px;display:grid;place-items:center;font-size:1.7rem;
background:linear-gradient(135deg,rgba(124,92,255,.35),rgba(0,212,255,.25));border:1px solid var(--line);
transition:transform .5s cubic-bezier(.2,.8,.2,1)}
.card:hover .ico{transform:rotate(-8deg) scale(1.12)}
.tag{align-self:flex-start;font-size:.76rem;padding:4px 12px;border-radius:99px;color:#cfc6ff;
background:rgba(124,92,255,.18);border:1px solid rgba(124,92,255,.35)}
.tag.hot{color:#ffd3f3;background:rgba(255,78,205,.18);border-color:rgba(255,78,205,.45)}
.card h3{font-size:clamp(1.15rem,4.4vw,1.4rem);line-height:1.25;letter-spacing:-.02em}
.card.feat h3{font-size:clamp(1.4rem,5.6vw,2rem)}
.hook{color:var(--mut)}
.ben{list-style:none;display:grid;gap:8px}
.ben li{display:flex;gap:10px;font-size:.95rem;align-items:flex-start}
.ben li::before{content:"✓";flex:none;width:20px;height:20px;border-radius:50%;display:grid;place-items:center;
font-size:.72rem;color:#06060f;background:linear-gradient(135deg,var(--b),#3dffa0);margin-top:2px}
.ideal{font-size:.88rem;color:var(--mut);border-top:1px solid var(--line);padding-top:12px;margin-top:auto}
.ideal b{color:var(--txt);font-weight:600}
.btn{position:relative;overflow:hidden;display:inline-flex;align-items:center;justify-content:center;gap:8px;
min-height:52px;padding:0 26px;border-radius:16px;font-weight:700;font-size:1rem;text-decoration:none;color:#fff;
background:linear-gradient(135deg,var(--a),#5b7cff 50%,var(--b));
box-shadow:0 12px 30px -10px rgba(124,92,255,.8);transition:transform .3s,box-shadow .3s}
.btn::after{content:"";position:absolute;top:0;left:-120%;width:60%;height:100%;
background:linear-gradient(100deg,transparent,rgba(255,255,255,.45),transparent);transform:skewX(-20deg);transition:left .7s}
.btn:hover{transform:translateY(-2px);box-shadow:0 18px 40px -10px rgba(0,212,255,.7)}
.btn:hover::after{left:140%}
.btn:active{transform:scale(.97)}
.card .btn{width:100%}
.chips{display:flex;flex-wrap:wrap;gap:10px}
.chip{padding:10px 16px;border-radius:99px;background:var(--glass);border:1px solid var(--line);
text-decoration:none;font-size:.92rem;min-height:44px;display:inline-flex;align-items:center;
-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);transition:transform .3s,background .3s,border-color .3s}
.chip:hover{transform:translateY(-3px);background:rgba(124,92,255,.22);border-color:rgba(160,140,255,.6)}
.trust{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr))}
.trust .card{gap:6px}
.trust strong{font-size:1.05rem}
.trust span{color:var(--mut);font-size:.92rem}
.prose p{color:var(--mut);margin-top:10px;max-width:62ch}
footer{margin-top:64px;padding:28px 0;border-top:1px solid var(--line);color:var(--mut);font-size:.82rem}
footer p{max-width:70ch;margin-bottom:8px}
.sticky{position:fixed;left:0;right:0;bottom:0;z-index:30;
padding:12px 16px calc(12px + env(safe-area-inset-bottom));
background:rgba(10,10,25,.72);-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px);
border-top:1px solid var(--line)}
.sticky .wrap{display:flex;gap:12px;align-items:center;justify-content:space-between}
.sticky span{font-size:.85rem;color:var(--mut);line-height:1.3}
.sticky span b{color:var(--txt);display:block;font-size:.95rem}
.sticky .btn{min-height:48px;padding:0 20px;white-space:nowrap}
.rv{opacity:0;transform:translateY(26px);transition:opacity .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms),
transform .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms)}
.rv.in{opacity:1;transform:none}
.rv.in.card:hover{transform:translateY(-8px)}
a:focus-visible,.btn:focus-visible{outline:3px solid var(--b);outline-offset:3px}
@media(max-width:560px){.sticky span{display:none}.sticky .btn{width:100%}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}
.rv{opacity:1;transform:none}}
"""

JS = """
(function(){
var io=new IntersectionObserver(function(es){es.forEach(function(e){
if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:.12});
document.querySelectorAll('.rv').forEach(function(el){io.observe(el)});
document.querySelectorAll('.card').forEach(function(c){
c.addEventListener('pointermove',function(e){var r=c.getBoundingClientRect();
c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')})});
})();
"""

SHELL = """<!doctype html><html lang="%%LANG%%"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#06060f">
<title>%%TITLE%%</title><meta name="description" content="%%DESC%%">
<link rel="canonical" href="%%CANON%%">
<meta property="og:title" content="%%TITLE%%"><meta property="og:description" content="%%DESC%%">
<meta property="og:type" content="website"><meta property="og:url" content="%%CANON%%">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>%%CSS%%</style>
<noscript><style>.rv{opacity:1;transform:none}</style></noscript></head>
<body><div class="aurora"><i></i><i></i><i></i></div>
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


def product_card(p, idx=0, featured=False):
    icon, cat, name, hook, benefits, ideal, query = p
    items = "".join(f"<li>{esc(b)}</li>" for b in benefits)
    badge = '<span class="tag hot">Destacado de hoy</span>' if featured else f'<span class="tag">{esc(cat)}</span>'
    return (f'<article class="card rv{" feat" if featured else ""}" style="--d:{idx * 90}ms">'
            f'<div class="ico">{icon}</div>{badge}<h3>{esc(name)}</h3>'
            f'<p class="hook">{esc(hook)}</p><ul class="ben">{items}</ul>'
            f'<p class="ideal"><b>Ideal si</b> {esc(ideal)}.</p>'
            f'<a class="btn" href="{affiliate_url(query)}" rel="sponsored nofollow noopener" '
            f'target="_blank">Ver precio actual en Amazon</a></article>')


TRUST = """<div class="trust">
<div class="card rv"><strong>Nueva selección cada día</strong><span>Los productos cambian a diario según lo que la gente busca.</span></div>
<div class="card rv" style="--d:90ms"><strong>Sin ruido</strong><span>Solo cinco opciones a la vez, con lo esencial para decidir.</span></div>
<div class="card rv" style="--d:180ms"><strong>Compra en Amazon</strong><span>Precio, stock y devoluciones los gestiona Amazon.</span></div></div>"""


def render_index(db, picks, out):
    pub = db.execute("SELECT kw FROM keywords WHERE published=1 "
                     "ORDER BY created DESC, score DESC LIMIT 16").fetchall()
    chips = "".join(f'<a class="chip" href="{slugify(k)}.html">{esc(k)}</a>' for (k,) in pub)
    cards = "".join(product_card(p, i, featured=(i == 0)) for i, p in enumerate(picks))
    trends = (f'<h2 class="sec">Lo que se busca ahora</h2>'
              f'<p class="sub">Guías rápidas sobre las búsquedas de compra más activas.</p>'
              f'<div class="chips">{chips}</div>') if chips else ""
    body = (f'<main class="wrap"><section class="hero"><h1>La tecnología que sí merece tu dinero</h1>'
            f'<p>Cada día, {len(picks)} productos elegidos según búsquedas reales. '
            f'Rápido de leer, fácil de decidir.</p>'
            f'<a class="btn" href="#hoy">Ver selección de hoy</a></section>'
            f'<h2 class="sec" id="hoy">Selección del {date_es(dt.date.today())}</h2>'
            f'<p class="sub">Cinco productos nuevos cada día, sin repetir los de ayer.</p>'
            f'<div class="grid">{cards}</div>{trends}'
            f'<h2 class="sec">Cómo funciona</h2>{TRUST}</main>')
    first = picks[0]
    (out / "index.html").write_text(page(
        f"{CONFIG['SITE_NAME']}: tecnología recomendada hoy",
        "Selección diaria de productos tecnológicos con las mejores opciones para comprar hoy.",
        f"{CONFIG['SITE_URL']}/index.html", body,
        first[2][:34] + "…", affiliate_url(first[6])), encoding="utf-8")


def render_keyword_page(kw, picks_pool, out):
    related = [r for r in autocomplete(kw) if r != kw][:8]
    chips = "".join(f'<a class="chip" rel="sponsored nofollow noopener" target="_blank" '
                    f'href="{affiliate_url(r)}">{esc(r)}</a>' for r in related)
    rel_html = (f'<h2 class="sec">Búsquedas relacionadas</h2><div class="chips">{chips}</div>'
                if chips else "")
    sample = random.Random(kw).sample(picks_pool, 3)
    cards = "".join(product_card(p, i) for i, p in enumerate(sample))
    year = dt.date.today().year
    body = (f'<main class="wrap"><section class="hero"><h1>{esc(kw.capitalize())}</h1>'
            f'<p>Guía rápida para elegir bien: qué mirar antes de comprar y dónde comparar '
            f'precios actualizados.</p>'
            f'<a class="btn" href="{affiliate_url(kw)}" rel="sponsored nofollow noopener" '
            f'target="_blank">Ver ofertas de {esc(kw)}</a></section>'
            f'<div class="card rv prose"><h3>Qué revisar antes de comprar</h3><ul class="ben">'
            f'<li>Valoraciones reales y número de opiniones.</li>'
            f'<li>Relación calidad-precio frente a alternativas.</li>'
            f'<li>Garantía, devoluciones y plazo de entrega.</li>'
            f'<li>Historial de precio: compara antes de decidir.</li></ul></div>'
            f'{rel_html}<h2 class="sec">También te puede interesar</h2>'
            f'<div class="grid">{cards}</div></main>')
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
        time.sleep(0.4)
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
