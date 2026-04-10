import tkinter as tk
from tkinter import ttk
from ocr import save_region, save_inputline_pos, save_patient_region
from goae_db import validate_codes, get_code_fee, get_total_fees


def _run_overlay_selection(on_done):
    """Zeigt ein transparentes Fullscreen-Overlay fuer Mausauswahl."""
    coords = {"x1": None, "y1": None, "x2": None, "y2": None}

    def on_mouse_down(event):
        coords["x1"], coords["y1"] = event.x_root, event.y_root
        canvas.delete("rect")

    def on_mouse_move(event):
        if coords["x1"] is None:
            return
        canvas.delete("rect")
        # Bildschirmkoordinaten in Canvas-Koordinaten umrechnen
        cx1 = coords["x1"] - root.winfo_rootx()
        cy1 = coords["y1"] - root.winfo_rooty()
        cx2 = event.x_root - root.winfo_rootx()
        cy2 = event.y_root - root.winfo_rooty()
        canvas.create_rectangle(
            cx1, cy1, cx2, cy2,
            outline="red", width=2, tag="rect"
        )

    def on_mouse_up(event):
        coords["x2"], coords["y2"] = event.x_root, event.y_root
        root.destroy()

    root = tk.Toplevel()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.3)
    root.attributes("-topmost", True)
    root.configure(bg="black")
    root.lift()
    root.focus_force()

    canvas = tk.Canvas(root, cursor="cross", bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)

    # ESC zum Abbrechen
    root.bind("<Escape>", lambda e: root.destroy())

    root.wait_window()

    if None in coords.values():
        return
    on_done(coords)


def calibrate_ocr_region(status_var):
    """Kalibriert den OCR-Bereich (Krankenblatt in Medical Office)."""
    def done(coords):
        x1, y1, x2, y2 = coords["x1"], coords["y1"], coords["x2"], coords["y2"]
        left, top = min(x1, x2), min(y1, y2)
        width = max(x1, x2) - left
        height = max(y1, y2) - top
        if width < 10 or height < 10:
            return
        save_region((left, top, width, height))
        status_var.set("OCR-Bereich gesetzt")

    _run_overlay_selection(done)


def calibrate_patient_region(status_var):
    """Kalibriert den OCR-Bereich fuer Patientendaten (Kopfzeile)."""
    def done(coords):
        x1, y1, x2, y2 = coords["x1"], coords["y1"], coords["x2"], coords["y2"]
        left, top = min(x1, x2), min(y1, y2)
        width = max(x1, x2) - left
        height = max(y1, y2) - top
        if width < 10 or height < 10:
            return
        save_patient_region((left, top, width, height))
        status_var.set("Patientenbereich gesetzt")

    _run_overlay_selection(done)


def calibrate_inputline(status_var):
    """Kalibriert die Position der Eingabezeile in Medical Office."""
    pos = {"x": None, "y": None}

    def on_click(event):
        pos["x"], pos["y"] = event.x_root, event.y_root
        root.destroy()

    root = tk.Toplevel()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.3)
    root.attributes("-topmost", True)
    root.configure(bg="black")
    root.lift()
    root.focus_force()

    # Canvas als Klickflaeche ueber den gesamten Bildschirm
    canvas = tk.Canvas(root, cursor="crosshair", bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # Label AUF dem Canvas (nicht darunter)
    canvas.create_text(
        root.winfo_screenwidth() // 2, root.winfo_screenheight() // 2,
        text="Klicken Sie auf die Eingabezeile in Medical Office",
        font=("Arial", 20, "bold"), fill="white"
    )

    # Gesamter Canvas ist klickbar
    canvas.bind("<ButtonPress-1>", on_click)

    # ESC zum Abbrechen
    root.bind("<Escape>", lambda e: root.destroy())

    root.wait_window()

    if pos["x"] is not None:
        save_inputline_pos((pos["x"], pos["y"]))
        status_var.set("Eingabezeile gesetzt")


def choose_diagnosis(entries):
    """Zeigt erkannte Diagnosen zur Auswahl."""
    selected = {"value": None}

    def select(event=None):
        if not listbox.curselection():
            return
        selected["value"] = entries[listbox.curselection()[0]]
        win.destroy()

    win = tk.Toplevel()
    win.title("Diagnose auswaehlen")
    win.geometry("1000x500")
    win.grab_set()
    win.focus_force()

    header = tk.Frame(win, bg="#2196F3", height=50)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(
        header,
        text="  Welche Diagnose soll abgerechnet werden?",
        font=("Arial", 13, "bold"), fg="white", bg="#2196F3", anchor="w"
    ).pack(fill="both", expand=True, padx=10)

    listbox = tk.Listbox(win, width=150, height=20, font=("Consolas", 11), selectmode="single")

    for e in entries:
        line = f"  {e['date'].strftime('%d.%m.%Y')}   |   {e['content']}"
        listbox.insert(tk.END, line)

    if entries:
        listbox.selection_set(0)

    listbox.pack(fill="both", expand=True, padx=10, pady=(10, 5))
    listbox.bind("<Double-Button-1>", select)
    listbox.bind("<Return>", select)

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=10)
    tk.Button(
        btn_frame, text="Auswaehlen", command=select,
        font=("Arial", 11, "bold"), bg="#2196F3", fg="white", padx=30, pady=5
    ).pack()

    win.wait_window()
    return selected["value"]


def choose_goae_codes(matched_codes, matched_label, diagnosis_text,
                      goae_data, patient_info=None):
    """Zeigt GOAe-Ziffern mit Live-Validierung, Ausschlusspruefung und Gebuehrenvorschau.

    - Alle Ziffern vorausgewaehlt
    - Ausschluesse werden live ausgegraut mit Warnung
    - Alters-/Geschlechtsprobleme werden rot markiert
    - Gebuehrensumme wird unten angezeigt
    """
    result = {"codes": []}
    rules = goae_data.get("rules", {})

    win = tk.Toplevel()
    win.title("GOAe-Ziffern - Auswahl")
    win.geometry("950x700")
    win.grab_set()
    win.focus_force()

    # --- Header ---
    header = tk.Frame(win, bg="#2196F3", height=60)
    header.pack(fill="x")
    header.pack_propagate(False)

    header_text = f"  Diagnose: {diagnosis_text}"
    if matched_label:
        header_text += f"  ({matched_label})"
    tk.Label(
        header, text=header_text,
        font=("Arial", 12, "bold"), fg="white", bg="#2196F3",
        anchor="w", wraplength=900
    ).pack(fill="both", expand=True, padx=10)

    # --- Patienteninfo-Leiste ---
    if patient_info and (patient_info.get("age") is not None or patient_info.get("gender")):
        pat_frame = tk.Frame(win, bg="#E3F2FD")
        pat_frame.pack(fill="x")
        parts = []
        if patient_info.get("age") is not None:
            parts.append(f"Alter: {patient_info['age']} Jahre")
        if patient_info.get("gender"):
            g = "maennlich" if patient_info["gender"] == "m" else "weiblich"
            parts.append(f"Geschlecht: {g}")
        tk.Label(
            pat_frame, text="  Patient: " + "  |  ".join(parts),
            font=("Arial", 10), bg="#E3F2FD", fg="#1565C0", pady=4
        ).pack(anchor="w", padx=10)

    # --- Info + Zaehler ---
    count_var = tk.StringVar()
    fee_var = tk.StringVar()

    info_frame = tk.Frame(win)
    info_frame.pack(fill="x", padx=10, pady=(8, 3))
    tk.Label(
        info_frame,
        text="Unpassende abwaehlen - Ausschluss-Konflikte werden automatisch erkannt:",
        font=("Arial", 10), fg="#666"
    ).pack(side="left")
    tk.Label(
        info_frame, textvariable=count_var,
        font=("Arial", 10, "bold"), fg="#2196F3"
    ).pack(side="right")

    # --- Scrollbarer Bereich ---
    container = tk.Frame(win)
    container.pack(fill="both", expand=True, padx=10)

    canvas = tk.Canvas(container, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable = tk.Frame(canvas)

    scrollable.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # --- Checkboxen mit Validierung ---
    checkboxes = {}
    warning_labels = {}
    row_frames = {}
    code_labels = {}
    fee_labels = {}

    sorted_codes = sorted(
        matched_codes.items(),
        key=lambda x: int(x[0]) if x[0].isdigit() else 99999
    )

    for code, description in sorted_codes:
        # Vorpruefung: blockierende Alters-/Geschlechtsprobleme
        code_rules = rules.get(code, {})
        blocked = False
        block_reason = ""

        if patient_info:
            age = patient_info.get("age")
            gender = patient_info.get("gender")
            age_min = code_rules.get("age_min")
            age_max = code_rules.get("age_max")
            req_gender = code_rules.get("gender")

            if age is not None and age_min is not None and age < age_min:
                blocked = True
                block_reason = f"Erst ab {age_min} Jahren (Patient: {age})"
            if age is not None and age_max is not None and age > age_max:
                blocked = True
                block_reason = f"Nur bis {age_max} Jahre (Patient: {age})"
            if req_gender and gender and gender != req_gender:
                blocked = True
                gl = "Frauen" if req_gender == "w" else "Maenner"
                block_reason = f"Nur fuer {gl}"

        var = tk.BooleanVar(value=not blocked)

        row = tk.Frame(scrollable)
        row.pack(fill="x", padx=5, pady=1)
        row_frames[code] = row

        cb = tk.Checkbutton(row, variable=var, anchor="w")
        cb.pack(side="left")

        code_lbl = tk.Label(
            row, text=f"{code}", font=("Arial", 10, "bold"),
            width=6, anchor="e"
        )
        code_lbl.pack(side="left")
        code_labels[code] = code_lbl

        desc_lbl = tk.Label(
            row, text=f"  {description}", font=("Arial", 10), anchor="w"
        )
        desc_lbl.pack(side="left")

        # Gebuehr rechts anzeigen
        fee = code_rules.get("fee_2_3", 0)
        fee_lbl = tk.Label(
            row, text=f"{fee:.2f} EUR" if fee > 0 else "",
            font=("Arial", 9), fg="#888", width=12, anchor="e"
        )
        fee_lbl.pack(side="right")
        fee_labels[code] = fee_lbl

        # Warnung-Label (erstmal leer)
        warn_lbl = tk.Label(
            row, text="", font=("Arial", 9, "italic"), fg="#D32F2F"
        )
        warn_lbl.pack(side="right", padx=(0, 10))
        warning_labels[code] = warn_lbl

        # Wenn durch Alter/Geschlecht blockiert: sofort markieren
        if blocked:
            var.set(False)
            cb.config(state="disabled")
            code_lbl.config(fg="#999")
            desc_lbl.config(fg="#999")
            warn_lbl.config(text=f"  {block_reason}")

        checkboxes[code] = var

    def update_validation(*args):
        """Live-Pruefung: Ausschluss-Konflikte erkennen und anzeigen."""
        selected = [code for code, var in checkboxes.items() if var.get()]
        warnings = validate_codes(selected, goae_data, patient_info)

        # Alle Warnungen zuruecksetzen die nicht durch Alter/Geschlecht blockiert sind
        for code, warn_lbl in warning_labels.items():
            code_rules_local = rules.get(code, {})
            is_permanently_blocked = False

            if patient_info:
                age = patient_info.get("age")
                gender = patient_info.get("gender")
                if age is not None and code_rules_local.get("age_max") is not None and age > code_rules_local["age_max"]:
                    is_permanently_blocked = True
                if age is not None and code_rules_local.get("age_min") is not None and age < code_rules_local["age_min"]:
                    is_permanently_blocked = True
                if code_rules_local.get("gender") and gender and gender != code_rules_local["gender"]:
                    is_permanently_blocked = True

            if is_permanently_blocked:
                continue

            code_warnings = warnings.get(code, [])
            exclusion_warnings = [w for w in code_warnings if w["type"] == "exclusion"]

            if exclusion_warnings:
                # Zeige den ersten Konflikt
                warn_lbl.config(
                    text=f"  {exclusion_warnings[0]['msg']}",
                    fg="#D32F2F"
                )
                code_labels[code].config(fg="#D32F2F")
            else:
                warn_lbl.config(text="")
                code_labels[code].config(fg="black")

        # Zaehler + Gebuehren aktualisieren
        n = len(selected)
        count_var.set(f"{n} von {len(checkboxes)} Ziffern")
        total = get_total_fees(selected, goae_data)
        fee_var.set(f"Gesamt: {total:.2f} EUR (2,3-fach)")

    # Trace auf alle Checkboxen setzen
    for var in checkboxes.values():
        var.trace_add("write", update_validation)

    update_validation()

    # --- Trennlinie ---
    ttk.Separator(win, orient="horizontal").pack(fill="x", padx=10, pady=(5, 0))

    # --- Gebuehren-Leiste ---
    fee_frame = tk.Frame(win, bg="#E8F5E9")
    fee_frame.pack(fill="x", padx=10, pady=(0, 0))
    tk.Label(
        fee_frame, textvariable=fee_var,
        font=("Arial", 12, "bold"), bg="#E8F5E9", fg="#2E7D32", pady=6
    ).pack(side="right", padx=10)

    # --- Buttons ---
    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=10)

    def select_all():
        for code, var in checkboxes.items():
            if str(checkboxes[code].cget("state") if hasattr(checkboxes[code], 'cget') else "") != "disabled":
                var.set(True)

    def deselect_all():
        for var in checkboxes.values():
            var.set(False)

    def confirm():
        selected = [code for code, var in checkboxes.items() if var.get()]
        # Letzte Warnung bei Konflikten
        warnings = validate_codes(selected, goae_data, patient_info)
        has_blocking = any(
            any(w["type"] == "exclusion" for w in code_warnings)
            for code_warnings in warnings.values()
        )
        if has_blocking:
            # Warndialog
            warn_win = tk.Toplevel(win)
            warn_win.title("Achtung - Ausschluss-Konflikte")
            warn_win.geometry("500x200")
            warn_win.grab_set()
            tk.Label(
                warn_win,
                text="Es gibt Ausschluss-Konflikte!\n\n"
                     "Einige der gewaehlten Ziffern duerfen nicht\n"
                     "zusammen abgerechnet werden (rot markiert).\n\n"
                     "Trotzdem uebernehmen?",
                font=("Arial", 11), justify="center"
            ).pack(pady=20)
            bf = tk.Frame(warn_win)
            bf.pack(pady=10)
            tk.Button(
                bf, text="Trotzdem uebernehmen", command=lambda: [warn_win.destroy(), _do_confirm()],
                bg="#FF9800", fg="white", font=("Arial", 10, "bold"), padx=15
            ).pack(side="left", padx=10)
            tk.Button(
                bf, text="Zurueck", command=warn_win.destroy,
                font=("Arial", 10), padx=15
            ).pack(side="left", padx=10)
        else:
            _do_confirm()

    def _do_confirm():
        result["codes"] = [code for code, var in checkboxes.items() if var.get()]
        win.destroy()

    def cancel():
        win.destroy()

    tk.Button(
        btn_frame, text="Alle an", command=select_all,
        font=("Arial", 9), padx=10
    ).pack(side="left", padx=5)

    tk.Button(
        btn_frame, text="Alle ab", command=deselect_all,
        font=("Arial", 9), padx=10
    ).pack(side="left", padx=5)

    tk.Button(
        btn_frame, text="  Uebernehmen  ", command=confirm,
        bg="#4CAF50", fg="white", font=("Arial", 12, "bold"),
        padx=25, pady=5, cursor="hand2"
    ).pack(side="left", padx=20)

    tk.Button(
        btn_frame, text="Abbrechen", command=cancel,
        font=("Arial", 9), padx=10
    ).pack(side="left", padx=5)

    win.wait_window()
    return result["codes"]


def show_status_popup(message, duration_ms=2000):
    """Zeigt kurz eine Statusmeldung an."""
    win = tk.Toplevel()
    win.overrideredirect(True)
    win.attributes("-topmost", True)

    tk.Label(
        win, text=f"  {message}  ",
        font=("Arial", 12, "bold"), bg="#4CAF50", fg="white",
        padx=20, pady=10
    ).pack()

    win.update_idletasks()
    screen_w = win.winfo_screenwidth()
    w = win.winfo_width()
    win.geometry(f"+{screen_w - w - 20}+20")

    win.after(duration_ms, win.destroy)
