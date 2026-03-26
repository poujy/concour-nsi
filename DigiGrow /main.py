import time
import threading
from datetime import date
import requests
from customtkinter import *

# ─────────────────────────────────────────────────────────────────────────────
#  Chargement des données distantes
# ─────────────────────────────────────────────────────────────────────────────


# Les trois fichiers de référence sont récupérés au démarrage depuis GitHub.
# .json() convertit directement la réponse HTTP en dictionnaire Python.
villes_data = requests.get(
    f"https://raw.githubusercontent.com/poujy/concour-nsi/refs/heads/main/DigiGrow%20/data/villes.json").json()
data = requests.get(f"https://raw.githubusercontent.com/poujy/concour-nsi/refs/heads/main/DigiGrow%20/data/stockage.json").json()

METEO_URL = (
    "http://api.weatherapi.com/v1/forecast.json"
    "?key=741a648e81bf44c28d7122536251410"
    "&q=Paris,France&days=14&aqi=no&alerts=no")
meteo_response = requests.get(METEO_URL)
# Code 200 = réponse OK. Si l'API est indisponible ou la clé invalide,

meteo = meteo_response.json() if meteo_response.status_code == 200 else None

if meteo is None:
    print("Erreur lors du téléchargement des données météo :", meteo_response.status_code)

# ─────────────────────────────────────────────────────────────────────────────
#  État de l'application (données en mémoire)
# ─────────────────────────────────────────────────────────────────────────────

# Jardin de l'utilisateur : liste de dicts, chacun représentant une plante ajoutée.
jardin = {"plantes": []}

# Compteur d'instances par espèce, pour numéroter les plantes
compteur_plantes = {}

# Ville choisie au démarrage, utilisée pour filtrer les plantes compatibles
ville_active = None



def get_saison(d: date) -> str:
    """Retourne la saison correspondant au mois de la date passée en paramètre."""
    mois = d.month
    if mois in (12, 1, 2):
        return "hiver"
    if mois in (3, 4, 5):
        return "printemps"
    if mois in (6, 7, 8):
        return "ete"
    return "automne"


def verif_climat_plante(nom_ville: str) -> list[str]:
    """Retourne la liste des plantes plantables dans la ville selon la saison actuelle."""
    # next(..., None) parcourt la liste et renvoie le premier élément qui correspond
    # ou None si aucun ne correspond
    ville = next((v for v in villes_data["villes"] if v["nom_ville"] == nom_ville), None)
    if ville is None:
        return []

    saison = get_saison(date.today())

    # On garde uniquement les plantes dont la saison courante est True et dont le climat est compatible avec celui de la ville sélectionnée
    plantes_dispo = [
        plante["nom_courant"]
        for plante in data["plantes"]
        if plante[saison] and correspond_climat(plante, ville)
    ]
    return plantes_dispo


def correspond_climat(plante: dict, ville: dict) -> bool:
    """Vérifie si le climat d'une plante est compatible avec celui de la ville."""
    types_climat = ("oceanique", "mediterraneen", "continental", "oceanique_altere", "montagnard")
    # any() s'arrête au premier True : la plante est compatible si elle partage au moins un type de climat avec la ville.
    return any(plante[c] == ville[c] for c in types_climat)


# ─────────────────────────────────────────────────────────────────────────────
#  Gestion du compteur et du jardin
# ─────────────────────────────────────────────────────────────────────────────

def compte(nom_plante: str) -> int:
    """Incrémente et retourne le numéro d'instance de l'espèce dans le jardin."""
    # .get() retourne 0 si la clé n'existe pas encore, puis on ajoute 1.
    compteur_plantes[nom_plante] = compteur_plantes.get(nom_plante, 0) + 1
    return compteur_plantes[nom_plante]


def ajouter_plante(nom_plante: str, nom_numerote: str) -> list:
    """Ajoute une entrée plante dans le jardin en mémoire."""
    jardin["plantes"].append({
        "nom_numéroté": nom_numerote,
        "nom_courant": nom_plante,
        "eau_deja_presente": 0,
    })
    return jardin["plantes"]


# ─────────────────────────────────────────────────────────────────────────────
#  Calcul de l'arrosage
# ─────────────────────────────────────────────────────────────────────────────

MULTIPLICATEURS_STADE = {
    "tout juste planté": 0.65,
    "maturité": 1.0,
    "floraison": 1.35,
}


def aroser(nom_numerote: str, stade: str) -> tuple[float | None, float | None]:
    """
    Calcule la quantité d'eau à apporter et met à jour le stock d'eau de la plante.
    Retourne (eau_a_apporter, eau_actuelle), ou (None, None) si les données sont manquantes.
    """
    if meteo is None:
        return None, None

    # rstrip("0123456789") retire les chiffres en fin de chaîne pour retrouver le nom d'espèce de base. Ex : "Rose2" → "Rose".
    nom_base = nom_numerote.rstrip("0123456789")
    plante = next((p for p in data["plantes"] if p["nom_courant"] == nom_base), None)
    if plante is None:
        return None, None

    instance = next((p for p in jardin["plantes"] if p["nom_numéroté"] == nom_numerote), None)
    if instance is None:
        return None, None

    # Paramètres propres à l'espèce
    eau = plante["eau"]
    dissipation_base = plante["dissipation"]
    ch_min, ch_max = plante["besoin_chaleur_min"], plante["besoin_chaleur_max"]
    sol_min, sol_max = plante["besoin_soleil_min"], plante["besoin_soleil_max"]
    ha_min, ha_max = plante["humidite_air_min"], plante["humidite_air_max"]

    # Relevé météo actuel
    # L'API ne fournit qu'une seule valeur d'humidité (air) ;
    # on l'utilise comme proxy pour l'humidité ambiante globale.
    humidite = meteo["current"]["humidity"]
    soleil = meteo["current"]["uv"]
    chaleur = meteo["current"]["temp_c"]

    stade_mul = MULTIPLICATEURS_STADE.get(stade, 1.0)

    # Pour chaque paramètre, on mesure l'écart entre la valeur idéale (centre de la plage optimale)
    # et la valeur réelle, normalisé par le demi-écart de la plage.
    # Un écart positif signifie que les conditions sont moins favorables → plus d'eau nécessaire.
    eau_a_apporter = eau * stade_mul * (
            ((ch_min + ch_max) / 2 - chaleur) / ((ch_max - ch_min) / 2) +
            ((sol_min + sol_max) / 2 - soleil) / ((sol_max - sol_min) / 2) +
            ((ha_min + ha_max) / 2 - humidite) / ((ha_max - ha_min) / 2)
    )

    # Plancher à 10 % de la dose de base : même dans des conditions idéales,
    # une plante a toujours besoin d'un apport minimum en eau.
    eau_a_apporter = max(eau_a_apporter, eau * 0.1)

    # La chaleur et le soleil accélèrent l'évaporation (facteur +),
    # l'humidité la ralentit (facteur -). Chaque terme est un multiplicateur autour de 1.0.
    dissipation = dissipation_base * (
            (1 + 0.020 * (chaleur - (ch_min + ch_max) / 2)) *
            (1 + 0.030 * (soleil - (sol_min + sol_max) / 2)) *
            (1 - 0.015 * (humidite - (ha_min + ha_max) / 2))
    )

    # On soustrait la fraction d'eau évaporée depuis le dernier passage.
    instance["eau_deja_presente"] -= instance["eau_deja_presente"] * dissipation

    # Si le stock tombe à 5 mL ou moins, on notifie l'utilisateur et on recharge.
    if instance["eau_deja_presente"] <= 5:
        notification(
            f"AROSER {nom_numerote}",
            f"Votre {nom_numerote} a besoin d'eau !\nQuantité recommandée : {eau_a_apporter:.0f} mL"
        )
        instance["eau_deja_presente"] = eau_a_apporter

    return eau_a_apporter, instance["eau_deja_presente"]


# ─────────────────────────────────────────────────────────────────────────────
#  Thread de surveillance par plante
# ─────────────────────────────────────────────────────────────────────────────

def boucle_plante(nom_numerote: str, stade: str) -> None:
    """Tourne en arrière-plan et recalcule l'arrosage toutes les heures."""
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
    Point d'entrée pour ajouter une plante : incrémente le compteur,
    enregistre la plante dans le jardin et démarre son thread de surveillance.
    Retourne le nom numéroté attribué à l'instance.
    """
    num = compte(nom_plante)
    nom_numerote = f"{nom_plante}{num}"

    ajouter_plante(nom_plante, nom_numerote)

    # daemon=True : le thread s'arrête automatiquement à la fermeture de la fenêtre.
    # Sans ça, Python attendrait que tous les threads aient terminé avant de quitter.
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

# Téléchargement et application de l icône de la fenêtre
try:
    ico_response = requests.get(
        "https://raw.githubusercontent.com/poujy/concour-nsi/refs/heads/main/DigiGrow%20/data/DigiGrow.ico"
    )
    if ico_response.status_code == 200:
        ico_path = "DigiGrow.ico"
        with open(ico_path, "wb") as f:
            f.write(ico_response.content)
        app.iconbitmap(ico_path)
except Exception as e:
    print("Impossible de charger l icône :", e)

noms_villes = [v["nom_ville"] for v in villes_data["villes"]]
main_frame = CTkFrame(master=app)
content_frame = CTkFrame(master=main_frame)

main_frame.pack(fill=BOTH, expand=True)
content_frame.pack(fill=BOTH, expand=True)


# ── Notification ─────────────────────────────────────────────────────────────

def notification(titre: str, texte: str) -> None:
    """Affiche une fenêtre modale de notification, compatible avec les threads."""

    def _afficher():
        fenetre = CTkToplevel(app)
        fenetre.title(titre)
        fenetre.geometry("300x150")
        # grab_set() bloque les interactions avec la fenêtre principale
        # tant que cette notification est ouverte.
        fenetre.grab_set()
        CTkLabel(fenetre, text=titre, font=("Arial", 16, "bold")).pack(pady=20)
        CTkLabel(fenetre, text=texte, font=("Arial", 13)).pack(pady=5)
        CTkButton(fenetre, text="OK", width=100, command=fenetre.destroy).pack(pady=15)

    # app.after(0, ...) planifie l'exécution dans le thread principal Tkinter.
    # Tkinter n'est pas thread-safe : créer un widget depuis un thread secondaire
    # provoquerait un crash — ce détour est donc obligatoire.
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
        # "global" permet de modifier la variable définie au niveau du module.
        # Sans ce mot-clé, Python créerait une variable locale qui disparaîtrait
        # dès la fin de la fonction.
        global ville_active
        ville_active = combobox.get()
        afficher_menu()
        afficher_page("Plants")

    CTkButton(content_frame, text="VALIDER", width=200, command=valider).pack(pady=20)


# ── Barre de navigation ───────────────────────────────────────────────────────

def afficher_menu() -> None:
    """Crée la barre de navigation en bas de l'écran (appelée une seule fois après le choix de ville)."""
    barre = CTkFrame(master=app, height=60)
    barre.pack(side=BOTTOM, fill=X)

    pages = [("📘", "Handbook"), ("🌱", "Plants"), ("📊", "Stats"), ("⚙️", "Settings")]
    for icone, page in pages:
        CTkButton(
            barre, text=icone, width=60, corner_radius=0,
            # "lambda p=page" capture la valeur de `page` au moment de la création.
            # Sans ça, toutes les lambdas pointeraient vers la dernière valeur de la boucle.
            command=lambda p=page: afficher_page(p)
        ).pack(side=LEFT, expand=True, fill=BOTH)


# ── Pages dynamiques ──────────────────────────────────────────────────────────

def vider_contenu() -> None:
    """Supprime tous les widgets du content_frame pour préparer l'affichage d'une nouvelle page."""
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
    CTkLabel(content_frame, text="Ajouter une plante", font=("Arial", 22, "bold")).pack(pady=20)

    plantes_dispo = verif_climat_plante(ville_active)
    valeurs_combo = plantes_dispo if plantes_dispo else ["Aucune plante disponible"]

    combo_plante = CTkComboBox(content_frame, values=valeurs_combo, state="readonly", width=220)
    combo_plante.pack(pady=5)
    combo_plante.set("Choisissez une plante...")

    combo_stade = CTkComboBox(
        content_frame,
        values=["tout juste planté", "maturité", "floraison"],
        state="readonly", width=220
    )
    combo_stade.pack(pady=5)
    combo_stade.set("tout juste planté")

    def ajouter():
        nom_choisi = combo_plante.get()
        stade_choisi = combo_stade.get()
        if nom_choisi not in ("Choisissez une plante...", "Aucune plante disponible"):
            portail_plante(nom_choisi, stade_choisi)
            afficher_page("Plants")

    CTkButton(content_frame, text="Ajouter Plante", width=200, command=ajouter).pack(pady=20)


def page_handbook() -> None:
    CTkLabel(content_frame, text="📘 Votre Jardin", font=("Arial", 22, "bold")).pack(pady=20)

    if jardin["plantes"]:
        for plante in jardin["plantes"]:
            CTkLabel(content_frame, text=f"🌱 {plante['nom_numéroté']}", font=("Arial", 14)).pack(pady=2)
    else:
        CTkLabel(content_frame, text="Aucune plante pour l'instant", font=("Arial", 13)).pack(pady=10)


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
