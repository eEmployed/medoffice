import pyautogui
import pytesseract
import tkinter as tk
import json
import re
from datetime import datetime
import threading
import keyboard
import cv2
import numpy as np

# ========================
# 🔤 Tesseract Pfad
# ========================
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CONFIG_FILE = "config.json"

run_requested = False


# ========================
# 🔧 Kalibrierung
# ========================
def calibrate(status_var):
    coords = {"x1": None, "y1": None, "x2": None, "y2": None}

    def on_mouse_down(event):
        coords["x1"], coords["y1"] = event.x, event.y
        canvas.delete("rect")

    def on_mouse_move(event):
        if coords["x1"] is None:
            return
        canvas.delete("rect")
        canvas.create_rectangle(
            coords["x1"], coords["y1"], event.x, event.y,
            outline="red", width=2, tag="rect"
        )

    def on_mouse_up(event):
        coords["x2"], coords["y2"] = event.x, event.y
        root.quit()

    root = tk.Toplevel()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.3)
    root.configure(bg="black")

    canvas = tk.Canvas(root, cursor="cross", bg="black")
    canvas.pack(fill="both", expand=True)

    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)

    root.mainloop()
    root.destroy()

    if None in coords.values():
        return

    x1, y1, x2, y2 = coords["x1"], coords["y1"], coords["x2"], coords["y2"]

    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1, x2)
    bottom = max(y1, y2)

    width = right - left
    height = bottom - top

    if width < 10 or height < 10:
        return

    region = (left, top, width, height)

    with open(CONFIG_FILE, "w") as f:
        json.dump(region, f)

    status_var.set("Bereich markiert ✅")


# ========================
# 🧠 Parser (mit Datum-Fix)
# ========================
def parse_entries(text):
    entries = []
    current_date = None

    lines = text.split("\n")

    for line in lines:
        line = line.strip()

        if not line:
            continue

        date_match = re.search(r"\d{2}\.\d{2}\.\d{4}", line)

        if date_match:
            try:
                current_date = datetime.strptime(date_match.group(), "%d.%m.%Y")
            except:
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


# ========================
# 🪟 Auswahlfenster (NEU!)
# ========================
def choose_da_entry(entries):
    selected = {"value": None}

    def select(event=None):
        if not listbox.curselection():
            return
        selected["value"] = da_entries[listbox.curselection()[0]]
        win.destroy()

    win = tk.Toplevel()
    win.title("Diagnose auswählen")
    win.geometry("1000x500")

    label = tk.Label(
        win,
        text="Welche Diagnose wollen Sie abrechnen?",
        font=("Arial", 12, "bold")
    )
    label.pack(pady=10)

    listbox = tk.Listbox(win, width=150, height=20)

    # 🔥 nur "da"
    da_entries = [e for e in entries if e["type"].startswith("da")]

    for e in da_entries:
        line = f"{e['date'].date()} | {e['content']}"
        listbox.insert(tk.END, line)

    listbox.pack(fill="both", expand=True, padx=10)
    listbox.bind("<Double-Button-1>", select)

    btn = tk.Button(win, text="Auswählen", command=select)
    btn.pack(pady=10)

    win.mainloop()
    return selected["value"]


# ========================
# 🚀 Hauptfunktion
# ========================
def run():
    try:
        with open(CONFIG_FILE) as f:
            region = tuple(json.load(f))
    except:
        return

    img = pyautogui.screenshot(region=region)

    # ✂️ nur linke Spalten
    width, height = img.size
    img = img.crop((0, 0, int(width * 0.65), height))

    # 🧪 Bild verbessern
    img_np = np.array(img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    text = pytesseract.image_to_string(thresh)

    entries = parse_entries(text)

    if not entries:
        return

    entries.sort(key=lambda x: x["date"], reverse=True)

    selected = choose_da_entry(entries)

    if selected:
        print("Gewählt:", selected)


# ========================
# 🎯 Hotkey Fix
# ========================
def trigger_run():
    global run_requested
    run_requested = True


def start_hotkeys():
    keyboard.add_hotkey("F11", trigger_run)
    keyboard.wait()


threading.Thread(target=start_hotkeys, daemon=True).start()


# ========================
# 🔄 GUI Loop
# ========================
def check_run():
    global run_requested
    if run_requested:
        run_requested = False
        run()
    app.after(100, check_run)


# ========================
# 🪟 Hauptfenster
# ========================
app = tk.Tk()
app.title("Medical OCR Tool")
app.geometry("300x160")

label = tk.Label(app, text="Medical OCR Tool", font=("Arial", 12))
label.pack(pady=10)

status_var = tk.StringVar()
status_var.set("Kein Bereich definiert")

btn = tk.Button(app, text="Bereich definieren", command=lambda: calibrate(status_var))
btn.pack(pady=10)

status_label = tk.Label(app, textvariable=status_var)
status_label.pack(pady=5)

info = tk.Label(app, text="F11 = Diagnosen auswählen")
info.pack(pady=5)

check_run()

app.mainloop()