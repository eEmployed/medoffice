import re
from datetime import datetime, date


def parse_entries(text):
    entries = []
    current_date = None

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        date_match = re.search(r"\d{2}\.\d{2}\.\d{4}", line)

        if date_match:
            try:
                current_date = datetime.strptime(date_match.group(), "%d.%m.%Y")
            except ValueError:
                continue
            rest = line[date_match.end():].strip()
        else:
            if current_date is None:
                continue
            rest = line

        parts = rest.split()
        if len(parts) < 1:
            continue

        typ = parts[0].lower()
        content = " ".join(parts[1:]) if len(parts) > 1 else ""

        entries.append({
            "date": current_date,
            "type": typ,
            "content": content
        })

    return entries


def get_diagnoses(entries):
    da_entries = [e for e in entries if e["type"].startswith("da")]
    da_entries.sort(key=lambda x: x["date"], reverse=True)
    return da_entries


def parse_patient_info(text):
    """Extrahiert Patientendaten aus OCR-Text des Patientenkopfs.

    Sucht nach Geburtsdatum (dd.mm.yyyy) und Geschlechtshinweisen.
    Gibt dict mit 'birthdate', 'age', 'gender' zurueck.
    """
    result = {"birthdate": None, "age": None, "gender": None}

    # Geburtsdatum finden (dd.mm.yyyy)
    date_matches = re.findall(r"\d{2}\.\d{2}\.\d{4}", text)
    for d in date_matches:
        try:
            bd = datetime.strptime(d, "%d.%m.%Y").date()
            # Plausibilitaet: Geburtsdatum sollte in der Vergangenheit liegen
            # und Person sollte nicht aelter als 120 sein
            today = date.today()
            age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            if 0 <= age <= 120:
                result["birthdate"] = bd
                result["age"] = age
                break
        except ValueError:
            continue

    # Geschlecht erkennen
    text_lower = text.lower()
    male_indicators = ["maennlich", "männlich", "herr ", " m ", " m,", "/m/", "(m)", "mann"]
    female_indicators = ["weiblich", "frau ", " w ", " w,", "/w/", "(w)", " f ", "/f/"]

    male_score = sum(1 for ind in male_indicators if ind in text_lower)
    female_score = sum(1 for ind in female_indicators if ind in text_lower)

    if male_score > female_score:
        result["gender"] = "m"
    elif female_score > male_score:
        result["gender"] = "w"

    return result
