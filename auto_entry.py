import pyautogui
import time

from ocr import load_inputline_pos


def enter_codes_in_medical_office(codes):
    """Traegt GOAe-Ziffern automatisch in Medical Office ein.

    1. Klickt auf die Eingabezeile (kalibrierte Position)
    2. Fuer jede Ziffer: "gz" + Enter + Ziffer + Enter

    Args:
        codes: Liste von GOAe-Ziffer-Strings, z.B. ["1", "3", "250"]
    """
    if not codes:
        return

    inputline_pos = load_inputline_pos()

    # Kurz warten damit Medical Office in den Vordergrund kommt
    time.sleep(0.5)

    # Auf Eingabezeile klicken um Fokus zu setzen
    if inputline_pos:
        pyautogui.click(inputline_pos[0], inputline_pos[1])
        time.sleep(0.2)

    for code in codes:
        # "gz" in die Eingabezeile tippen (Kuerzel fuer Gebuehrenziffer)
        pyautogui.typewrite('gz', interval=0.05)
        time.sleep(0.1)

        # Enter oeffnet den GZ-Dialog
        pyautogui.press('enter')
        time.sleep(0.3)

        # Ziffer eintippen
        pyautogui.typewrite(str(code), interval=0.02)
        time.sleep(0.1)

        # Enter bestaetigt die Ziffer und traegt sie auf den Schein
        pyautogui.press('enter')
        time.sleep(0.3)
