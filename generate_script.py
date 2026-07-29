# -*- coding: utf-8 -*-
"""
Escribe el guion del dia con IA (Gemini) siguiendo PROMPT-MAESTRO.md.
Se activa solo si existe GEMINI_API_KEY. Si falla algo, devuelve None
y el sistema usa el banco de guiones (scripts.json) como reserva.
Devuelve un dict con el mismo formato que usa generate.py.
"""
import os, sys, json, datetime, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
BGS = ["blue", "green", "orange", "purple", "teal", "red"]

# Temas y formatos que rotan por dia para no repetir (anti "contenido inautentico")
TEMAS = [
    "cortar cebolla sin llorar",
    "el arroz en su punto",
    "madurar y conservar el aguacate",
    "pelar ajo rapido",
    "la tortilla jugosa",
    "ablandar la carne",
    "aprovechar las sobras",
    "cocer bien la pasta",
    "masa de pizza rapida",
    "congelar alimentos bien",
    "salsas rapidas caseras",
    "marinar la carne o el pescado",
    "medir sin bascula",
    "evitar que la comida se pegue",
    "postres expres",
    "batch cooking para la semana",
    "trucos con el huevo",
    "el pan casero facil",
    "alinos para ensaladas",
    "conservar hierbas frescas"
]
FORMATOS = [
    "mito vs realidad", "un dato sorprendente con ejemplo numerico",
    "el error comun que casi todos cometen", "top 3 rapido",
    "esto no te lo cuentan", "comparativa antes vs despues",
    "una pregunta que pica la curiosidad y su respuesta",
]

SCHEMA_INSTRUCCION = """
Devuelve UNICAMENTE un JSON valido (sin texto alrededor) con esta forma exacta:
{
  "title": "titulo honesto y con gancho, max 90 caracteres, puede llevar 1 emoji y #shorts",
  "description": "1-2 frases de valor + CTA.",
  "hashtags": ["Shorts", "cocina", "trucos", "recetas"],  // 3 a 5, sin '#', el primero SIEMPRE 'Shorts'
  "bg": "uno de: blue, green, orange, purple, teal, red",
  "broll": "2-4 palabras EN INGLES para metraje de archivo (ej: 'cooking food kitchen')",
  "ai_disclosure": false,
  "lines": [
    {"voice": "frase corta que se narra (con numeros en palabras: 'cien euros', no '100')",
     "cap": "subtitulo MUY corto en pantalla (2-4 palabras, puede llevar cifras)"}
  ]
}
Reglas del guion:
- Entre 10 y 13 lineas. Cada 'voice' es una frase corta y natural (el video debe durar 20-40 s).
- La PRIMERA linea es el gancho: sin saludos ni intro, engancha en el primer segundo.
- La ULTIMA linea es el CTA: invita a seguir ("Sigueme para cocinar mejor cada dia") o a comentar.
- 'cap' nunca lleva emojis (la fuente no los dibuja). 'voice' escribe los numeros con letras.
- Espanol, cercano y apetitoso. Pasos claros y utiles.
"""

def _run_seed():
    try:
        return int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    except ValueError:
        return 0

def _pick(lst, salt=0):
    y = datetime.date.today().timetuple().tm_yday
    return lst[(y + _run_seed() + salt) % len(lst)]

def _call_gemini(prompt, key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.95, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]

def _validate(s):
    assert isinstance(s.get("lines"), list) and 6 <= len(s["lines"]) <= 16, "lineas fuera de rango"
    for ln in s["lines"]:
        assert ln.get("voice"), "linea sin voz"
        ln.setdefault("cap", "")
    s.setdefault("bg", "blue")
    if s["bg"] not in BGS:
        s["bg"] = "blue"
    hs = [h.lstrip("#") for h in s.get("hashtags", []) if h.strip()]
    if not hs or hs[0].lower() != "shorts":
        hs = ["Shorts"] + [h for h in hs if h.lower() != "shorts"]
    s["hashtags"] = hs[:5]
    assert s.get("title"), "sin titulo"
    s.setdefault("description", "Truco de cocina en 30 segundos. Sigueme para cocinar mejor cada dia.")
    s["id"] = "ia-" + datetime.date.today().isoformat()
    s.pop("chart", None)
    return s

def generate():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        master = open(os.path.join(BASE, "PROMPT-MAESTRO.md"), encoding="utf-8").read()
    except Exception:
        master = "Eres un productor experto de YouTube Shorts de cocina y trucos en espanol."
    tema, formato = _pick(TEMAS), _pick(FORMATOS, salt=2)
    seed = _run_seed()
    prompt = (master
              + "\n\n---\nTAREA DE HOY:\n"
              + f"Crea el Short de hoy sobre: {tema}. Formato: {formato}.\n"
              + f"Dale un ENFOQUE ORIGINAL y distinto a cualquier video anterior "
              + f"(variacion #{seed}): cambia el gancho, el ejemplo y las frases exactas. "
              + "No repitas estructuras ni frases hechas.\n"
              + "Cumple TODAS las reglas de arriba (cumplimiento primero, luego viralidad).\n"
              + SCHEMA_INSTRUCCION)
    try:
        raw = _call_gemini(prompt, key)
        s = json.loads(raw)
        s = _validate(s)
        return s
    except Exception as e:
        sys.stderr.write(f"[ai] no se pudo generar con IA ({e}); se usara el banco.\n")
        return None

if __name__ == "__main__":
    import json as _j
    s = generate()
    print(_j.dumps(s, ensure_ascii=False, indent=2) if s else "None (sin GEMINI_API_KEY o error)")
