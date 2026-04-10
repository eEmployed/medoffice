import pyautogui
import pytesseract
import cv2
import numpy as np
import json
import os
import sys

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CONFIG_FILE = "config.json"


def get_config_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), CONFIG_FILE)
    return CONFIG_FILE


def load_config():
    try:
        with open(get_config_path()) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config):
    with open(get_config_path(), "w") as f:
        json.dump(config, f, indent=2)


def load_region():
    config = load_config()
    region = config.get("ocr_region")
    if region:
        return tuple(region)
    return None


def save_region(region):
    config = load_config()
    config["ocr_region"] = list(region)
    save_config(config)


def load_inputline_pos():
    """Laedt die gespeicherte Position der Medical Office Eingabezeile."""
    config = load_config()
    pos = config.get("inputline_pos")
    if pos:
        return tuple(pos)
    return None


def save_inputline_pos(pos):
    """Speichert die Position der Medical Office Eingabezeile."""
    config = load_config()
    config["inputline_pos"] = list(pos)
    save_config(config)


def load_patient_region():
    """Laedt den kalibrierten Bereich fuer Patientendaten (Kopfzeile)."""
    config = load_config()
    region = config.get("patient_region")
    if region:
        return tuple(region)
    return None


def save_patient_region(region):
    config = load_config()
    config["patient_region"] = list(region)
    save_config(config)


def _preprocess_image(img):
    """Bild fuer OCR vorverarbeiten (Graustufen + Threshold)."""
    img_np = np.array(img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return thresh


def capture_and_ocr(region):
    img = pyautogui.screenshot(region=region)

    width, height = img.size
    img = img.crop((0, 0, int(width * 0.65), height))

    thresh = _preprocess_image(img)
    text = pytesseract.image_to_string(thresh, lang="deu")
    return text


def capture_patient_info(region):
    """Liest Patientendaten (Name, Geburtsdatum, Geschlecht) per OCR aus dem Patientenkopf."""
    img = pyautogui.screenshot(region=region)
    thresh = _preprocess_image(img)
    text = pytesseract.image_to_string(thresh, lang="deu")
    return text
