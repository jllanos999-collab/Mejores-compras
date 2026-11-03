#!/usr/bin/env python3
"""
MÓDULO 1 - Motor autónomo de keywords + sitio SEO de afiliados.

Flujo:  semillas de nicho + Google Trends  ->  autocompletado de Google
        (long-tail con intención de compra) -> puntuación -> páginas HTML
        con enlace de afiliado -> index.html, sitemap.xml, ideas.csv

Dependencias: pip install requests
Ejecutar:     python modulo1_motor.py
Salida:       carpeta ./site (se publica gratis en GitHub Pages)
"""
import csv
import datetime as dt
import html
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
    "SITE_URL": "https://TU_USUARIO.github.io/TU_REPO",  # cámbialo al publicar
    "LANG": "es",
    "GEO": "ES",                       # país para Google Trends
    "AMAZON_DOMAIN": "amazon.es",
    "AMAZON_TAG": "TU_TAG-21",         # tu ID de Amazon Afiliados
    "NICHE_SEEDS": [                   # semillas del nicho (cámbialas a tu gusto)
        "auriculares inalámbricos",
        "robot aspirador",
        "freidora de aire",
        "monitor gaming",
        "teclado mecánico",
    ],
    "NICHE_FILTER": ["auricular", "aspirador", "freidora", "monitor", "teclado"],
    "MODIFIERS": ["mejor", "mejores", "comprar", "barato", "opiniones", "vs", "calidad precio"],
    "MAX_NEW_PAGES_PER_RUN": 10,       # ritmo constante evita parecer spam
    "OUT_DIR": "site",
    "DB_FILE": "keywords.db",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrendBot/1.0)"}
COMMERCIAL_WORDS = {"mejor", "mejores", "comprar", "barato", "opiniones",
                    "vs", "precio", "oferta", "calidad"}


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
    """Sugerencias reales de búsqueda de Google (keywords long-tail)."""
    r = http_get("https://suggestqueries.google.com/complete/search",
                 params={"client": "firefox", "hl": CONFIG["LANG"], "q": query})
    try:
        return [s.lower() for s in r.json()[1]] if r else []
    except (ValueError, IndexError):
        return []


def collect_keywords():
    """Devuelve {keyword: score} combinando semillas, modificadores y tendencias."""
    found = {}
    trends = fetch_trends(CONFIG["GEO"])
    niche_trends = [t for t in trends
                    if any(f in t for f in CONFIG["NICHE_FILTER"])]
    for seed in CONFIG["NICHE_SEEDS"] + niche_trends:
        queries = [seed] + [f"{m} {seed}" for m in CONFIG["MODIFIERS"]]
        for q in queries:
            for kw in autocomplete(q):
                found[kw] = max(found.get(kw, 0), score(kw, kw in niche_trends))
            time.sleep(0.4)  # respeto al servidor
    return found


def score(kw, is_trend):
    """Puntuación simple: intención comercial + longitud ideal + tendencia."""
    words = kw.split()
    s = 2 * len(COMMERCIAL_WORDS.intersection(words))
    s += 1 if 3 <= len(words) <= 6 else 0
    s += 3 if is_trend else 0
    return s


# ============================ BASE DE DATOS ============================
def init_db():
    db = sqlite3.connect(CONFIG["DB_FILE"])
    db.execute("""CREATE TABLE IF NOT EXISTS keywords(
        kw TEXT PRIMARY KEY, score INTEGER, published INTEGER DEFAULT 0,
        created TEXT)""")
    return db


def save_keywords(db, found):
    today = dt.date.today().isoformat()
    for kw, sc in found.items():
        db.execute("INSERT OR IGNORE INTO keywords(kw, score, created) VALUES(?,?,?)",
                   (kw, sc, today))
    db.commit()


# ============================ GENERACIÓN DE SITIO ============================
def slugify(text):
    text = text.lower()
    for a, b in zip("áéíóúñü", "aeiounu"):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def affiliate_url(kw):
    return (f"https://www.{CONFIG['AMAZON_DOMAIN']}/s?k={quote_plus(kw)}"
            f"&tag={CONFIG['AMAZON_TAG']}")


PAGE = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<style>body{{font-family:system-ui;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6}}
.btn{{display:inline-block;background:#f90;color:#111;padding:.8rem 1.2rem;border-radius:8px;
text-decoration:none;font-weight:700}}small{{color:#666}}</style></head><body>
<p><a href="index.html">&larr; {site}</a></p>
<h1>{h1}</h1>
<p>Si buscas <strong>{kw}</strong>, esta guía te ayuda a decidir rápido: qué mirar,
qué evitar y dónde comparar precios actualizados.</p>
<p><a class="btn" rel="sponsored nofollow noopener" target="_blank"
href="{aff}">Ver ofertas de {kw} &rarr;</a></p>
<h2>Qué revisar antes de comprar</h2>
<ul><li>Valoraciones reales y número de opiniones.</li>
<li>Relación calidad-precio frente a alternativas.</li>
<li>Garantía, devoluciones y plazo de entrega.</li>
<li>Historial de precio: compara antes de comprar.</li></ul>
<h2>Búsquedas relacionadas</h2><ul>{related}</ul>
<p><a class="btn" rel="sponsored nofollow noopener" target="_blank"
href="{aff}">Comparar precios ahora</a></p>
<p><small>Divulgación: como afiliado de Amazon obtenemos una comisión por compras
cualificadas, sin coste extra para ti. Actualizado: {date}.</small></p>
</body></html>"""


def build_page(kw, out):
    related_kws = [r for r in autocomplete(kw) if r != kw][:6]
    related = "".join(
        f'<li><a rel="sponsored nofollow noopener" target="_blank" '
        f'href="{affiliate_url(r)}">{html.escape(r)}</a></li>' for r in related_kws
    ) or f"<li>{html.escape(kw)}</li>"
    title = f"{kw.capitalize()}: guía y ofertas ({dt.date.today().year})"
    page = PAGE.format(
        lang=CONFIG["LANG"], title=html.escape(title), site=CONFIG["SITE_NAME"],
        desc=html.escape(f"Guía rápida para elegir {kw}: qué mirar y dónde comprar al mejor precio."),
        canon=f"{CONFIG['SITE_URL']}/{slugify(kw)}.html",
        h1=html.escape(kw.capitalize()), kw=html.escape(kw),
        aff=affiliate_url(kw), related=related, date=dt.date.today().isoformat())
    (out / f"{slugify(kw)}.html").write_text(page, encoding="utf-8")


def build_site(db):
    out = Path(CONFIG["OUT_DIR"])
    out.mkdir(exist_ok=True)
    pending = db.execute(
        "SELECT kw FROM keywords WHERE published=0 ORDER BY score DESC LIMIT ?",
        (CONFIG["MAX_NEW_PAGES_PER_RUN"],)).fetchall()
    for (kw,) in pending:
        build_page(kw, out)
        db.execute("UPDATE keywords SET published=1 WHERE kw=?", (kw,))
        time.sleep(0.4)
    db.commit()

    pub = db.execute("SELECT kw, score FROM keywords WHERE published=1 "
                     "ORDER BY created DESC, score DESC").fetchall()
    links = "".join(f'<li><a href="{slugify(k)}.html">{html.escape(k)}</a></li>'
                    for k, _ in pub)
    (out / "index.html").write_text(
        f'<!doctype html><html lang="{CONFIG["LANG"]}"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{CONFIG["SITE_NAME"]}</title></head>'
        f'<body style="font-family:system-ui;max-width:720px;margin:2rem auto;padding:0 1rem">'
        f'<h1>{CONFIG["SITE_NAME"]}</h1><ul>{links}</ul></body></html>',
        encoding="utf-8")

    urls = "".join(f"<url><loc>{CONFIG['SITE_URL']}/{slugify(k)}.html</loc></url>"
                   for k, _ in pub)
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
    db = init_db()
    found = collect_keywords()
    print(f"Keywords capturadas: {len(found)}")
    save_keywords(db, found)
    n = build_site(db)
    print(f"Páginas nuevas publicadas: {n} -> carpeta '{CONFIG['OUT_DIR']}'")


if __name__ == "__main__":
    main()
