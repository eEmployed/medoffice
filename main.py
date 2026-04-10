import tkinter as tk
from tkinter import messagebox
import threading
import ctypes
import sys
import os

from ocr import load_region, load_inputline_pos, load_patient_region
from ocr import capture_and_ocr, capture_patient_info
from parser import parse_entries, get_diagnoses, parse_patient_info
from goae_db import load_goae_data, find_matching_codes
from auto_entry import enter_codes_in_medical_office
from ui import (
    calibrate_ocr_region, calibrate_patient_region, calibrate_inputline,
    choose_diagnosis, choose_goae_codes, show_status_popup
)


def is_admin():
    """Prueft ob das Programm mit Admin-Rechten laeuft."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def restart_as_admin():
    """Startet das Programm mit Admin-Rechten neu."""
    if getattr(sys, 'frozen', False):
        exe = sys.executable
    else:
        exe = sys.executable
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe,
            " ".join(sys.argv) if not getattr(sys, 'frozen', False) else "",
            None, 1
        )
    except Exception:
        pass
    sys.exit()


# Admin-Check beim Start (nur auf Windows)
if os.name == 'nt' and not is_admin():
    restart_as_admin()

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

run_requested = False
goae_data = None


def update_status():
    """Aktualisiert die Statusanzeige basierend auf der Konfiguration."""
    region = load_region()
    inputline = load_inputline_pos()
    patient = load_patient_region()

    done = sum(1 for x in [region, inputline, patient] if x)

    if done == 3:
        status_var.set("Bereit - F11 druecken")
        status_label.config(fg="#4CAF50")
    elif done > 0:
        missing = []
        if not region:
            missing.append("OCR-Bereich")
        if not patient:
            missing.append("Patientenbereich")
        if not inputline:
            missing.append("Eingabezeile")
        status_var.set(f"Fehlt: {', '.join(missing)}")
        status_label.config(fg="#FF9800")
    else:
        status_var.set("Bitte zuerst kalibrieren (Schritte 1-3)")
        status_label.config(fg="#F44336")


def run():
    global goae_data

    region = load_region()
    if not region:
        status_var.set("Fehler: OCR-Bereich nicht kalibriert")
        return

    if goae_data is None:
        goae_data = load_goae_data()

    # 1. Patientendaten lesen (wenn kalibriert)
    patient_info = None
    patient_region = load_patient_region()
    if patient_region:
        status_var.set("Lese Patientendaten...")
        app.update()
        patient_text = capture_patient_info(patient_region)
        patient_info = parse_patient_info(patient_text)

    # 2. Krankenblatt lesen
    status_var.set("Lese Krankenblatt...")
    app.update()

    text = capture_and_ocr(region)
    entries = parse_entries(text)

    if not entries:
        status_var.set("Keine Eintraege erkannt")
        app.after(3000, update_status)
        return

    # 3. Diagnosen filtern
    diagnoses = get_diagnoses(entries)
    if not diagnoses:
        status_var.set("Keine Diagnosen gefunden")
        app.after(3000, update_status)
        return

    pat_text = ""
    if patient_info:
        parts = []
        if patient_info.get("age") is not None:
            parts.append(f"{patient_info['age']}J")
        if patient_info.get("gender"):
            parts.append(patient_info["gender"])
        if parts:
            pat_text = f" | Patient: {'/'.join(parts)}"

    status_var.set(f"{len(diagnoses)} Diagnose(n) erkannt{pat_text}")
    app.update()

    # 4. Diagnose auswaehlen
    selected = choose_diagnosis(diagnoses)
    if not selected:
        update_status()
        return

    diagnosis_text = selected["content"]

    # 5. GOAe-Ziffern matchen
    matched_codes, matched_label = find_matching_codes(diagnosis_text, goae_data)

    if not matched_codes:
        matched_codes = {
            "1": goae_data["codes"].get("1", "Beratung"),
            "5": goae_data["codes"].get("5", "Symptombezogene Untersuchung"),
        }
        matched_label = "Keine spezifische Zuordnung - Grundleistungen"

    # 6. Ziffern-Auswahl mit Validierung
    selected_codes = choose_goae_codes(
        matched_codes, matched_label, diagnosis_text,
        goae_data, patient_info
    )

    if not selected_codes:
        update_status()
        return

    # 7. Automatisch in Medical Office eintragen
    status_var.set(f"Trage {len(selected_codes)} Ziffern ein...")
    app.update()

    enter_codes_in_medical_office(selected_codes)

    show_status_popup(f"{len(selected_codes)} Ziffern eingetragen")
    update_status()


# Hotkey-System
def trigger_run():
    global run_requested
    run_requested = True


keyboard_registered = False
if HAS_KEYBOARD:
    try:
        def start_hotkeys():
            keyboard.add_hotkey("F11", trigger_run)
            keyboard.wait()
        threading.Thread(target=start_hotkeys, daemon=True).start()
        keyboard_registered = True
    except Exception:
        keyboard_registered = False


# GUI Loop
def check_run():
    global run_requested
    if run_requested:
        run_requested = False
        run()
    app.after(100, check_run)


# === Hauptfenster ===
app = tk.Tk()
app.title("GOAe-Ziffern Assistent")
app.geometry("420x340")
app.resizable(False, False)

# Tkinter-Fallback fuer F11 (funktioniert auch ohne Admin-Rechte)
if not keyboard_registered:
    app.bind_all("<F11>", lambda e: trigger_run())

# Titel
title_frame = tk.Frame(app, bg="#2196F3", height=45)
title_frame.pack(fill="x")
title_frame.pack_propagate(False)
tk.Label(
    title_frame, text="  GOAe-Ziffern Assistent - Orthopaedie",
    font=("Arial", 13, "bold"), fg="white", bg="#2196F3", anchor="w"
).pack(fill="both", expand=True, padx=5)

# Kalibrierungs-Buttons
cal_frame = tk.LabelFrame(app, text="Einrichtung (einmalig)", font=("Arial", 9), padx=10, pady=5)
cal_frame.pack(fill="x", padx=15, pady=(12, 5))

status_var = tk.StringVar()

tk.Button(
    cal_frame, text="1. Krankenblatt-Bereich markieren",
    command=lambda: [calibrate_ocr_region(status_var), update_status()],
    font=("Arial", 9), width=30, anchor="w"
).pack(pady=2)

tk.Button(
    cal_frame, text="2. Patientenkopf-Bereich markieren",
    command=lambda: [calibrate_patient_region(status_var), update_status()],
    font=("Arial", 9), width=30, anchor="w"
).pack(pady=2)

tk.Button(
    cal_frame, text="3. Eingabezeile markieren",
    command=lambda: [calibrate_inputline(status_var), update_status()],
    font=("Arial", 9), width=30, anchor="w"
).pack(pady=2)

# Status
status_label = tk.Label(app, textvariable=status_var, font=("Arial", 11, "bold"))
status_label.pack(pady=12)

# Hotkey-Info
info_frame = tk.Frame(app, bg="#f0f0f0")
info_frame.pack(fill="x", side="bottom")
tk.Label(
    info_frame,
    text="F11 = Diagnose erkennen + Ziffern vorschlagen + eintragen",
    font=("Arial", 10), fg="#666", bg="#f0f0f0", pady=8
).pack()

update_status()
check_run()
app.mainloop()
