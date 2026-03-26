
import json
import time
import threading
from datetime import date
import requests
from customtkinter import *


# ─────────────────────────────────────────────────────────────────────────────
#  Chargement des données distantes
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://raw.githubusercontent.com/poujy/concour-nsi/refs/heads/main/troph%C3%A9e%20nsi"

# On charge les 3 fichiers JSON depuis GitHub au démarrage.
# .json() convertit directement la réponse HTTP en dictionnaire Python.
villes_data = requests.get(f"{BASE_URL}/villes.json").json()
data        = requests.get(f"{BASE_URL}/stockage(3).json").json()
compteur    = requests.get(f"{BASE_URL}/compteur.json").json()

METEO_URL = (
    "http://api.weatherapi.com/v1/forecast.json"
    "?key=741a648e81bf44c28d7122536251410"
    "&q=Paris,France&days=14&aqi=no&alerts=no"
)
meteo_response = requests.get(METEO_URL)
# Si l'API météo répond correctement (code 200 = OK), on parse le JSON.
# Sinon on stocke None pour pouvoir tester l'échec plus tard dans le code.
meteo = meteo_response.json() if meteo_response.status_code == 200 else None

if meteo is None:
    print("Erreur lors du téléchargement des données météo :", meteo_response.status_code)


# ─────────────────────────────────────────────────────────────────────────────
#  État de l'application
# ─────────────────────────────────────────────────────────────────────────────

jardin       = {"plantes": []}   # jardin de l'utilisateur courant
ville_active = None              # ville choisie au démarrage


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers — saison & climat
# ─────────────────────────────────────────────────────────────────────────────

def get_saison(d: date) -> str:
    """Retourne la saison correspondant au mois de la date donnée."""
    mois = d.month
    if mois in (12, 1, 2):
        return "hiver"
    if mois in (3, 4, 5):
        return "printemps"
    if mois in (6, 7, 8):
        return "ete"
    return "automne"


def verif_climat_plante(nom_ville: str) -> list[str]:
    """Retourne la liste des plantes plantables dans la ville selon la saison."""
    # next(..., None) parcourt la liste et renvoie le premier élément qui correspond,
    # ou None si aucun ne correspond — plus efficace qu'une boucle for/break.
    ville = next((v for v in villes_data["villes"] if v["nom_ville"] == nom_ville), None)
    if ville is None:
        return []

    saison = get_saison(date.today())

    # Compréhension de liste : on garde uniquement les plantes dont
    # le champ [saison] est True ET dont le climat correspond à la ville.
    plantes_dispo = [
        plante["nom_courant"]
        for plante in data["plantes"]
        if plante[saison] and correspond_climat(plante, ville)
    ]
    return plantes_dispo


def correspond_climat(plante: dict, ville: dict) -> bool:
    """Vérifie si le climat d'une plante correspond à celui de la ville."""
    types_climat = ("oceanique", "mediterraneen", "continental", "oceanique_altere", "montagnard")
    # any() renvoie True dès qu'une des conditions est vraie (s'arrête au premier match).
    # Ici : la plante est compatible si elle partage au moins un type de climat avec la ville.
    return any(plante[c] == ville[c] for c in types_climat)


# ─────────────────────────────────────────────────────────────────────────────
#  Gestion du compteur et du jardin
# ─────────────────────────────────────────────────────────────────────────────

def compte(nom_plante: str) -> int:
    cle = f"compteur_{nom_plante}"
    # On cherche le dictionnaire qui contient cette clé dans la liste compteur["compteur"].
    # La liste ressemble à : [{"compteur_Rose": 2}, {"compteur_Tulipe": 1}, ...]
    entree = next((c for c in compteur["compteur"] if cle in c), None)

    if entree is None:
        # Première fois qu'on plante cette espèce : on crée son entrée à 0.
        compteur["compteur"].append({cle: 0})
        entree = compteur["compteur"][-1]  # [-1] = dernier élément = celui qu'on vient d'ajouter

    entree[cle] += 1
    return entree[cle]


def ajouter_plante(nom_plante: str, nom_numerote: str) -> list:
    """Ajoute une plante dans le jardin en mémoire."""
    jardin["plantes"].append({
        "nom_numéroté":      nom_numerote,
        "nom_courant":       nom_plante,
        "eau_deja_presente": 0,
    })
    return jardin["plantes"]


# ─────────────────────────────────────────────────────────────────────────────
#  Calcul de l'arrosage
# ─────────────────────────────────────────────────────────────────────────────

MULTIPLICATEURS_STADE = {
    "tout juste planté": 0.65,
    "maturité":          1.0,
    "floraison":         1.35,
}


def aroser(nom_numerote: str, stade: str) -> tuple[float | None, float | None]:
    """
    Calcule la quantité d'eau à apporter et met à jour le stock d'eau de la plante.
    Retourne (eau_a_apporter, eau_actuelle) ou (None, None) en cas d'erreur.
    """
    if meteo is None:
        return None, None

    # rstrip("0123456789") supprime tous les chiffres en fin de chaîne.
    # Ex : "Rose2" → "Rose", pour retrouver la fiche dans le catalogue.
    nom_base = nom_numerote.rstrip("0123456789")
    plante   = next((p for p in data["plantes"] if p["nom_courant"] == nom_base), None)
    if plante is None:
        return None, None

    # Retrouver l'instance dans le jardin
    instance = next((p for p in jardin["plantes"] if p["nom_numéroté"] == nom_numerote), None)
    if instance is None:
        return None, None

    # Paramètres de la plante
    eau              = plante["eau"]
    dissipation_base = 3600 * plante["dissipation"]
    ch_min, ch_max   = plante["besoin_chaleur_min"],  plante["besoin_chaleur_max"]
    sol_min, sol_max = plante["besoin_soleil_min"],   plante["besoin_soleil_max"]
    hs_min, hs_max   = plante["humidite_sol_min"],    plante["humidite_sol_max"]
    ha_min, ha_max   = plante["humidite_air_min"],    plante["humidite_air_max"]

    # Conditions météo actuelles
    humidite_sol = meteo["current"]["humidity"]
    humidite_air = meteo["current"]["humidity"]
    soleil       = meteo["current"]["uv"]
    chaleur      = meteo["current"]["temp_c"]

    stade_mul = MULTIPLICATEURS_STADE.get(stade, 1.0)

    # Formule d'arrosage : pour chaque paramètre (chaleur, soleil, humidité sol et air),
    # on calcule l'écart entre la valeur idéale (milieu de la plage optimale) et la valeur réelle,
    # normalisé par le demi-écart de la plage. Un écart positif = conditions moins favorables = plus d'eau.
    # Les 4 termes sont additionnés, puis multipliés par la dose de base et le facteur de stade.
    eau_a_apporter = eau * stade_mul * (
        ((ch_min  + ch_max)  / 2 - chaleur)      / ((ch_max  - ch_min)  / 2) +
        ((sol_min + sol_max) / 2 - soleil)        / ((sol_max - sol_min) / 2) +
        ((hs_min  + hs_max)  / 2 - humidite_sol)  / ((hs_max  - hs_min)  / 2) +
        ((ha_min  + ha_max)  / 2 - humidite_air)  / ((ha_max  - ha_min)  / 2)
    )

    # Dissipation effective : la chaleur et le soleil accélèrent l'évaporation (facteur +),
    # l'humidité (sol et air) la ralentit (facteur -).
    # Chaque facteur est un multiplicateur autour de 1.0, appliqué à la dissipation de base.
    dissipation = dissipation_base * (
        (1 + 0.020 * (chaleur      - (ch_min  + ch_max)  / 2)) *
        (1 + 0.030 * (soleil       - (sol_min + sol_max) / 2)) *
        (1 - 0.015 * (humidite_air - (ha_min  + ha_max)  / 2)) *
        (1 - 0.010 * (humidite_sol - (hs_min  + hs_max)  / 2))
    )

    # On soustrait la fraction d'eau évaporée depuis le dernier passage
    instance["eau_deja_presente"] -= instance["eau_deja_presente"] * dissipation

    # Notification et remplissage si stock trop bas
    if instance["eau_deja_presente"] <= 5:
        notification(
            f"AROSER {nom_numerote}",
            f"Votre {nom_numerote} a besoin d'eau !"
        )
        instance["eau_deja_presente"] = eau_a_apporter

    return eau_a_apporter, instance["eau_deja_presente"]


# ─────────────────────────────────────────────────────────────────────────────
#  Thread de surveillance par plante
# ─────────────────────────────────────────────────────────────────────────────

def boucle_plante(nom_numerote: str, stade: str) -> None:
    """Tourne en arrière-plan et recalcule l'arrosage chaque heure."""
    while True:
        eau_a_apporter, eau_actuelle = aroser(nom_numerote, stade)
        if eau_a_apporter is not None:
            print(
                f"[{nom_numerote}] "
                f"eau à apporter : {eau_a_apporter:.2f} | "
                f"eau présente : {eau_actuelle:.2f}"
            )
        time.sleep(3600)


def portail_plante(nom_plante: str, stade: str) -> str:
    """
    Point d'entrée pour ajouter une plante :
    incrémente le compteur, ajoute au jardin, lance le thread de surveillance.
    Retourne le nom numéroté de la plante.
    """
    num = compte(nom_plante)
    nom_numerote = f"{nom_plante}{num}"

    ajouter_plante(nom_plante, nom_numerote)

    # daemon=True : le thread s'arrête automatiquement quand la fenêtre principale est fermée.
    # Sans ça, Python attendrait que tous les threads soient terminés avant de quitter.
    thread = threading.Thread(target=boucle_plante, args=(nom_numerote, stade), daemon=True)
    thread.start()

    return nom_numerote


# ─────────────────────────────────────────────────────────────────────────────
#  Interface graphique (CustomTkinter)
# ─────────────────────────────────────────────────────────────────────────────

app = CTk()
app.geometry("360x640")
app.title("DigiGrow")
set_appearance_mode("dark")

noms_villes   = [v["nom_ville"] for v in villes_data["villes"]]
main_frame    = CTkFrame(master=app)
content_frame = CTkFrame(master=main_frame)

main_frame.pack(fill=BOTH, expand=True)
content_frame.pack(fill=BOTH, expand=True)


# ── Notification ─────────────────────────────────────────────────────────────

def notification(titre: str, texte: str) -> None:
    """Affiche une fenêtre de notification (thread-safe via app.after)."""
    def _afficher():
        fenetre = CTkToplevel(app)
        fenetre.title(titre)
        fenetre.geometry("300x150")
        # grab_set() bloque les interactions avec la fenêtre principale
        # tant que cette notification est ouverte (comportement "modal").
        fenetre.grab_set()
        CTkLabel(fenetre, text=titre, font=("Arial", 16, "bold")).pack(pady=20)
        CTkLabel(fenetre, text=texte, font=("Arial", 13)).pack(pady=5)
        CTkButton(fenetre, text="OK", width=100, command=fenetre.destroy).pack(pady=15)

    # app.after(0, ...) planifie l'exécution de _afficher() dans le thread principal Tkinter.
    # C'est obligatoire car aroser() tourne dans un thread secondaire :
    # Tkinter n'est pas thread-safe et plante si on crée des widgets depuis un autre thread.
    app.after(0, _afficher)


# ── Page d'accueil ────────────────────────────────────────────────────────────

def afficher_home() -> None:
    vider_contenu()

    CTkLabel(content_frame, text="DigiGrow", font=("Arial", 28, "bold")).pack(pady=40)
    CTkLabel(content_frame, text="Sélectionnez votre ville", font=("Arial", 18)).pack(pady=10)

    combobox = CTkComboBox(content_frame, values=noms_villes, state="readonly", width=220)
    combobox.pack(pady=5)
    combobox.set(noms_villes[0])

    def valider():
        # "global" est nécessaire ici pour modifier la variable définie au niveau du module.
        # Sans ce mot-clé, Python créerait une variable locale qui disparaîtrait à la fin de la fonction.
        global ville_active
        ville_active = combobox.get()
        afficher_menu()
        afficher_page("Plants")

    CTkButton(content_frame, text="VALIDER", width=200, command=valider).pack(pady=20)


# ── Barre de navigation ───────────────────────────────────────────────────────

def afficher_menu() -> None:
    """Crée la barre de navigation en bas (appelée une seule fois)."""
    barre = CTkFrame(master=app, height=60)
    barre.pack(side=BOTTOM, fill=X)

    pages = [("📘", "Handbook"), ("🌱", "Plants"), ("📊", "Stats"), ("⚙️", "Settings")]
    for icone, page in pages:
        CTkButton(
            barre, text=icone, width=60, corner_radius=0,
            # "lambda p=page" capture la valeur actuelle de `page` dans la variable p.
            # Sans ça, toutes les lambdas partageraient la même référence à `page`
            # et pointeraient toutes vers la dernière valeur de la boucle.
            command=lambda p=page: afficher_page(p)
        ).pack(side=LEFT, expand=True, fill=BOTH)


# ── Pages dynamiques ──────────────────────────────────────────────────────────

def vider_contenu() -> None:
    # winfo_children() retourne la liste de tous les widgets enfants du frame.
    # On les détruit un par un pour "réinitialiser" l'affichage avant de charger une nouvelle page.
    for widget in content_frame.winfo_children():
        widget.destroy()


def afficher_page(nom: str) -> None:
    vider_contenu()

    if nom == "Plants":
        page_plants()
    elif nom == "Handbook":
        page_handbook()
    elif nom == "Stats":
        page_stats()
    elif nom == "Settings":
        page_settings()


def page_plants() -> None:
    CTkLabel(content_frame, text="Votre Jardin", font=("Arial", 22, "bold")).pack(pady=20)

    # Liste des plantes existantes
    if jardin["plantes"]:
        for plante in jardin["plantes"]:
            CTkLabel(content_frame, text=f"🌱 {plante['nom_numéroté']}", font=("Arial", 14)).pack(pady=2)
    else:
        CTkLabel(content_frame, text="Aucune plante pour l'instant", font=("Arial", 13)).pack(pady=10)

    CTkLabel(content_frame, text="Ajouter une plante", font=("Arial", 13)).pack(pady=(20, 5))

    # Sélection de la plante
    plantes_dispo = verif_climat_plante(ville_active)
    valeurs_combo = plantes_dispo if plantes_dispo else ["Aucune plante disponible"]

    combo_plante = CTkComboBox(content_frame, values=valeurs_combo, state="readonly", width=220)
    combo_plante.pack(pady=5)
    combo_plante.set("Choisissez une plante...")

    # Sélection du stade
    combo_stade = CTkComboBox(
        content_frame,
        values=["tout juste planté", "maturité", "floraison"],
        state="readonly", width=220
    )
    combo_stade.pack(pady=5)
    combo_stade.set("tout juste planté")

    def ajouter():
        nom_choisi   = combo_plante.get()
        stade_choisi = combo_stade.get()
        if nom_choisi not in ("Choisissez une plante...", "Aucune plante disponible"):
            portail_plante(nom_choisi, stade_choisi)
            afficher_page("Plants")

    CTkButton(content_frame, text="Ajouter Plante", width=200, command=ajouter).pack(pady=20)


def page_handbook() -> None:
    CTkLabel(content_frame, text="📘 Handbook", font=("Arial", 22, "bold")).pack(pady=20)
    CTkLabel(content_frame, text="(à venir)", font=("Arial", 14)).pack()


def page_stats() -> None:
    CTkLabel(content_frame, text="📊 Statistiques", font=("Arial", 22, "bold")).pack(pady=20)
    CTkLabel(content_frame, text=f"Plantes dans le jardin : {len(jardin['plantes'])}", font=("Arial", 14)).pack(pady=5)


def page_settings() -> None:
    CTkLabel(content_frame, text="⚙️ Paramètres", font=("Arial", 22, "bold")).pack(pady=20)
    CTkLabel(content_frame, text="(à venir)", font=("Arial", 14)).pack()


# ─────────────────────────────────────────────────────────────────────────────
#  Lancement
# ─────────────────────────────────────────────────────────────────────────────

afficher_home()
app.mainloop()
