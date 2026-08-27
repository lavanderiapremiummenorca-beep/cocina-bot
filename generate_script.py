# -*- coding: utf-8 -*-
"""
Escribe el guion del dia con IA (Gemini) siguiendo PROMPT-MAESTRO.md.
Se activa solo si existe GEMINI_API_KEY. Si falla algo, devuelve None
y el sistema usa el banco de guiones (scripts.json) como reserva.
Devuelve un dict con el mismo formato que usa generate.py.
"""
import os, sys, json, datetime, random, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("GEMINI_MODEL", "").strip()  # vacio = autodetectar modelo valido
# Candidatos por si ListModels no responde (de mas nuevo a mas compatible).
_MODEL_CANDIDATES = [
    "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash",
    "gemini-2.5-flash-lite", "gemini-2.0-flash-001", "gemini-1.5-flash",
]
BGS = ["blue", "green", "orange", "purple", "teal", "red"]
# TIPOS DE PLATO que rotan por dia (se usan como "a evitar hoy" para forzar variedad)
TEMAS = [
    "pasta", "arroz", "pollo", "huevos", "cremas y sopas", "postres expres",
    "tostas y bocadillos", "verduras", "legumbres", "pescado", "tortillas",
    "ensaladas templadas", "salsas caseras", "desayunos", "meriendas dulces",
    "cenas rapidas", "platos de una sola sarten", "aperitivos",
]
# ESTILOS que se intercalan cada dia (una receta apetecible, no una lista de tips)
FORMATOS = [
    "la receta rapida paso a paso, apetecible de principio a fin",
    "que ceno hoy: una cena facil que resuelve el dia",
    "el truco que sube de nivel un plato de siempre",
    "una receta con pocos ingredientes (4 o 5) y mucho sabor",
    "el clasico reinventado en version rapida",
    "el plato que impresiona sin apenas esfuerzo",
]

SCHEMA_INSTRUCCION = """
Devuelve UNICAMENTE un JSON valido (sin texto alrededor) con esta forma exacta:
{
  "title": "titulo apetecible y concreto, max 90 caracteres, puede llevar 1 emoji y #shorts",
  "description": "1-2 frases que abran el apetito + invitar a guardar. Anade al final: 'Guardalo para cuando no sepas que cocinar.'",
  "hashtags": ["Shorts", "receta", "cocina", "recetasfaciles"],  // 3 a 5, sin '#', el primero SIEMPRE 'Shorts'
  "bg": "uno de: orange, red, green, teal (tonos calidos y apetecibles)",
  "broll": "2-4 palabras EN INGLES del plato/accion (ej: 'pasta cooking closeup')",
  "broll_list": ["3 o 4 planos apetecibles EN INGLES, en orden (ej: 'sizzling pan closeup', 'chopping fresh vegetables', 'plating finished dish steam')"],
  "ai_disclosure": false,
  "lines": [
    {"voice": "frase corta y apetecible (numeros en palabras: 'dos huevos', no '2')",
     "cap": "subtitulo MUY corto en pantalla (2-4 palabras, puede llevar cifras)"}
  ]
}
Reglas del guion (formato 'Que ceno hoy'):
- Entre 8 y 11 lineas. Guia una receta REAL y sencilla, paso a paso, de forma apetecible (el video dura 30-45 s).
- NO ES UNA LISTA DE TIPS: es una receta o un plato que da hambre y se quiere guardar. Nada de 'sabias que' ni 'top 3 trucos'.
- APERTURA (linea 1, VARIADA cada dia, nunca identica a la de ayer): arranca con el plato ya hecho o su promesa irresistible. Ej: 'Esta cena esta lista en diez minutos y sabe a gloria.'
- CIERRE (ultima linea, VARIADO cada dia): invita a guardarlo. Ej: 'Guardalo para esta noche.'
- Cantidades y pasos realistas y faciles de seguir. 'cap' sin emojis. 'voice' con numeros en letras.
- Espanol de Espana, cercano y con ganas. Nada de consejo dietetico o medico.
"""
def _run_seed():
    try:
        return int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    except ValueError:
        return 0

def _pick(lst, salt=0):
    y = datetime.date.today().timetuple().tm_yday
    return lst[(y + _run_seed() + salt) % len(lst)]

def _list_models(key):
    """Pregunta a Google que modelos existen de verdad para esta clave."""
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/models"
               f"?key={key}&pageSize=200")
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
        out = []
        for m in data.get("models", []):
            if "generateContent" in (m.get("supportedGenerationMethods") or []):
                out.append(m.get("name", "").replace("models/", ""))
        return out
    except Exception:
        return []

def _model_order(key):
    """Orden a probar: modelo forzado por env -> candidatos -> los reales
    de la cuenta (priorizando 'flash')."""
    order = []
    if MODEL:
        order.append(MODEL)
    for m in _MODEL_CANDIDATES:
        if m not in order:
            order.append(m)
    disc = _list_models(key)
    for m in disc:
        if "flash" in m and m not in order:
            order.append(m)
    for m in disc:
        if m not in order:
            order.append(m)
    return order

def _post_generate(model, prompt, key):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.95, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]

def _call_gemini(prompt, key):
    """Prueba varios modelos y usa el primero que responda (sobrevive a que
    Google jubile un modelo). Solo falla si NINGUNO funciona."""
    last = None
    for model in _model_order(key):
        try:
            txt = _post_generate(model, prompt, key)
            sys.stderr.write(f"[ai] modelo usado: {model}\n")
            return txt
        except Exception as e:
            last = e
    raise RuntimeError(f"ningun modelo Gemini respondio: {last}")

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
    s.setdefault("description", "Una cena facil y rica en menos de lo que crees. Guardalo para cuando no sepas que cocinar.")
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
        master = "Eres un cocinero creativo de YouTube Shorts en espanol que hace recetas rapidas, apetecibles y faciles de guardar."
    formato = random.choice(FORMATOS)
    hoy = datetime.date.today().isoformat()
    # Usamos TEMAS solo como "lo obvio a EVITAR", para empujar novedad
    evitar = ", ".join(random.sample(TEMAS, min(6, len(TEMAS)))) if TEMAS else ""
    seed = _run_seed()
    prompt = (master
              + f"\n\n---\nTAREA DE HOY ({hoy}):\n"
              + "CREA una receta o plato NUEVO, sencillo y apetecible para hoy. "
                "Elige tu mismo el plato; que de hambre y se quiera guardar.\n"
              + (f"Para forzar variedad, HOY evita estos tipos de plato (elige otro): {evitar}.\n" if evitar else "")
              + f"Presentalo con este ESTILO de hoy: {formato}.\n"
              + "Apertura y cierre VARIADOS (nunca los de ayer); titulo y descripcion UNICOS de hoy. Que HOY se note claramente distinto a cualquier dia anterior. Es una receta apetecible, NO una lista de tips.\n"
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
