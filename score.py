"""
score.py - Analog-Score (0.0 bis 1.0) für Mars-/Mond-ähnliche Orte auf der Erde.

Idee:
  1. Für jedes Merkmal (Trockenheit, Vegetation, ...) wird der Erdwert mit dem
     Zielwert des Planeten verglichen  ->  Teilscore zwischen 0 und 1.
  2. Alle Teilscores werden gewichtet zu einem Lokalscore zusammengefasst.

Alle Funktionen arbeiten mit numpy. Dadurch funktionieren sie nicht nur mit
einzelnen Zahlen, sondern auch direkt mit ganzen 2D-Rastern (lat x lon) –
genau das, was ihr später für die Heatmap braucht. Keine for-Schleife über
Pixel nötig.

Fehlende Daten werden als NaN (np.nan) übergeben und beim Gesamtscore
automatisch ignoriert (die übrigen Gewichte werden hochskaliert).
"""

import numpy as np


# ---------------------------------------------------------------------------
# 1. Bausteine: so wird aus (Erdwert, Zielwert) ein Teilscore
# ---------------------------------------------------------------------------

def score_gauss(wert, ziel, toleranz):
    """Glockenkurve: 1.0 genau am Zielwert, fällt nach beiden Seiten ab.

    Für Merkmale, bei denen 'zu viel' und 'zu wenig' beides schlecht ist
    (z. B. Hangneigung). Bei Abstand = 1x toleranz ist der Score ~0.61,
    bei 2x toleranz ~0.14, bei 3x toleranz ~0.01.
    """
    wert = np.asarray(wert, dtype=float)
    return np.exp(-0.5 * ((wert - ziel) / toleranz) ** 2)


def score_weniger_ist_besser(wert, gut, schlecht):
    """1.0 wenn wert <= gut, 0.0 wenn wert >= schlecht, linear dazwischen.

    Für Merkmale, bei denen der Planet praktisch bei 'null' liegt
    (z. B. Vegetation, Niederschlag, Abstand zum nächsten Krater).
    """
    wert = np.asarray(wert, dtype=float)
    return np.clip((schlecht - wert) / (schlecht - gut), 0.0, 1.0)


def score_mehr_ist_besser(wert, schlecht, gut):
    """0.0 wenn wert <= schlecht, 1.0 wenn wert >= gut, linear dazwischen."""
    wert = np.asarray(wert, dtype=float)
    return np.clip((wert - schlecht) / (gut - schlecht), 0.0, 1.0)


def score_zusammensetzung(erde, ziel, toleranz):
    """Vergleicht zwei Zusammensetzungen (z. B. Oxid-Anteile in %).

    Berechnet den euklidischen Abstand der beiden Vektoren (in Prozentpunkten)
    und steckt ihn in die Glockenkurve. Die letzte Achse von `erde` sind die
    Bestandteile, d. h. für ein Raster hat `erde` die Form (lat, lon, n).
    """
    erde = np.asarray(erde, dtype=float)
    ziel = np.asarray(ziel, dtype=float)
    abstand = np.linalg.norm(erde - ziel, axis=-1)
    return np.exp(-0.5 * (abstand / toleranz) ** 2)


# ---------------------------------------------------------------------------
# 2. Konfiguration: Zielwerte pro Planet
# ---------------------------------------------------------------------------
# !!! Alle Zahlen sind PLATZHALTER / grobe Richtwerte zum Testen. !!!
# Bitte im Team mit echten Quellen (Paper, NASA-Datensätze) belegen.
#
# Reihenfolge der Bodenoxide: [SiO2, Al2O3, FeO, MgO, CaO, Rest]  (Gew.-%)

OXIDE = ["SiO2", "Al2O3", "FeO", "MgO", "CaO", "Rest"]

ZIELE = {
    "mars": {
        # Aridity Index = Niederschlag / potenzielle Verdunstung (<0.05 = hyperarid)
        "trockenheit": {"typ": "weniger", "gut": 0.03, "schlecht": 0.5, "gewicht": 2.0},
        # NDVI (Vegetationsindex): < 0.1 = praktisch kahl
        "vegetation":  {"typ": "weniger", "gut": 0.05, "schlecht": 0.3, "gewicht": 2.0},
        # mittlere Einstrahlung in kWh/m²/Tag (Proxy: wenig Wolken, dünne Luft)
        "sonne":       {"typ": "mehr", "schlecht": 3.0, "gut": 7.0, "gewicht": 0.5},
        # mittlere Hangneigung in Grad
        "hangneigung": {"typ": "gauss", "ziel": 5.0, "toleranz": 5.0, "gewicht": 1.0},
        # Rauheit, z. B. Terrain Ruggedness Index (TRI) in Metern
        "rauheit":     {"typ": "gauss", "ziel": 15.0, "toleranz": 15.0, "gewicht": 0.5},
        # Abstand zur nächsten Impaktstruktur in km
        "krater":      {"typ": "weniger", "gut": 0.0, "schlecht": 50.0, "gewicht": 1.0,
                        "minimum": 0.4},
        # Boden: basaltisch, eisenreich
        "boden":       {"typ": "zusammensetzung",
                        "ziel": [46, 10, 17, 8, 7, 12], "toleranz": 12.0, "gewicht": 1.5},
    },
    "mond": {
        "trockenheit": {"typ": "weniger", "gut": 0.03, "schlecht": 0.5, "gewicht": 2.0},
        "vegetation":  {"typ": "weniger", "gut": 0.05, "schlecht": 0.3, "gewicht": 2.0},
        "sonne":       {"typ": "mehr", "schlecht": 3.0, "gut": 7.0, "gewicht": 0.5},
        "hangneigung": {"typ": "gauss", "ziel": 8.0, "toleranz": 6.0, "gewicht": 1.0},
        "rauheit":     {"typ": "gauss", "ziel": 20.0, "toleranz": 15.0, "gewicht": 0.5},
        # Mond ist viel stärker verkratert -> Krater wichtiger
        "krater":      {"typ": "weniger", "gut": 0.0, "schlecht": 50.0, "gewicht": 2.0,
                        "minimum": 0.3},
        # Boden: Hochland-Anorthosit, sehr Al- und Ca-reich
        "boden":       {"typ": "zusammensetzung",
                        "ziel": [45, 25, 6, 7, 15, 2], "toleranz": 12.0, "gewicht": 1.5},
    },
}


# ---------------------------------------------------------------------------
# 3. Teilscore für ein Merkmal anhand der Konfiguration
# ---------------------------------------------------------------------------

def teilscore(wert, regel):
    """Wählt anhand von regel['typ'] die passende Bausteinfunktion.

    Optional regel['minimum']: Untergrenze für den Teilscore. Sinnvoll für
    'Bonus-Merkmale' wie Krater, die auf der Erde fast nirgends vorkommen –
    ihr Fehlen soll den Gesamtscore senken, aber nicht auf 0 drücken.
    """
    typ = regel["typ"]
    if typ == "gauss":
        s = score_gauss(wert, regel["ziel"], regel["toleranz"])
    elif typ == "weniger":
        s = score_weniger_ist_besser(wert, regel["gut"], regel["schlecht"])
    elif typ == "mehr":
        s = score_mehr_ist_besser(wert, regel["schlecht"], regel["gut"])
    elif typ == "zusammensetzung":
        s = score_zusammensetzung(wert, regel["ziel"], regel["toleranz"])
    else:
        raise ValueError(f"Unbekannter Regel-Typ: {typ}")
    # np.fmax statt np.maximum, damit NaN (fehlende Daten) NaN bleibt
    return np.where(np.isnan(s), np.nan, np.fmax(s, regel.get("minimum", 0.0)))


# ---------------------------------------------------------------------------
# 4. Teilscores zum Lokalscore zusammensetzen
# ---------------------------------------------------------------------------

def gesamtscore(teilscores, gewichte, methode="geometrisch", abdeckung_strafe=1.0):
    """Fasst Teilscores (dict name -> Wert/Array) gewichtet zusammen.

    Rückgabe: (score, abdeckung)
      abdeckung = Anteil der Gewichte, für die Daten vorhanden sind (0..1).
      Der Score wird mit abdeckung ** abdeckung_strafe multipliziert, damit ein
      Ort mit nur 2 bekannten Merkmalen nicht künstlich 1.0 erreicht.
      abdeckung_strafe=0 schaltet die Strafe aus, 1 = linear, 2 = streng.

    methode="arithmetisch": normaler gewichteter Mittelwert.
        Ein grüner Regenwald mit Krater und Basalt kann trotzdem ~0.5 erreichen.
    methode="geometrisch": gewichtetes geometrisches Mittel (empfohlen).
        Ist EIN wichtiges Merkmal ~0, zieht es den ganzen Score Richtung 0.
        Das passt besser zu 'ein Analog muss in allem halbwegs passen'.

    NaN-Teilscores (fehlende Daten) werden ignoriert.
    """
    namen = list(teilscores)
    # broadcast_arrays: ein komplett fehlendes Merkmal (einzelnes NaN) wird
    # automatisch auf Rastergröße gebracht
    arrays = np.broadcast_arrays(*[np.asarray(teilscores[n], dtype=float) for n in namen])
    s = np.stack(arrays)
    w = np.array([gewichte[n] for n in namen], dtype=float)
    w = w.reshape((-1,) + (1,) * (s.ndim - 1))      # Gewichte passend zum Raster formen

    vorhanden = ~np.isnan(s)
    w_eff = np.where(vorhanden, w, 0.0)              # fehlende Daten -> Gewicht 0
    w_summe = w_eff.sum(axis=0)
    abdeckung = w_summe / w.sum()

    with np.errstate(invalid="ignore", divide="ignore"):
        if methode == "arithmetisch":
            ergebnis = np.nansum(w_eff * s, axis=0) / w_summe
        elif methode == "geometrisch":
            log_s = np.log(np.maximum(np.nan_to_num(s, nan=1.0), 1e-6))
            ergebnis = np.exp((w_eff * log_s).sum(axis=0) / w_summe)
        else:
            raise ValueError(f"Unbekannte Methode: {methode}")

    ergebnis = ergebnis * abdeckung ** abdeckung_strafe
    ergebnis = np.where(w_summe > 0, ergebnis, np.nan)   # gar keine Daten -> NaN
    return ergebnis, abdeckung


def lokalscore(erdwerte, planet="mars", methode="geometrisch", abdeckung_strafe=1.0):
    """Hauptfunktion: Erdwerte (dict) -> (Lokalscore, Teilscores, Abdeckung).

    Merkmale, die in `erdwerte` fehlen, zählen als fehlende Daten (NaN)
    und senken über die Abdeckung den Score.
    """
    regeln = ZIELE[planet]
    teile = {name: teilscore(erdwerte.get(name, np.nan), regel)
             for name, regel in regeln.items()}
    gewichte = {name: regel["gewicht"] for name, regel in regeln.items()}
    score, abdeckung = gesamtscore(teile, gewichte, methode, abdeckung_strafe)
    return score, teile, abdeckung


# ---------------------------------------------------------------------------
# 5. Kleiner Test mit Beispielorten
# ---------------------------------------------------------------------------
# Die Werte sind GESCHÄTZTE Beispielwerte zum Testen der Logik, keine Messdaten.

BEISPIELE = {
    "Atacama (Chile)": {
        "trockenheit": 0.01, "vegetation": 0.05, "sonne": 7.5,
        "hangneigung": 4.0, "rauheit": 12.0, "krater": 300.0,
        "boden": [60, 15, 6, 3, 5, 11],
    },
    "Lavafeld (Island)": {
        "trockenheit": 1.2, "vegetation": 0.15, "sonne": 2.5,
        "hangneigung": 6.0, "rauheit": 25.0, "krater": 2000.0,
        "boden": [49, 15, 11, 7, 10, 8],
    },
    "Meteor Crater (Arizona)": {
        "trockenheit": 0.15, "vegetation": 0.12, "sonne": 6.0,
        "hangneigung": 7.0, "rauheit": 20.0, "krater": 0.0,
        "boden": [65, 10, 3, 2, 8, 12],
    },
    "Amazonas (Brasilien)": {
        "trockenheit": 1.8, "vegetation": 0.85, "sonne": 4.5,
        "hangneigung": 2.0, "rauheit": 5.0, "krater": 800.0,
        "boden": [55, 25, 8, 1, 1, 10],
    },
    "Ort mit fehlenden Daten": {
        "trockenheit": 0.02, "vegetation": np.nan, "sonne": 7.0,
    },
}


if __name__ == "__main__":
    for planet in ("mars", "mond"):
        print(f"\n===== Zielplanet: {planet.upper()} =====")
        for ort, werte in BEISPIELE.items():
            geo, teile, abd = lokalscore(werte, planet, "geometrisch")
            ari, _, _ = lokalscore(werte, planet, "arithmetisch")
            details = "  ".join(f"{k}={float(v):.2f}" for k, v in teile.items())
            print(f"{ort:26s} geo={float(geo):.2f}  arith={float(ari):.2f}  "
                  f"abdeckung={float(abd):.2f}   | {details}")

    # Raster-Test: dieselben Funktionen auf einem 3x4-Gitter (wie später die Heatmap)
    rng = np.random.default_rng(0)
    raster = {
        "trockenheit": rng.uniform(0, 1, (3, 4)),
        "vegetation":  rng.uniform(0, 0.8, (3, 4)),
        "boden":       rng.uniform(0, 30, (3, 4, len(OXIDE))),
    }
    # ein Pixel ohne Vegetationsdaten, um die Abdeckung im Raster zu prüfen
    raster["vegetation"][0, 1] = np.nan
    karte, _, abdeckung = lokalscore(raster, "mars", abdeckung_strafe=0)
    print("\nRaster-Test ohne Strafe (Form", karte.shape, "):\n", np.round(karte, 2))
    print("Abdeckung pro Pixel:\n", np.round(abdeckung, 2))
