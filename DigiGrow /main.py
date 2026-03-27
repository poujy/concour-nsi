import json
import os
import time
import threading
import math
from datetime import date
from typing import List, Tuple, Optional
import requests
from customtkinter import *

#  Chargement des fichiers JSON , d*la def recupere uniquement le nom du fichier et renvoie le fichier sans necessité de reecrire le chemin d'accées

villes_data = requests.get(
    f"https://raw.githubusercontent.com/poujy/concour-nsi/refs/heads/main/DigiGrow%20/data/villes.json").json()
catalogue = requests.get(f"https://raw.githubusercontent.com/poujy/concour-nsi/refs/heads/main/DigiGrow%20/data/stockage.json").json()

#  Appel de l'API météo (WeatherAPI)

METEO_URL = (
    "http://api.weatherapi.com/v1/forecast.json?key=741a648e81bf44c28d7122536251410&q=Paris,France&days=14&aqi=no&alerts=no")

_reponse_meteo = requests.get(METEO_URL)
meteo = _reponse_meteo.json() if _reponse_meteo.status_code == 200 else None

if meteo is None:
    print("Erreur météo :", _reponse_meteo.status_code)

#  Codes météo WeatherAPI convertit en texte afin que l'utilisateur puisse comprendre (mdr)

CODES_METEO = {1000: "Ensoleillé", 1003: "Partiellement nuageux", 1006: "Nuageux",
               1009: "Couvert", 1030: "Brumeux", 1063: "Pluie possible",
               1066: "Neige possible", 1069: "Grésil possible", 1072: "Bruine verglaçante possible",
               1087: "Orages possibles", 1114: "Tempête de neige", 1117: "Blizzard",
               1135: "Brouillard", 1147: "Brouillard givrant", 1150: "Bruine légère",
               1153: "Bruine fine", 1168: "Bruine verglaçante", 1171: "Bruine verglaçante forte",
               1180: "Pluie légère", 1183: "Pluie légère", 1186: "Pluie modérée",
               1189: "Pluie modérée", 1192: "Pluie forte", 1195: "Pluie forte",
               1198: "Pluie verglaçante", 1201: "Pluie verglaçante forte",
               1204: "Grésil léger", 1207: "Grésil fort", 1210: "Neige légère",
               1213: "Neige légère", 1216: "Neige modérée", 1219: "Neige modérée",
               1222: "Neige forte", 1225: "Neige forte", 1237: "Grêle",
               1240: "Averses légères", 1243: "Averses fortes", 1246: "Averses torrentielles",
               1249: "Averses de grésil", 1252: "Averses de grésil fort",
               1255: "Averses de neige", 1258: "Averses de neige forte",
               1261: "Averses de grêle", 1264: "Averses de grêle forte",
               1273: "Pluie et orages", 1276: "Pluie forte et orages",
               1279: "Neige et orages", 1282: "Neige forte et orages"}


def traduire_code_meteo(current: dict) -> str:
    code = current.get("condition", {}).get("code", None)
    if code is None:
        return "Inconnue"
    return CODES_METEO.get(code, f"Code {code}")


#  État global de l'application

jardin = {"plantes": []}  # plantes actives de l'utilisateur
compteur_instances = {}  # { "Rose": 2, "Carotte": 1, ... }
ville_active = None
nb_arrosages = 0  # arrosages d'urgence depuis le lancement

#  tout les conseils pour chaques plantes

CONSEILS = {
    "Carotte": "Semez en sol meuble et profond. Éclaircissez à 5 cm pour obtenir de belles racines. Arrosez régulièrement pour éviter les fourches.",
    "Pommedeterre": "Plantez les tubercules-graines en buttes et buttez régulièrement. Évitez l'excès d'humidité qui favorise la pourriture.",
    "Rose": "Taillez après chaque floraison. Arrosez toujours au pied pour prévenir l'oïdium. Un apport de compost au printemps garantit une belle floraison.",
    "Tulipe": "Plantez les bulbes en automne, pointe vers le haut. Laissez le feuillage sécher naturellement après floraison pour reconstituer les réserves.",
    "Courgette": "Plants gourmand en eau et en soleil. Récoltez jeune (15-20 cm) pour stimuler la production. Un seul pied suffit souvent pour une famille.",
    "Concombre": "Palissez les tiges pour économiser de l'espace. Maintenez une humidité constante du sol pour éviter l'amertume des fruits.",
    "Poivron": "Aime la chaleur. En climat tempéré, démarrez les plants en intérieur. Arrosez en profondeur plutôt que souvent.",
    "Aubergine": "Exige chaleur et plein soleil. Pincez les tiges pour favoriser la ramification. Attendez que la peau soit bien brillante avant de récolter.",
    "Haricot": "Ne semez pas avant que le sol soit bien réchauffé. Inutile de fertiliser : la plante fixe elle-même l'azote atmosphérique.",
    "Petits pois": "Semez tôt, ils supportent un léger gel. Palissez les tiges. Récoltez régulièrement pour prolonger la production.",
    "Salade": "Évitez la chaleur qui fait monter en graines. Arrosez le matin pour limiter les risques de maladies foliaires.",
    "Épinard": "Préfère les saisons fraîches. Monte vite en graines dès que les jours rallongent : choisissez des variétés à montaison lente.",
    "Chou": "Exige beaucoup d'eau et d'espace. Protégez des chenilles de la piéride avec un voile fin. Buttez le pied pour le stabiliser.",
    "Oignon": "Arrêtez l'arrosage quand les fanes tombent : c'est le signal de la récolte. Faites sécher les bulbes avant de les stocker.",
    "Ail": "Plantez les caïeux en automne, pointe vers le haut. Récoltez quand les fanes jaunissent. Tressez et suspendez pour la conservation.",
    "Poireau": "Transplantez en jabot pour blanchir le fût. Buttez progressivement en cours de culture pour un résultat optimal.",
    "Radis": "Culture ultra-rapide (3-4 semaines). Semez toutes les deux semaines pour étaler la récolte. Évitez les sols compactés.",
    "Betterave": "Semez par bouquets et éclaircissez à 10 cm. Les jeunes feuilles se cuisinent comme des épinards.",
    "Céleri": "Culture longue, très gourmande en eau. Buttez progressivement les tiges pour les blanchir si vous cultivez le céleri-branche.",
    "Tomate": "Ébourgeonnez et palissez régulièrement. Arrosez strictement à la base pour éviter les maladies foliaires. Attendez la pleine maturité sur pied.",
    "Menthe": "Plantez en pot ou posez une barrière dans le sol , sinon la plante vous envahiras ! Hyper robuste. couper les touffes tout les 2 ans.",
    "Basilic": "Pincez les fleurs pour prolonger la récolte de feuilles. Craint le froid et les courants d'air. Arrosez par le bas.",
    "Thym": "Très rustique et peu exigeant. Taille légère après floraison. Supporte bien les périodes de sécheresse une fois établi.",
    "Romarin": "Arbrisseau persistant résistant. Taille après floraison. Redoute l'excès d'eau en hiver, surtout en pot.",
    "Ciboulette": "Repousse bien après coupe. Divisez les touffes tous les 2-3 ans. Les fleurs mauves sont comestibles et décoratives.",
    "Persil": "Germination lente (3 semaines). Faites tremper les graines 24h avant le semis. Arrosez régulièrement.",
    "Origan": "Récoltez avant la pleine floraison pour un arôme maximal. Tolère bien la sécheresse estivale.",
    "Sauge": "Taillez après floraison pour éviter la lignification. Préfère un sol bien drainé. Propriétés digestives reconnues.",
    "Estragon": "Préférez l'estragon français pour sa saveur. Moins aromatique séché que frais : utilisez-le de préférence frais ou congelé.",
    "Coriandre": "Monte vite en graines par forte chaleur. Semez en successions. Les graines sèches sont une épice à part entière.",
    "Laurier": "Arbuste persistant très robuste. Taille de forme au printemps. Séchez les feuilles à l'ombre pour préserver les arômes.",
    "Aneth": "Ne pas planter près du fenouil (risque d'hybridation). Monte vite en graines. Récoltez feuilles et graines séparément.",
    "Cerfeuil": "Préfère la mi-ombre. Monte vite en graines par chaleur : privilégiez les semis précoces ou automnaux.",
    "Marjolaine": "Plus douce que l'origan. Séchez à l'ombre pour conserver les arômes. Préfère les sols calcaires bien drainés."}


def conseil_pour_plante(nom: str) -> str:
    return CONSEILS.get(nom,
                        f"Plantez votre {nom} dans un sol adapté à ses besoins en chaleur et en humidité. ""Consultez les indicateurs d'arrosage de l'application pour un suivi précis.")


#  la def vas renvoyer la saison actuel

def saison_du_jour(d: date) -> str:
    m = d.month
    if m in (12, 1, 2): return "hiver"
    if m in (3, 4, 5):  return "printemps"
    if m in (6, 7, 8):  return "ete"
    return "automne"


# ces defs vont comparer les climats dans la ville de l'utilisateur et le climats necessaire pour les plantes et renvoyer la liste de plante qui peuvent etre planté dans la zone

def plantes_compatibles_ville(nom_ville: str) -> List[str]:
    ville = next((v for v in villes_data["villes"] if v["nom_ville"] == nom_ville), None)
    if ville is None:
        return []
    saison = saison_du_jour(date.today())
    return [p["nom_courant"] for p in catalogue["plantes"] if p[saison] and _climat_compatible(p, ville)]


def _climat_compatible(plante: dict, ville: dict) -> bool:
    types = ("oceanique", "mediterraneen", "continental", "oceanique_altere", "montagnard")
    return any(plante[c] == ville[c] for c in types)


#  Gestion du jardin (compteur)

def incrémenter_compteur(nom_plante: str) -> int:
    compteur_instances[nom_plante] = compteur_instances.get(nom_plante, 0) + 1
    return compteur_instances[nom_plante]


# ajout de la plante dans le jardin de l'utilisateur

def inscrire_plante_au_jardin(nom_plante: str, nom_numerote: str, stade: str) -> list:
    jardin["plantes"].append(
        {"nom_numéroté": nom_numerote, "nom_courant": nom_plante, "stade": stade, "eau_deja_presente": 0.0, })
    return jardin["plantes"]


#  Calcul de l'arrosage et estimation du prochain

FACTEURS_STADE = {"tout juste planté": 0.65, "maturité": 1.0, "floraison": 1.35, }


def temps_avant_prochain_arrosage(instance: dict, plante: dict) -> str:
    """cette def vas faire une estimation du prochain arrosage grace a un calcul"""
    eau = instance["eau_deja_presente"]
    seuil = plante["eau"] * 0.10
    if eau <= seuil:
        return "Maintenant !"

    d = plante["dissipation"]
    if d <= 0 or d >= 1:
        return "?"
    try:
        n_secondes = math.log(seuil / eau) / math.log(1 - d)
        if n_secondes < 0:
            return "Maintenant !"
        n_heures = n_secondes / 3600
        if n_heures < 1:
            return "< 1h"
        if n_heures < 24:
            return f"Dans {int(n_heures)}h"
        return f"Dans {int(n_heures / 24)}j"
    except (ValueError, ZeroDivisionError):
        return "?"


def calculer_cycle_arrosage(nom_numerote: str) -> Tuple[Optional[float], Optional[float]]:
    """def appelé toute les heure qui vas a la fois calculer les besoins de la plante et l'eau qui se dissipe en fonction de la météo"""
    global nb_arrosages
    if meteo is None:
        return None, None
    nom_base = nom_numerote.rstrip("0123456789")
    plante = next((p for p in catalogue["plantes"] if p["nom_courant"] == nom_base), None)
    if plante is None:
        return None, None
    instance = next((p for p in jardin["plantes"] if p["nom_numéroté"] == nom_numerote), None)
    if instance is None:
        return None, None
    stade = instance.get("stade", "maturité")
    eau = plante["eau"]

    # dissipation par seconde qui vas etre convertit en heure

    dissipation_horaire = 3600 * plante["dissipation"]
    ch_min, ch_max = plante["besoin_chaleur_min"], plante["besoin_chaleur_max"]
    sol_min, sol_max = plante["besoin_soleil_min"], plante["besoin_soleil_max"]
    ha_min, ha_max = plante["humidite_air_min"], plante["humidite_air_max"]
    humidite = meteo["current"].get("humidity", 60)
    soleil = meteo["current"].get("uv", 3)
    chaleur = meteo["current"].get("temp_c", 15)
    stade_mul = FACTEURS_STADE.get(stade, 1.0)
    eau_a_apporter = eau * stade_mul * (
                ((ch_min + ch_max) / 2 - chaleur) / ((ch_max - ch_min) / 2) + ((sol_min + sol_max) / 2 - soleil) / (
                    (sol_max - sol_min) / 2) + ((ha_min + ha_max) / 2 - humidite) / ((ha_max - ha_min) / 2))
    eau_a_apporter = max(eau_a_apporter, eau * 0.1)

    # dissipation en temp réele en fonction de la météo

    dissipation = dissipation_horaire * (
                (1 + 0.020 * (chaleur - (ch_min + ch_max) / 2)) * (1 + 0.030 * (soleil - (sol_min + sol_max) / 2)) * (
                    1 - 0.015 * (humidite - (ha_min + ha_max) / 2)))
    instance["eau_deja_presente"] -= instance["eau_deja_presente"] * dissipation
    seuil_alerte = plante["eau"] * 0.10
    if instance["eau_deja_presente"] <= seuil_alerte:
        nb_arrosages += 1
        ouvrir_notif(f"AROSER {nom_numerote}", f"Votre {nom_numerote} a besoin d'eau !")
        instance["eau_deja_presente"] = eau_a_apporter
    return eau_a_apporter, instance["eau_deja_presente"]


#  Thread de surveillance par plante renouvelé chaque heures

def surveiller_hydratation(nom_numerote: str) -> None:
    """Tourne en arrière-plan, vérifie l'hydratation toutes les heures."""
    instance = next((p for p in jardin["plantes"] if p["nom_numéroté"] == nom_numerote), None)
    if instance and instance["eau_deja_presente"] <= 0:
        ouvrir_notif(f"ARROSER {nom_numerote}", f"Votre {nom_numerote} a soif \n pensez à l'arroser !")
    while True:
        time.sleep(3600)
        dose, niveau = calculer_cycle_arrosage(nom_numerote)
        if dose is not None:
            print(f"[{nom_numerote}] dose : {dose:.2f} mL | niveau : {niveau:.2f} mL")


def enregistrer_et_surveiller(nom_plante: str, stade: str) -> str:
    """Numérote la plante, l'ajoute au jardin et lance son thread de surveillance."""
    num = incrémenter_compteur(nom_plante)
    nom_numerote = f"{nom_plante}{num}"
    inscrire_plante_au_jardin(nom_plante, nom_numerote, stade)
    threading.Thread(target=surveiller_hydratation, args=(nom_numerote,), daemon=True).start()
    return nom_numerote


#  la page dede l'accueil / choix  ville

app = CTk()
app.geometry("360x640")
app.title("DigiGrow")
set_appearance_mode("dark")
noms_villes = [v["nom_ville"] for v in villes_data["villes"]]
main_frame = CTkFrame(master=app)
content_frame = CTkFrame(master=main_frame)
main_frame.pack(fill=BOTH, expand=True)
content_frame.pack(fill=BOTH, expand=True)


#  la notif
def ouvrir_notif(titre: str, texte: str) -> None:
    def _construire_fenetre():
        fenetre = CTkToplevel(app)
        fenetre.title(titre)
        fenetre.geometry("300x150")
        fenetre.grab_set()
        CTkLabel(fenetre, text=titre, font=("Arial", 15, "bold")).pack(pady=20)
        CTkLabel(fenetre, text=texte, font=("Arial", 12)).pack(pady=5)
        CTkButton(fenetre, text="OK", width=120, command=fenetre.destroy).pack(pady=10)

    app.after(0, _construire_fenetre)


#  les navigations en general sous forme de def utilisable sur toutes les pages

def vider_contenu() -> None:
    for widget in content_frame.winfo_children():
        widget.destroy()


def naviguer_vers(nom: str) -> None:
    vider_contenu()
    pages = {"Plants": dessiner_jardin, "Handbook": dessiner_handbook, "Stats": dessiner_stats,
             "AjouterPlante": dessiner_formulaire_ajout}
    if nom in pages:
        pages[nom]()


#  la page dede l'accueil / choix  ville

def dessiner_accueil() -> None:
    vider_contenu()
    CTkLabel(content_frame, text="DigiGrow", font=("Arial", 28, "bold")).pack(pady=40)
    CTkLabel(content_frame, text="Sélectionnez votre ville", font=("Arial", 18)).pack(pady=10)
    combobox = CTkComboBox(content_frame, values=noms_villes, state="readonly", width=220)
    combobox.pack(pady=5)
    combobox.set(noms_villes[0])

    def valider_ville():
        global ville_active
        ville_active = combobox.get()
        navbar()
        naviguer_vers("Plants")

    CTkButton(content_frame, text="VALIDER", width=200, command=valider_ville).pack(pady=20)


#  la navbar (waw)

def navbar() -> None:
    barre = CTkFrame(master=app, height=60)
    barre.pack(side=BOTTOM, fill=X)
    for icone, page in [("📘", "Handbook"), ("🌱", "Plants"), ("📊", "Stats")]:
        CTkButton(barre, text=icone, width=60, corner_radius=0, command=lambda p=page: naviguer_vers(p)).pack(side=LEFT,
                                                                                                              expand=True,
                                                                                                              fill=BOTH)


#  la page du jardin de l'user

def recharger_eau_manuellement(nom_numerote: str) -> None:
    """remplit l'eau de la plante qu'elle as besoin manuellement."""
    nom_base = nom_numerote.rstrip("0123456789")
    ref = next((p for p in catalogue["plantes"] if p["nom_courant"] == nom_base), None)
    instance = next((p for p in jardin["plantes"] if p["nom_numéroté"] == nom_numerote), None)
    if instance and ref:
        instance["eau_deja_presente"] = float(ref["eau"])
    naviguer_vers("Plants")


def dessiner_jardin() -> None:
    CTkLabel(content_frame, text="🌿 Mon Jardin", font=("Arial", 22, "bold")).pack(pady=(15, 5))
    if not jardin["plantes"]:
        CTkLabel(content_frame, text="Aucune plante pour l'instant.\nAjoutez-en une ci-dessous !", font=("Arial", 13),
                 text_color="#888888", justify="center").pack(pady=30)
    else:
        scroll = CTkScrollableFrame(content_frame, fg_color="transparent")
        scroll.pack(fill=BOTH, expand=True, padx=10, pady=5)
        for p in jardin["plantes"]:
            nom_num = p["nom_numéroté"]
            nom_base = p["nom_courant"]
            stade = p.get("stade", "maturité")
            eau_ml = p["eau_deja_presente"]
            ref = next((x for x in catalogue["plantes"] if x["nom_courant"] == nom_base), None)
            eau_max = ref["eau"] if ref else 50
            pct_eau = max(0.0, min(1.0, eau_ml / eau_max))
            prochain = temps_avant_prochain_arrosage(p, ref) if ref else "?"
            if pct_eau > 0.6:
                clr_bar = "#4CAF50"
            elif pct_eau > 0.3:
                clr_bar = "#FFC107"
            else:
                clr_bar = "#F44336"
            carte = CTkFrame(scroll, corner_radius=12, fg_color=("#2b2b2b", "#1e1e1e"), border_width=1,
                             border_color="#3a3a3a")
            carte.pack(fill=X, pady=6, padx=4)
            haut = CTkFrame(carte, fg_color="transparent")
            haut.pack(fill=X, padx=12, pady=(10, 2))
            CTkLabel(haut, text=f"🌱 {nom_num}", font=("Arial", 15, "bold"), anchor="w").pack(side=LEFT)
            CTkLabel(haut, text=stade, font=("Arial", 11), text_color="#888888").pack(side=RIGHT)
            lbl_eau = CTkFrame(carte, fg_color="transparent")
            lbl_eau.pack(fill=X, padx=12)
            CTkLabel(lbl_eau, text="💧 Eau", font=("Arial", 11), anchor="w").pack(side=LEFT)
            CTkLabel(lbl_eau, text=f"{eau_ml / 1000:.2f} L", font=("Arial", 11), text_color="#888888").pack(
                side=RIGHT)  # Affichage en cL
            barre = CTkProgressBar(carte, progress_color=clr_bar, height=8, corner_radius=4)
            barre.pack(fill=X, padx=12, pady=(2, 4))
            barre.set(pct_eau)
            CTkLabel(carte, text=f"⏱ Prochain arrosage : {prochain}", font=("Arial", 11), text_color="#aaaaaa",
                     anchor="w").pack(anchor="w", padx=12, pady=(0, 6))
            CTkButton(carte, text="💧 Je l'ai arrosé", width=180, height=30, corner_radius=8, fg_color="#1a6b3a",
                      hover_color="#145c30", font=("Arial", 12),
                      command=lambda n=nom_num: recharger_eau_manuellement(n)).pack(pady=(0, 10))
    CTkButton(content_frame, text="➕  Ajouter une plante", width=240, height=40, corner_radius=20,
              command=lambda: naviguer_vers("AjouterPlante")).pack(pady=10)


#  la page d'ajout de plantes

def dessiner_formulaire_ajout() -> None:
    CTkButton(content_frame, text="← Retour", width=100, anchor="w", fg_color="transparent",
              command=lambda: naviguer_vers("Plants")).pack(anchor="w", padx=10, pady=(10, 0))
    CTkLabel(content_frame, text="➕ Ajouter une plante", font=("Arial", 20, "bold")).pack(pady=(5, 15))
    plantes_dispo = plantes_compatibles_ville(ville_active)
    valeurs_combo = plantes_dispo if plantes_dispo else ["Aucune plante cette saison , dans cette ville"]
    CTkLabel(content_frame, text="Espèce", font=("Arial", 13)).pack()
    combo_plante = CTkComboBox(content_frame, values=valeurs_combo, state="readonly", width=220)
    combo_plante.pack(pady=5)
    combo_plante.set("Choisissez une plante...")
    CTkLabel(content_frame, text="Stade de développement", font=("Arial", 13)).pack(pady=(10, 0))
    combo_stade = CTkComboBox(content_frame, values=["tout juste planté", "maturité", "floraison"], state="readonly",
                              width=220)
    combo_stade.pack(pady=5)
    combo_stade.set("tout juste planté")

    def confirmer_ajout():
        nom = combo_plante.get()
        stade = combo_stade.get()
        if nom not in ("Choisissez une plante...", "Aucune plante disponible"):
            enregistrer_et_surveiller(nom, stade)
            naviguer_vers("Plants")

    CTkButton(content_frame, text="Ajouter", width=200, height=40, corner_radius=20, command=confirmer_ajout).pack(
        pady=25)


#  la page des conseil du père fouras le planteur fou

def dessiner_handbook() -> None:
    CTkLabel(content_frame, text="📘 Bible du jardinage", font=("Arial", 22, "bold")).pack(pady=(15, 2))
    CTkLabel(content_frame, text="Sélectionnez une plante pour ses conseils", font=("Arial", 12),
             text_color="#888888").pack(pady=(0, 8))
    scroll = CTkScrollableFrame(content_frame, fg_color="transparent")
    scroll.pack(fill=BOTH, expand=True, padx=10, pady=5)
    toutes = [p["nom_courant"] for p in catalogue["plantes"]]
    ligne = None
    for i, nom in enumerate(toutes):
        col = i % 2
        if col == 0:
            ligne = CTkFrame(scroll, fg_color="transparent")
            ligne.pack(fill=X, pady=3)
        CTkButton(ligne, text=nom, width=155, height=40, corner_radius=10,
                  command=lambda n=nom: ouvrir_fiche_plante(n)).grid(row=0, column=col, padx=4)


def ouvrir_fiche_plante(nom_plante: str) -> None:
    vider_contenu()
    CTkButton(content_frame, text="← Retour", width=100, anchor="w", fg_color="transparent",
              command=lambda: naviguer_vers("Handbook")).pack(anchor="w", padx=10, pady=(10, 0))
    CTkLabel(content_frame, text=f"🌿 {nom_plante}", font=("Arial", 22, "bold")).pack(pady=(5, 4))
    ref = next((p for p in catalogue["plantes"] if p["nom_courant"] == nom_plante), None)
    if ref:
        info_frame = CTkFrame(content_frame, corner_radius=10, fg_color=("#2b2b2b", "#1e1e1e"))
        info_frame.pack(fill=X, padx=15, pady=6)
        for label, valeur in [("🌡  Température", f"{ref['besoin_chaleur_min']}-{ref['besoin_chaleur_max']} °C"),
                              ("☀️  Soleil (UV)", f"{ref['besoin_soleil_min']}-{ref['besoin_soleil_max']}"),
                              ("💧  Eau / cycle", f"{ref['eau'] / 1000:.2f} L"),
                              ("💨  Humidité air", f"{ref['humidite_air_min']}-{ref['humidite_air_max']} %")]:
            ligne = CTkFrame(info_frame, fg_color="transparent")
            ligne.pack(fill=X, padx=12, pady=3)
            CTkLabel(ligne, text=label, font=("Arial", 12), anchor="w").pack(side=LEFT)
            CTkLabel(ligne, text=valeur, font=("Arial", 12, "bold"), anchor="e").pack(side=RIGHT)
    conseil_frame = CTkFrame(content_frame, corner_radius=10, fg_color=("#2b2b2b", "#1e1e1e"))
    conseil_frame.pack(fill=X, padx=15, pady=6)
    CTkLabel(conseil_frame, text="💡 Conseils", font=("Arial", 13, "bold"), anchor="w").pack(anchor="w", padx=12,
                                                                                            pady=(10, 4))
    CTkLabel(conseil_frame, text=conseil_pour_plante(nom_plante), font=("Arial", 12), wraplength=300, justify="left",
             anchor="w").pack(anchor="w", padx=12, pady=(0, 12))


#  la page des stats de l'user

def dessiner_stats() -> None:
    CTkLabel(content_frame, text="📊 Statistiques", font=("Arial", 22, "bold")).pack(pady=(15, 10))

    def carte_stat(icone: str, titre: str, valeur: str) -> None:
        carte = CTkFrame(content_frame, corner_radius=12, fg_color=("#2b2b2b", "#1e1e1e"), border_width=1,
                         border_color="#3a3a3a")
        carte.pack(fill=X, padx=15, pady=5)
        CTkLabel(carte, text=f"{icone}  {titre}", font=("Arial", 12), text_color="#888888", anchor="w").pack(anchor="w",
                                                                                                             padx=12,
                                                                                                             pady=(8,
                                                                                                                   2))
        CTkLabel(carte, text=valeur, font=("Arial", 18, "bold"), anchor="w").pack(anchor="w", padx=12, pady=(0, 8))

    carte_stat("🌱", "Plantes dans le jardin", str(len(jardin["plantes"])))
    carte_stat("💧", "Arrosages effectués", str(nb_arrosages))
    carte_stat("📍", "Ville actuelle", ville_active or "—")
    if meteo:
        temp = meteo["current"].get("temp_c", "?")
        hum = meteo["current"].get("humidity", "?")
        cond = traduire_code_meteo(meteo["current"])
        carte_stat("🌤", "Météo actuelle", f"{temp} °C — {cond}")
        carte_stat("💨", "Humidité de l'air", f"{hum} %")


#  Lancements de l'application

dessiner_accueil()
app.mainloop()
