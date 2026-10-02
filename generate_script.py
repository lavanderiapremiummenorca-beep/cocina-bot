# -*- coding: utf-8 -*-
"""
Cerebro del canal COCINA ("Cocina Facil").
Gemini ELIGE el tema libre cada dia (dentro del canal). Para que no se repita ni
derive, se le pasa una PISTA rotatoria distinta cada dia (un area/enfoque), ademas
de formato, gancho y cierre (todo por rotacion determinista).
Devuelve el mismo dict que usa generate.py.
"""
import os, sys, json, datetime, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("GEMINI_MODEL", "").strip()
_MODEL_CANDIDATES = [
    "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash",
    "gemini-2.5-flash-lite", "gemini-2.0-flash-001", "gemini-1.5-flash",
]

CANAL_NOMBRE = "COCINA FACIL"
HASHTAGS_BASE = ("cocina", "recetas", "trucosdecocina", "cocinafacil")
TEMA_GENERICO = "la cocina"
TITULO_FALLBACK = "3 trucos de {base} que te cambian la cena"
BG_DEFAULT = "orange"
BROLL_FALLBACK = "close up of a spanish dish, steam rising, warm kitchen window light"
BROLL_EJEMPLOS = ("primerisimos planos de comida, apetitosos y con vapor, luz calida de ventana; "
                  "ej: 'close up of a golden spanish omelette being flipped in a pan, steam rising', "
                  "'hands slicing an onion on a wooden board, macro, warm kitchen light', "
                  "'overhead shot of garlic sizzling in olive oil in a black pan'")
TONO = ("cercano y practico, como un amigo que cocina bien y te lo cuenta rapido. Espanol de Espana. "
        "Cada frase, un paso o un dato util. Nada de relleno.")
REGLA_EXTRA = ("- Planos de COMIDA y de MANOS cocinando (macro, cenital, sarten, tabla), NO personas posando.\n"
               "- Cada escena muestra el paso exacto que se esta narrando en ese momento.\n"
               "- Nada de consejos medicos, dietas para adelgazar ni promesas de salud. Cocina y punto.")
MASTER_FALLBACK = "Eres un guionista de Shorts de cocina practica en espanol de Espana."

PISTAS = [
    ("platos de cuchara: guisos, potajes y legumbres", "chickpea stew bubbling in a clay pot, steam"),
    ("todo lo que se puede hacer con huevos", "poached egg cut open, yolk running, macro"),
    ("arroces y como no arruinarlos", "white rice steaming in a pot, macro"),
    ("pasta como en Italia con pocas cosas", "spaghetti being tossed in a pan with sauce"),
    ("carnes jugosas y bien hechas", "steak resting on a board, juices visible, warm light"),
    ("pescado sin que se pegue ni huela", "fish fillet searing skin down in a hot pan"),
    ("verduras con sabor, no hervidas y tristes", "roasted vegetables on a tray, charred edges"),
    ("postres rapidos con lo que tienes en casa", "chocolate dessert in a glass, spoon dipping in"),
    ("panes y masas: revivirlos y no tirarlos", "rustic bread loaf sliced on a wooden board"),
    ("salsas, sofritos y aliños que salvan un plato", "creamy sauce being whisked in a small pan"),
    ("tecnicas de sarten y control del fuego", "empty hot pan with a drop of oil shimmering"),
    ("trucos de cuchillo y de corte", "chef knife dicing an onion on a wooden board, macro"),
    ("conservar mejor y aprovechar las sobras", "labelled food containers in a fridge, cold light"),
    ("desayunos rapidos que no son cereales", "toast with tomato and olive oil, morning light"),
    ("tapas y aperitivos faciles para invitados", "small tapas plates on a bar counter"),
    ("freidora de aire y microondas bien usados", "air fryer basket full of golden potatoes"),
    ("mitos de cocina que son mentira", "kitchen counter with contrasting ingredients, top down"),
    ("trucos de abuela que funcionan de verdad", "old wooden spoon and copper pot, rustic kitchen"),
]

FORMATOS = [
    "3 TRUCOS: tres trucos concretos sobre el tema, del mas conocido al que nadie usa.",
    "EL ERROR: el fallo que casi todo el mundo comete con esto, por que pasa y como se arregla.",
    "PASO A PASO: una receta o tecnica del tema en cuatro pasos rapidisimos y clarisimos.",
    "MITO O VERDAD: tres creencias sobre el tema, cuales son mentira y que hacer en su lugar.",
    "4 USOS: cuatro maneras de usar esto que no se te habian ocurrido, la mejor al final.",
]

GANCHOS = [
    "abre diciendo el error concreto que el espectador hace cada semana en su cocina, y remata con 'y hay algo peor'",
    "abre con el resultado apetitoso prometido en una frase que se ve en la cabeza (textura, color, sonido)",
    "abre desmontando algo que todo el mundo hace en la cocina y esta mal",
    "abre con una escena concreta de sarten o cuchillo, en presente, como si lo estuvieras haciendo ahora",
    "abre con el ahorro real (tiempo, dinero o platos sucios) que consigue el truco de hoy",
]

CTAS = [
    "¿Tú cómo lo haces? Cuéntamelo abajo.",
    "Guarda esto para la próxima cena.",
    "¿Cuál vas a probar hoy? Comenta.",
    "Dime qué plato quieres el próximo día.",
    "Sígueme, que mañana va otro truco.",
]

POWER = ("truco", "trucos", "error", "no vas a creer", "jamas", "deja de", "asi si",
         "perfecto", "perfecta", "en minutos", "sin", "mejor", "facil", "secreto", "nadie")

BGS = ["blue", "green", "orange", "purple", "teal", "red"]


def _run_seed():
    try:
        return int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    except ValueError:
        return 0

def _daykey():
    return datetime.date.today().toordinal() + _run_seed()

def _rot(lst, stride):
    return lst[(_daykey() * stride) % len(lst)]


def _list_models(key):
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/models"
               f"?key={key}&pageSize=200")
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
        return [m.get("name", "").replace("models/", "") for m in data.get("models", [])
                if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    except Exception:
        return []

def _model_order(key):
    order = []
    if MODEL:
        order.append(MODEL)
    for m in _MODEL_CANDIDATES:
        if m not in order:
            order.append(m)
    disc = _list_models(key)
    # Prioriza Gemini 'flash', luego otros Gemini, luego el resto.
    # Los 'gemma' (no dan JSON fiable) van al final.
    for m in disc:
        if "gemini" in m and "flash" in m and m not in order:
            order.append(m)
    for m in disc:
        if "gemini" in m and m not in order:
            order.append(m)
    for m in disc:
        if "gemma" not in m and m not in order:
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
        "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]

def _extract_json(txt):
    """Saca un JSON valido aunque el modelo lo envuelva en ```json ... ``` o texto."""
    if not txt:
        return None
    t = txt.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j != -1 and j > i:
        t = t[i:j + 1]
    try:
        return json.loads(t)
    except Exception:
        return None

def _gen_json(prompt, key):
    """Prueba modelos hasta obtener un JSON valido. Salta los que fallen o
    devuelvan basura (p.ej. gemma con respuesta vacia). None si ninguno lo da."""
    last = None
    for model in _model_order(key):
        try:
            txt = _post_generate(model, prompt, key)
        except Exception as e:
            last = e
            continue
        obj = _extract_json(txt)
        if isinstance(obj, dict) and obj.get("lines"):
            sys.stderr.write(f"[ai] modelo usado: {model}\n")
            return obj
        sys.stderr.write(f"[ai] {model} no dio JSON valido; pruebo otro.\n")
    if last:
        sys.stderr.write(f"[ai] ultimo error: {last}\n")
    return None


# Red de seguridad: si el modelo escribe sin enes ni tildes, se restauran las
# palabras mas comunes (el subtitulo salia como "MANANA" en vez de "MANANA" con ene).
_ORTO = {
    "manana": "mañana", "ano": "año", "anos": "años", "nino": "niño", "ninos": "niños",
    "nina": "niña", "ninas": "niñas", "senor": "señor", "senora": "señora",
    "espanol": "español", "espanola": "española", "Espana": "España", "espana": "España",
    "pequeno": "pequeño", "pequena": "pequeña", "sueno": "sueño", "suenos": "sueños",
    "bano": "baño", "banos": "baños", "compania": "compañía", "montana": "montaña",
    "manana,": "mañana,", "ensenar": "enseñar", "ensena": "enseña", "diseno": "diseño",
    "extrano": "extraño", "dano": "daño", "danos": "daños", "puno": "puño",
    "canon": "cañón", "otono": "otoño", "sueno.": "sueño.", "duena": "dueña",
    "dueno": "dueño", "acompanar": "acompañar", "manana.": "mañana.",
}

def _fix_orto(txt):
    if not isinstance(txt, str) or not txt:
        return txt
    out = []
    for w in txt.split(" "):
        low = w.lower()
        rep = _ORTO.get(low) or _ORTO.get(w)
        if rep:
            if w[:1].isupper():
                rep = rep[:1].upper() + rep[1:]
            out.append(rep)
        else:
            out.append(w)
    return " ".join(out)


def _validate(s, tema="", cta="", broll_en=""):
    assert isinstance(s.get("lines"), list) and 4 <= len(s["lines"]) <= 12, "lineas fuera de rango"
    for ln in s["lines"]:
        assert ln.get("voice"), "linea sin voz"
        ln.setdefault("cap", "")
        ln["voice"] = _fix_orto(ln["voice"])
        ln["cap"] = _fix_orto(ln["cap"])
    s.setdefault("bg", BG_DEFAULT)
    if s["bg"] not in BGS:
        s["bg"] = BG_DEFAULT
    hs = [h.lstrip("#") for h in s.get("hashtags", []) if h.strip()]
    if not hs or hs[0].lower() != "shorts":
        hs = ["Shorts"] + [h for h in hs if h.lower() != "shorts"]
    s["hashtags"] = (hs + list(HASHTAGS_BASE))[:6]

    # TITULO: obliga a que lleve un numero o una palabra potente
    t = _fix_orto((s.get("title") or "").strip())
    low = t.lower()
    tiene_num = any(c.isdigit() for c in t) or any(w in low for w in
        ("tres", "cuatro", "cinco", "dos"))
    tiene_power = any(p in low for p in POWER)
    if not t:
        base = (tema or TEMA_GENERICO).strip()
        t = TITULO_FALLBACK.format(base=base)
    if "#short" not in low:
        t = t + " #shorts"
    s["title"] = t

    # CTA obligatorio como ultima linea (cebo de comentarios)
    if cta:
        last = (s["lines"][-1].get("voice", "") or "").lower()
        if "coment" not in last and "abajo" not in last and "sigue" not in last and "guarda" not in last:
            s["lines"].append({"voice": cta, "cap": "comenta abajo"})

    if not (s.get("description") or "").strip():
        s["description"] = (t.replace(" #shorts", "") + ". " + (cta or "")).strip()
    s["description"] = _fix_orto(s["description"]).rstrip()

    # BROLL como pista de imagen
    bl = s.get("broll_list")
    if not isinstance(bl, list) or not bl:
        bl = [broll_en] if broll_en else []
    bl = [b.strip() for b in bl if isinstance(b, str) and b.strip()][:12]
    if bl:
        s["broll_list"] = bl
        s["broll"] = bl[0]
    elif broll_en:
        s["broll_list"] = [broll_en]; s["broll"] = broll_en

    try:
        s["video_idx"] = int(s.get("video_idx", -1))
    except (TypeError, ValueError):
        s["video_idx"] = -1
    s["ai_disclosure"] = False
    s["id"] = "ia-" + datetime.date.today().isoformat()
    s.pop("chart", None)
    return s


def _schema(broll_en, formato, gancho, cta, pista):
    hs = '", "'.join(["Shorts"] + list(HASHTAGS_BASE))
    return f"""
Devuelve UNICAMENTE un JSON valido (sin texto alrededor) con esta forma exacta:
{{
  "title": "titulo IMPACTANTE con un NUMERO y/o una palabra potente. Sobre el tema de HOY. Max 80 caracteres, 1 emoji opcional, incluye #shorts.",
  "description": "1-2 frases con gancho + hashtags. Termina invitando a comentar.",
  "hashtags": ["{hs}"],
  "bg": "uno de: orange, red, purple, teal",
  "broll": "{broll_en}",
  "broll_list": ["una ESCENA para RECREAR con IA por CADA linea, EN INGLES, concreta, con ACCION, lugar y luz ({BROLL_EJEMPLOS}). En el MISMO orden que 'lines'. UNA escena por CADA linea (mismo numero de escenas que de lineas), y cada escena debe mostrar EXACTAMENTE lo que se narra en esa linea. Describe una imagen VIVA, como un plano de cine."],
  "ai_disclosure": false,
  "video_idx": "indice 0-based de la ESCENA de broll_list que MAS ganaria con MOVIMIENTO de video real (la mas dinamica). Devuelve -1 si ninguna lo necesita. Como MUCHO una.",
  "lines": [
    {{"voice": "frase que se narra (numeros en palabras)", "cap": "subtitulo corto en pantalla (2-4 palabras)"}}
  ]
}}
GUION DE HOY (canal de {CANAL_NOMBRE}, formato viral, DISTINTO a cualquier dia anterior):
- ELIGE TU EL TEMA DE HOY: libre, dentro del canal de {CANAL_NOMBRE}. Concreto y con gancho. Que sea DISTINTO a lo mas tipico y a lo de dias anteriores; NO te repitas ni tires siempre por lo mismo.
- PISTA PARA VARIAR HOY (orientate hacia esta zona para no caer siempre en lo mismo, pero TU decides el tema y el enfoque exactos, y puedes afinar dentro de ella): {pista}.
- FORMATO DE HOY: {formato}
- LINEA 1 = GANCHO (primer segundo). Tecnica de hoy: {gancho}. PROHIBIDO usar frases-comodin genericas ("el noventa por ciento no sabe esto", "prepara la cabeza", "esto te va a explotar la mente", "agarrate"): NO enganchan, suenan a bot. El gancho debe ser CONCRETO, especifico y util, sacado de lo MAS fuerte del tema de hoy, y ABRIR UN BUCLE (promete algo aun mejor que todavia no cuentas). Nada de empezar con "En [tema]...".
- Luego el contenido, cada parte concreta y VERAZ (nada inventado). De menos a mas: lo mejor al final.
- Encadena con TENSION ("pero lo siguiente es mejor", "y aun hay mas"), NO con "primero, segundo, tercero" a secas.
- ORTOGRAFIA: espanol de Espana IMPECABLE, con TILDES y con la letra ENE (mañana, año, España, sueño, pequeño). NUNCA sustituyas la ñ por n. Cuidado con articulos y concordancia. Frases cortas y en presente.
- ULTIMA LINEA = CIERRE que invita a participar: algo tipo "{cta}".
- Entre 5 y 8 lineas en total. Frases cortas y con energia (ritmo de Short, 30-45 s).
- Tono: {TONO}
- 'cap' sin emojis. 'voice' escribe los numeros con letras.
- SEGURIDAD (obligatorio): las escenas deben ser APTAS PARA YOUTUBE Y PUBLICIDAD. Con fuerza, pero SIN sangre, heridas, cuerpos mutilados, desnudos ni violencia explicita. Nada de caras de personas reales famosas.
{REGLA_EXTRA}
- CRITICO: cada escena de 'broll_list' debe MOSTRAR EXACTAMENTE lo que se narra en esa parte, EN EL MISMO ORDEN. NADA generico ni palabras sueltas: escena de cine con accion + lugar + luz, EN INGLES.
"""


def generate():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        master = open(os.path.join(BASE, "PROMPT-MAESTRO.md"), encoding="utf-8").read()
    except Exception:
        master = MASTER_FALLBACK

    pista, broll_en = _rot(PISTAS, 1)
    tema = ""  # el tema lo ELIGE Gemini; 'pista' solo orienta para no repetir
    formato = _rot(FORMATOS, 3)
    gancho = _rot(GANCHOS, 5)
    cta = _rot(CTAS, 7)
    hoy = datetime.date.today().isoformat()

    prompt = (master
              + f"\n\n---\nTAREA DE HOY ({hoy}):\n"
              + f"Crea un Short de {CANAL_NOMBRE} con el formato viral de abajo. ELIGE tu el tema (libre, del canal, sin repetir), "
                "y sigue EXACTAMENTE el formato, el gancho y el cierre que se te asignan. Todo debe ser VERAZ.\n"
              + _schema(broll_en, formato, gancho, cta, pista))
    try:
        s = _gen_json(prompt, key)
        if not s:
            raise RuntimeError("ningun modelo dio JSON valido")
        s = _validate(s, tema=tema, cta=cta, broll_en=broll_en)
        return s
    except Exception as e:
        sys.stderr.write(f"[ai] no se pudo generar con IA ({e}); se usara el banco.\n")
        return None


if __name__ == "__main__":
    import json as _j
    s = generate()
    print(_j.dumps(s, ensure_ascii=False, indent=2) if s else "None (sin GEMINI_API_KEY o error)")
