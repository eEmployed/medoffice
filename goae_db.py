import json
import os
import sys


def get_data_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "goae_data.json")
    return os.path.join(os.path.dirname(__file__), "goae_data.json")


def load_goae_data():
    with open(get_data_path(), encoding="utf-8") as f:
        return json.load(f)


def find_matching_codes(diagnosis_text, goae_data):
    """Findet passende GOAe-Ziffern fuer einen Diagnosetext."""
    text_lower = diagnosis_text.lower()
    codes = goae_data["codes"]
    mappings = goae_data["mappings"]

    matched_codes = {}
    matched_label = None

    # 1. Keyword-Mappings pruefen
    best_match_count = 0
    for mapping in mappings:
        match_count = sum(1 for kw in mapping["keywords"] if kw in text_lower)
        if match_count > best_match_count:
            best_match_count = match_count
            matched_codes = {}
            for code in mapping["codes"]:
                if code in codes:
                    matched_codes[code] = codes[code]
            matched_label = mapping["label"]

    # 2. Wenn kein Mapping passt: Freitext-Suche in Beschreibungen
    if not matched_codes:
        words = [w for w in text_lower.split() if len(w) > 3]
        for code, desc in codes.items():
            desc_lower = desc.lower()
            if any(word in desc_lower for word in words):
                matched_codes[code] = desc

    # 3. Immer Grundleistungen als Basis anbieten
    if matched_codes and "1" not in matched_codes:
        matched_codes["1"] = codes.get("1", "Beratung")

    return matched_codes, matched_label


def validate_codes(selected_codes, goae_data, patient_info=None):
    """Prueft GOAe-Ziffern auf Abrechnungsregeln und gibt Warnungen zurueck.

    Args:
        selected_codes: Liste von Ziffer-Strings die geprueft werden sollen
        goae_data: Die geladene GOAe-Datenbank
        patient_info: Dict mit 'age' (int), 'gender' ('m'/'w') oder None

    Returns:
        Dict mit code -> Liste von Warnungen/Fehlern:
        {
            "1": [],                                    # keine Probleme
            "K1": [{"type": "age", "msg": "...", "blocking": True}],
            "5": [{"type": "exclusion", "msg": "...", "blocking": True, "conflicts_with": ["6"]}]
        }
    """
    rules = goae_data.get("rules", {})
    warnings = {code: [] for code in selected_codes}

    age = patient_info.get("age") if patient_info else None
    gender = patient_info.get("gender") if patient_info else None

    for code in selected_codes:
        code_rules = rules.get(code, {})

        # 1. Alterspruefung
        age_min = code_rules.get("age_min")
        age_max = code_rules.get("age_max")
        if age is not None:
            if age_min is not None and age < age_min:
                warnings[code].append({
                    "type": "age",
                    "msg": f"Erst ab {age_min} Jahren (Patient: {age} J.)",
                    "blocking": True
                })
            if age_max is not None and age > age_max:
                warnings[code].append({
                    "type": "age",
                    "msg": f"Nur bis {age_max} Jahre (Patient: {age} J.)",
                    "blocking": True
                })

        # 2. Geschlechtspruefung
        req_gender = code_rules.get("gender")
        if req_gender and gender and gender != req_gender:
            gender_label = "Frauen" if req_gender == "w" else "Maenner"
            warnings[code].append({
                "type": "gender",
                "msg": f"Nur fuer {gender_label}",
                "blocking": True
            })

        # 3. Ausschlusspruefung (Kombinationsverbote)
        exclusions = code_rules.get("exclusions", [])
        for other_code in selected_codes:
            if other_code != code and other_code in exclusions:
                other_desc = goae_data["codes"].get(other_code, other_code)
                warnings[code].append({
                    "type": "exclusion",
                    "msg": f"Nicht neben Ziffer {other_code} ({other_desc})",
                    "blocking": True,
                    "conflicts_with": other_code
                })

    return warnings


def get_code_fee(code, goae_data, factor=2.3):
    """Berechnet die Gebuehr fuer eine Ziffer bei gegebenem Steigerungsfaktor."""
    rules = goae_data.get("rules", {})
    code_rules = rules.get(code, {})
    base_fee = code_rules.get("fee_simple", 0)
    return round(base_fee * factor, 2)


def get_total_fees(codes, goae_data, factor=2.3):
    """Berechnet die Gesamtsumme fuer eine Liste von Ziffern."""
    total = 0
    for code in codes:
        total += get_code_fee(code, goae_data, factor)
    return round(total, 2)


def get_code_info(code, goae_data):
    """Gibt alle Infos zu einer Ziffer zurueck (Beschreibung, Punkte, Gebuehren)."""
    rules = goae_data.get("rules", {})
    code_rules = rules.get(code, {})
    return {
        "code": code,
        "description": goae_data["codes"].get(code, "Unbekannt"),
        "points": code_rules.get("points", 0),
        "fee_simple": code_rules.get("fee_simple", 0),
        "fee_2_3": code_rules.get("fee_2_3", 0),
        "fee_3_5": code_rules.get("fee_3_5", 0),
        "exclusions": code_rules.get("exclusions", []),
        "age_min": code_rules.get("age_min"),
        "age_max": code_rules.get("age_max"),
        "gender": code_rules.get("gender"),
        "frequency": code_rules.get("frequency")
    }
