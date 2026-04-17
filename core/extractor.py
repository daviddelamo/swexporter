"""
SWADE Character Data Extractor
================================
Módulo compartido que contiene toda la lógica de extracción de datos
de personajes exportados desde Foundry VTT (sistema SWADE).

Usado por:
  - main.py (CLI standalone)
  - api/server.py (FastAPI REST endpoint)
"""

import re

# ─────────────────────────────────────────────────
# Constantes y mapeo de nombres de atributos
# ─────────────────────────────────────────────────

ATTR_NAMES = {
    "agility": "Agilidad",
    "smarts": "Astucia",
    "spirit": "Espíritu",
    "strength": "Fuerza",
    "vigor": "Vigor",
}

ATTR_ORDER = ["agility", "smarts", "spirit", "strength", "vigor"]

RANK_NAMES = {
    "novice": "Novato",
    "seasoned": "Experimentado",
    "veteran": "Veterano",
    "heroic": "Heroico",
    "legendary": "Legendario",
}

EQUIP_STATUS = {
    0: "No equipado",
    1: "Llevado",
    2: "Guardado",
    3: "Equipado",
}


# ─────────────────────────────────────────────────
# Funciones de utilidad
# ─────────────────────────────────────────────────

def safe_get(data: dict, *keys, default=None):
    """Acceso seguro a claves anidadas en un diccionario."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current if current is not None else default


def format_die(die_data: dict) -> str:
    """Formatea un dado SWADE: {sides: 8, modifier: 1} → 'd8+1'."""
    if not die_data or not isinstance(die_data, dict):
        return "—"
    sides = die_data.get("sides", 0)
    modifier = die_data.get("modifier", 0)
    if sides == 0:
        return "—"
    result = f"d{sides}"
    if modifier > 0:
        result += f"+{modifier}"
    elif modifier < 0:
        result += f"{modifier}"
    return result


def clean_foundry_links(text: str) -> str:
    """Reemplaza referencias de Foundry VTT como @Compendium[...]{texto},
    @UUID[...]{texto}, @Item[...]{texto} con solo el texto visible."""
    if not text or not isinstance(text, str):
        return text or ""
    # Patrón: @Tipo[referencia]{texto visible}
    text = re.sub(r'@\w+\[[^\]]*\]\{([^}]*)\}', r'\1', text)
    # Patrón alternativo sin llaves: @Tipo[referencia] → eliminar
    text = re.sub(r'@\w+\[[^\]]*\]', '', text)
    return text


def strip_html(text) -> str:
    """Elimina etiquetas HTML y referencias de Foundry VTT. Maneja dicts, listas y None."""
    if text is None:
        return ""
    if isinstance(text, dict):
        text = text.get("value", text.get("name", ""))
    if not isinstance(text, str):
        return str(text) if text else ""
    if not text:
        return ""
    text = clean_foundry_links(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def translate_rank(rank_str: str) -> str:
    """Traduce un rango del inglés al español, o lo deja como está."""
    if not rank_str:
        return "Desconocido"
    return RANK_NAMES.get(rank_str.lower(), rank_str.capitalize())


def _extract_string_or_nested(obj, *nested_keys):
    """Extrae un string de un campo que puede ser string o dict anidado."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for key in nested_keys:
            val = obj.get(key)
            if val and isinstance(val, str):
                return val
    return ""


# ─────────────────────────────────────────────────
# Extracción de datos del JSON
# ─────────────────────────────────────────────────

def extract_basic_info(data: dict) -> dict:
    """Extrae información básica del personaje."""
    system = data.get("system", {})
    details = system.get("details", {})
    advances = system.get("advances", {})

    name = data.get("name", "Sin Nombre")

    species_raw = details.get("species", "")
    species_name = _extract_string_or_nested(species_raw, "name")
    if not species_name:
        ancestry_raw = details.get("ancestry", "")
        species_name = _extract_string_or_nested(ancestry_raw, "name")

    archetype_raw = details.get("archetype", "")
    archetype = _extract_string_or_nested(archetype_raw, "name")

    biography_raw = details.get("biography", "")
    biography = strip_html(_extract_string_or_nested(biography_raw, "value"))
    if not biography:
        notes_raw = details.get("notes", "")
        biography = strip_html(notes_raw if isinstance(notes_raw, str) else "")

    appearance_raw = details.get("appearance", "")
    appearance = strip_html(_extract_string_or_nested(appearance_raw, "value"))

    rank_raw = safe_get(advances, "rank", default="")
    if not rank_raw:
        rank_raw = safe_get(details, "rank", default="")
    rank = translate_rank(rank_raw) if rank_raw else rank_raw

    advances_total = safe_get(advances, "value", default=0)
    if not advances_total:
        advances_total = safe_get(advances, "total", default=0)
    if not advances_total:
        advances_list = advances.get("list", [])
        if isinstance(advances_list, list):
            advances_total = len(advances_list)

    return {
        "name": name,
        "species": species_name,
        "archetype": archetype,
        "biography": biography,
        "appearance": appearance,
        "rank": rank,
        "advances": advances_total,
        "img": data.get("img", ""),
    }


def extract_attributes(data: dict) -> list:
    """Extrae los atributos del personaje en orden."""
    attrs_data = safe_get(data, "system", "attributes", default={})
    attributes = []
    for key in ATTR_ORDER:
        attr = attrs_data.get(key, {})
        die = attr.get("die", {})
        attributes.append({
            "key": key,
            "name": ATTR_NAMES.get(key, key.capitalize()),
            "die": format_die(die),
            "sides": die.get("sides", 0),
            "modifier": die.get("modifier", 0),
        })
    return attributes


def extract_derived_stats(data: dict) -> dict:
    """Extrae estadísticas derivadas: Paso, Parada, Dureza, etc."""
    system = data.get("system", {})
    stats = system.get("stats", {})
    details = system.get("details", {})

    pace = system.get("pace", {})
    if pace and isinstance(pace, dict) and pace.get("ground"):
        speed_val = pace.get("ground", 6)
        running_raw = pace.get("running", {})
        if isinstance(running_raw, dict):
            running_die = format_die({"sides": running_raw.get("die", 6), "modifier": running_raw.get("mod", 0)})
        else:
            running_die = "d6"
    else:
        speed_val = safe_get(stats, "speed", "adjusted", default=0)
        if not speed_val:
            speed_val = safe_get(stats, "speed", "value", default=6)
        running_die = format_die(safe_get(stats, "speed", "runningDie", default={}))

    parry_val = safe_get(stats, "parry", "value", default=2)
    parry_mod = safe_get(stats, "parry", "modifier", default=0)
    parry_shield = safe_get(stats, "parry", "shield", default=0)

    toughness_val = safe_get(stats, "toughness", "value", default=2)
    toughness_armor = safe_get(stats, "toughness", "armor", default=0)
    toughness_base = toughness_val - toughness_armor

    size = safe_get(stats, "size", default=0)

    vitals = system.get("vitals", {})
    bennies = system.get("bennies", vitals.get("bennies", {}))
    if isinstance(bennies, dict):
        bennies_current = bennies.get("value", 0)
        bennies_max = bennies.get("max", 3)
    else:
        bennies_current = 0
        bennies_max = 3

    wounds = system.get("wounds", vitals.get("wounds", {}))
    if isinstance(wounds, dict):
        wounds_current = wounds.get("value", 0)
        wounds_max = wounds.get("max", 3)
    else:
        wounds_current = 0
        wounds_max = 3

    fatigue = system.get("fatigue", vitals.get("fatigue", {}))
    if isinstance(fatigue, dict):
        fatigue_current = fatigue.get("value", 0)
        fatigue_max = fatigue.get("max", 2)
    else:
        fatigue_current = 0
        fatigue_max = 2

    encumbrance_val = safe_get(system, "encumbrance", "value", default=0)
    encumbrance_max = safe_get(system, "encumbrance", "max", default=0)

    currency = details.get("currency", system.get("currency", 0))
    if not isinstance(currency, (int, float)):
        currency = 0

    return {
        "speed": speed_val,
        "running_die": running_die,
        "parry": parry_val,
        "parry_modifier": parry_mod,
        "parry_shield": parry_shield,
        "toughness": toughness_val,
        "toughness_base": toughness_base,
        "toughness_armor": toughness_armor,
        "size": size,
        "bennies_current": bennies_current,
        "bennies_max": bennies_max,
        "wounds_current": wounds_current,
        "wounds_max": wounds_max,
        "fatigue_current": fatigue_current,
        "fatigue_max": fatigue_max,
        "encumbrance_current": encumbrance_val,
        "encumbrance_max": encumbrance_max,
        "currency": currency,
    }


def extract_skills(data: dict) -> list:
    """Extrae las habilidades del personaje desde la lista de items."""
    items = data.get("items", [])
    skills = []
    for item in items:
        if item.get("type") == "skill":
            sys = item.get("system", {})
            die = sys.get("die", {})
            attr_key = sys.get("attribute", "")
            skills.append({
                "name": item.get("name", "Desconocida"),
                "die": format_die(die),
                "sides": die.get("sides", 0),
                "modifier": die.get("modifier", 0),
                "attribute": ATTR_NAMES.get(attr_key, attr_key),
                "attribute_key": attr_key,
                "is_core": sys.get("isCoreSkill", False),
            })
    skills.sort(key=lambda s: (s["attribute"], s["name"]))
    return skills


def extract_edges(data: dict) -> list:
    """Extrae Ventajas (edges) del personaje."""
    items = data.get("items", [])
    edges = []
    for item in items:
        if item.get("type") == "edge":
            sys = item.get("system", {})
            desc = strip_html(sys.get("description", ""))
            edges.append({
                "name": item.get("name", ""),
                "description": desc,
                "rank": sys.get("rank", ""),
                "is_racial": sys.get("isRacial", False),
            })
    edges.sort(key=lambda e: e["name"])
    return edges


def extract_hindrances(data: dict) -> list:
    """Extrae Complicaciones (hindrances) del personaje."""
    items = data.get("items", [])
    hindrances = []
    for item in items:
        if item.get("type") == "hindrance":
            sys = item.get("system", {})
            is_major = sys.get("major", False)
            desc = strip_html(sys.get("description", ""))
            hindrances.append({
                "name": item.get("name", ""),
                "description": desc,
                "severity": "Mayor" if is_major else "Menor",
            })
    hindrances.sort(key=lambda h: (h["severity"], h["name"]))
    return hindrances


def extract_abilities(data: dict) -> list:
    """Extrae Capacidades raciales/especiales (abilities)."""
    items = data.get("items", [])
    abilities = []
    for item in items:
        if item.get("type") == "ability":
            sys = item.get("system", {})
            desc = strip_html(sys.get("description", ""))
            abilities.append({
                "name": item.get("name", ""),
                "description": desc,
            })
    abilities.sort(key=lambda a: a["name"])
    return abilities


def extract_weapons(data: dict) -> list:
    """Extrae armas del inventario."""
    items = data.get("items", [])
    weapons = []
    for item in items:
        if item.get("type") == "weapon":
            sys = item.get("system", {})
            equip = sys.get("equipStatus", 0)
            weapons.append({
                "name": item.get("name", ""),
                "damage": sys.get("damage", "—"),
                "ap": sys.get("ap", 0),
                "range": sys.get("range", "Cuerpo a cuerpo"),
                "rof": sys.get("rof", "1"),
                "notes": sys.get("notes", ""),
                "weight": sys.get("weight", 0),
                "price": sys.get("price", 0),
                "quantity": sys.get("quantity", 1),
                "min_str": sys.get("minStr", "—"),
                "equipped": EQUIP_STATUS.get(equip, "Desconocido"),
                "skill": safe_get(sys, "actions", "skill", default=""),
            })
    weapons.sort(key=lambda w: w["name"])
    return weapons


def extract_armor(data: dict) -> list:
    """Extrae armaduras del inventario."""
    items = data.get("items", [])
    armor_list = []
    for item in items:
        if item.get("type") == "armor":
            sys = item.get("system", {})
            equip = sys.get("equipStatus", 0)
            locs = sys.get("locations", {})
            covered = []
            if locs.get("head"):
                covered.append("Cabeza")
            if locs.get("torso"):
                covered.append("Torso")
            if locs.get("arms"):
                covered.append("Brazos")
            if locs.get("legs"):
                covered.append("Piernas")
            armor_list.append({
                "name": item.get("name", ""),
                "armor": sys.get("armor", 0),
                "notes": sys.get("notes", ""),
                "weight": sys.get("weight", 0),
                "price": sys.get("price", 0),
                "min_str": sys.get("minStr", "—"),
                "equipped": EQUIP_STATUS.get(equip, "Desconocido"),
                "locations": ", ".join(covered) if covered else "—",
            })
    armor_list.sort(key=lambda a: a["name"])
    return armor_list


def extract_shields(data: dict) -> list:
    """Extrae escudos del inventario."""
    items = data.get("items", [])
    shields = []
    for item in items:
        if item.get("type") == "shield":
            sys = item.get("system", {})
            equip = sys.get("equipStatus", 0)
            shields.append({
                "name": item.get("name", ""),
                "parry": sys.get("parry", 0),
                "cover": sys.get("cover", 0),
                "armor": sys.get("armor", 0),
                "notes": sys.get("notes", ""),
                "weight": sys.get("weight", 0),
                "price": sys.get("price", 0),
                "min_str": sys.get("minStr", "—"),
                "equipped": EQUIP_STATUS.get(equip, "Desconocido"),
            })
    shields.sort(key=lambda s: s["name"])
    return shields


def extract_gear(data: dict) -> list:
    """Extrae equipo general del inventario."""
    items = data.get("items", [])
    gear = []
    for item in items:
        if item.get("type") == "gear":
            sys = item.get("system", {})
            equip = sys.get("equipStatus", 0)
            desc = strip_html(sys.get("description", ""))
            gear.append({
                "name": item.get("name", ""),
                "description": desc,
                "weight": sys.get("weight", 0),
                "price": sys.get("price", 0),
                "quantity": sys.get("quantity", 1),
                "equipped": EQUIP_STATUS.get(equip, "Desconocido"),
            })
    gear.sort(key=lambda g: g["name"])
    return gear


def extract_powers(data: dict) -> dict:
    """Extrae poderes mágicos y puntos de poder."""
    system = data.get("system", {})
    items = data.get("items", [])

    pp_data = system.get("powerPoints", {})
    pp_pools = []
    total_current = 0
    total_max = 0
    for pool_name, pool_val in pp_data.items():
        if isinstance(pool_val, dict):
            p_cur = pool_val.get("value", 0) or 0
            p_max = pool_val.get("max", 0) or 0
            if p_max > 0:
                pp_pools.append({
                    "name": pool_name,
                    "current": p_cur,
                    "max": p_max,
                })
                total_current += p_cur
                total_max += p_max

    power_points = {
        "current": total_current,
        "max": total_max,
        "pools": pp_pools,
    }

    arcane_backgrounds = []
    for item in items:
        if item.get("type") == "edge":
            sys_data = item.get("system", {})
            name = item.get("name", "")
            is_ab = sys_data.get("isArcaneBackground", False)
            if is_ab or "trasfondo arcano" in name.lower() or "arcane background" in name.lower():
                arcane_backgrounds.append(name)

    arcane_background = ", ".join(arcane_backgrounds) if arcane_backgrounds else ""

    powers = []
    for item in items:
        if item.get("type") == "power":
            sys = item.get("system", {})
            desc = strip_html(sys.get("description", ""))
            skill = sys.get("skill", "")
            if not skill:
                skill = safe_get(sys, "actions", "trait", default="")
            powers.append({
                "name": item.get("name", ""),
                "pp": sys.get("pp", "—"),
                "range": sys.get("range", "—"),
                "duration": sys.get("duration", "—"),
                "trapping": sys.get("trapping", ""),
                "damage": sys.get("damage", ""),
                "description": desc,
                "rank": sys.get("rank", ""),
                "skill": skill,
                "arcane": sys.get("arcane", ""),
            })
    powers.sort(key=lambda p: p["name"])

    return {
        "power_points": power_points,
        "arcane_background": arcane_background,
        "powers": powers,
        "has_powers": len(powers) > 0 or power_points["max"] > 0,
    }


# ─────────────────────────────────────────────────
# Orquestador principal
# ─────────────────────────────────────────────────

def build_context(data: dict) -> dict:
    """Construye el contexto completo para la plantilla Jinja2."""
    return {
        "info": extract_basic_info(data),
        "attributes": extract_attributes(data),
        "derived": extract_derived_stats(data),
        "skills": extract_skills(data),
        "edges": extract_edges(data),
        "hindrances": extract_hindrances(data),
        "abilities": extract_abilities(data),
        "weapons": extract_weapons(data),
        "armor": extract_armor(data),
        "shields": extract_shields(data),
        "gear": extract_gear(data),
        "magic": extract_powers(data),
    }
