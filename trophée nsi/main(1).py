import json
import requests
import time
import threading
from customtkinter import *
import gzip
from datetime import *


url_communes = "https://raw.githubusercontent.com/poujy/concour-nsi/refs/heads/main/troph%C3%A9e%20nsi/jsonCommunes.json"
response = requests.get(url_communes)
communes = response.json()
villes = [commune["nom_standard_majuscule"] for commune in communes]

with open(r"\\LSOR-FILER\eleves$\gtomasino\Documents\trophe_nsi\data\stockage.json", "r", encoding="utf-8") as f:                            #fichier json contenant les plantes et leurs infos
    data = json.load(f)                                                                                                                 # JSON directement converti en dictionnaire Python

with open(r"\\LSOR-FILER\eleves$\gtomasino\Documents\trophe_nsi\data\compteur.json", "r", encoding="utf-8") as f:                            #json qui contient le nombres de plantes que l'utilisateur as
    compteur = json.load(f)                                                                                                             # JSON directement converti en dictionnaire Python                                                                                                # JSON directement converti en dictionnaire Python

url= "http://api.weatherapi.com/v1/forecast.json?key= 741a648e81bf44c28d7122536251410&q=Paris,France&days=14&aqi=no&alerts=no"          #api meteo url
response = requests.get(url)                                                                                                            # JSON directement converti en dictionnaire Python

if response.status_code == 200:                                                                                                         #verifie si l'url fonctionne bien
    data1 = response.json()                                                                                                             # JSON directement converti en dictionnaire Python
else:
    print("Erreur lors du téléchargement du JSON :", response.status_code)



#############################################################################################################################################################################################
#############################################################################################################################################################################################
#############################################################################################################################################################################################
#####                                                                          partie definitions                                                                                       #####
#############################################################################################################################################################################################
#############################################################################################################################################################################################
#############################################################################################################################################################################################


#cette def recupère la saison
def getsaison(date):
    mois = date.month #recupere le mois actuelle via le module datetime
    if mois in [12, 1, 2]:
        return "hiver"
    elif mois in [3, 4, 5]:
        return "printemps"
    elif mois in [6, 7, 8]:
        return "ete"
    else:
        return "automne"



############################################################################################################################################################################################################
############################################################################################################################################################################################################



def verif_climat_plante(nom_villes):
    plantes = data["plantes"]
    plantes_dispo = []

    # Recherche de la ville dans le fichier villes.json
    ville = None
    for v in villes["villes"]:                              # parcour toute les villes jusqu'a trouver la ville demandé
        if v["nom_ville"] == nom_villes:
            ville = v
            break

    # Comparaison des climats
    for plante in plantes:
        saison_actuelle = getsaison(date.today())

        #compare chaque climat pour trouver au moin une correspondance , cette etape est faite pour chaques fleures
        if (plante["oceanique"] == ville["oceanique"]) or (plante["mediterraneen"] == ville["mediterraneen"]) or (plante["continental"] == ville["continental"]) or (plante["oceanique_altere"] == ville["oceanique_altere"]) or (plante["montagnard"] == ville["montagnard"]):
            if plante[saison_actuelle] == True:
                plantes_dispo.append(plante["nom_courant"])                                                 # en cas de correspondance on ajoute la plante dans la liste de plantes plantable dans la ville demandé
            continue
    return plantes_dispo                                                                                # renvoie la liste de plante dispo sur une ville données


############################################################################################################################################################################################################
############################################################################################################################################################################################################


def aroser(nom_courant, stade):                                 #nom_courant str et stade str

    # nom_courant est par exemple "Rose1", il faut récupérer le nom de base
    eau = plante["eau"]
    dissipation_eau = 3600* plante["dissipation"]
    besoin_chaleur_min = plante["besoin_chaleur_min"]
    besoin_chaleur_max = plante["besoin_chaleur_max"]
    besoin_soleil_min = plante["besoin_soleil_min"]
    besoin_soleil_max = plante["besoin_soleil_max"]
    humidite_sol_min = plante["humidite_sol_min"]
    humidite_sol_max = plante["humidite_sol_max"]
    humidite_air_min = plante["humidite_air_min"]
    humidite_air_max = plante["humidite_air_max"]

    # données météo
    humidite_sol = data1["current"]["humidity"]
    humidite_air = data1["current"]["humidity"]
    soleil = data1["current"]["uv"]
    chaleur = data1["current"]["temp_c"]

    # multiplicateur selon le stade
    if stade == 'tout juste planté':
        stade_mul = 0.65
    elif stade == 'maturité':
        stade_mul = 1
    else:
        stade_mul = 1.35

    o_a_aroser = eau * stade_mul * (                                                                                     # formule de calcul de l'eau à arroser
        ((besoin_chaleur_min + besoin_chaleur_max) / 2 - chaleur_passer) / ((besoin_chaleur_max - besoin_chaleur_min) / 2)
        + ((besoin_soleil_min + besoin_soleil_max) / 2 - soleil_passer) / ((besoin_soleil_max - besoin_soleil_min) / 2)
        + ((humidite_sol_min + humidite_sol_max) / 2 - humidite_sol_passer) / ((humidite_sol_max - humidite_sol_min) / 2)
        + ((humidite_air_min + humidite_air_max) / 2 - humidite_air_passer) / ((humidite_air_max - humidite_air_min) / 2)
    )

    dissipation_effective = dissipation_eau * (
        (1 + 0.02 * (chaleur - ((besoin_chaleur_min + besoin_chaleur_max) / 2))) *
        (1 + 0.03 * (soleil - ((besoin_soleil_min + besoin_soleil_max) / 2))) *
        (1 - 0.015 * (humidite_air - ((humidite_air_min + humidite_air_max) / 2))) *
        (1 - 0.01 * (humidite_sol - ((humidite_sol_min + humidite_sol_max) / 2)))
    )


    existing = next((p for p in jardin["plantes"] if p["nom_courant"] == nom_courant), None)

    # soustraire la dissipation
    existing["eau_deja_presente"] -= existing["eau_deja_presente"] * dissipation_effective

    # initialiser eau_actuelle
    eau_actuelle = existing["eau_deja_presente"]

    # si eau trop faible, recharger et notifier
    if existing["eau_deja_presente"] <= 5:
        notification(f"AROSER VOTRE {nom_courant}", f"Votre {nom_courant} a besoin de votre attention")
        existing["eau_deja_presente"] = o_a_aroser
        eau_actuelle = existing["eau_deja_presente"]

    with open(r"data/jardin_utilisateur.json", "w", encoding="utf-8") as f:          # sauvegarde dans le JSON
        json.dump(jardin, f, indent=4, ensure_ascii=False)

    return o_a_aroser, eau_actuelle

############################################################################################################################################################################################################
############################################################################################################################################################################################################

def notification(titre,texte):
    print(titre,texte)                                                     #a faire avec tkinter

############################################################################################################################################################################################################
############################################################################################################################################################################################################

def boucle_plante(nom_courant, stade):                                      #faire tourner en thread indefiniment independament
    while True:
        print(aroser(nom_courant, stade))          #renvoie les données selon les calcul (eau a aroser en fonction de la meteo / eau restante apres dissipation chaque secondes)
        time.sleep(3600)                                                                           #attend une seconde avant chaque recalcul

############################################################################################################################################################################################################
############################################################################################################################################################################################################

def portail_plante(nom_courant, stade):
    global jardin_utilisateur
    jardin_utilisateur = []
    # Trouver la plante dans le jardin
    existing = next((p for p in jardin["plantes"] if p["nom_courant"].startswith(nom_courant)), None)

    # Récupérer le compteur correspondant dans le JSON compteur
    compteur_key = f"compteur_{nom_courant}"
    compteur_dict = next((c for c in compteur["compteur"] if compteur_key in c), None)

    # Incrémenter le compteur
    compteur_dict[compteur_key] += 1

    # Créer le nom final de la plante
    nom_plante_num = f"{nom_courant}{compteur_dict[compteur_key]}"

    # Ajouter la nouvelle plante dans le jardin
    ajouter_plante(nom_courant,nom_plante_num)

    # Lancer la boucle d'arrosage
    boucle_plante(nom_retourner, stade)

############################################################################################################################################################################################################
############################################################################################################################################################################################################

def ajouter_plante (nom_plante,nom_plante_num):
    jardin_utilisateur.append({"nom_numéroté":nom_plante_num,"nom_courant":nom_plante,"eau_deja_presente":0})
    return jardin_utilisateur

#############################################################################################################################################################################################
#############################################################################################################################################################################################
#############################################################################################################################################################################################
#####                                                                          partie CTkinter                                                                                          #####
#############################################################################################################################################################################################
#############################################################################################################################################################################################
#############################################################################################################################################################################################


app = CTk()
app.geometry("360x640")
set_appearance_mode("dark")
app.title("DigiGrow")
app.iconbitmap("data/DigiGrow.ico")

# Frame principale
main_frame = CTkFrame(master=app)
main_frame.pack(fill=BOTH, expand=True)

# Frame pour le contenu dynamique
content_frame = CTkFrame(master=main_frame)
content_frame.pack(fill=BOTH, expand=True)

# Variables globales pour Entry et Combobox
search_entry = None
combobox = None

# BUG CORRIGÉ : extraction de la liste des noms de villes depuis le dict JSON
noms_villes = [v["nom_ville"] for v in villes["villes"]]


# Fonction pour changer le contenu
def afficher_home(nom):
    global search_entry, combobox


    if nom == "Home":
        # Créer Entry + Combobox uniquement pour Home
        search_var = StringVar()

        label = CTkLabel(master=content_frame, text="Selectionnez votre ville", font=("Arial", 20))
        label.pack(pady=100)
        #filter_combobox , def qui permet a la combobox contenant les villes de s'adapter en fonction de la recherche souhaité
        def filter_combobox(*args):
            typed = search_var.get().lower()    #la recherche présente dans la combobox "search_var" est recupéré et assigné sur la valeur "typed"
            filtered = [v["nom_ville"] for v in villes["villes"] if typed in v["nom_ville"].lower()]    #la liste des villes présente sur le json est parcouru et le nom de chaques villes est assigné a la valeur filtered , filtered contien donc le nom de chaque villes
            combobox.configure(values=filtered)     #les villes sont definis comme des valeurs selectionnables dans la combobox
            if filtered:        #par defaut la villes definit par defaut devient le premier de la liste
                combobox.set(filtered[0])       #"Rouen"
            else:               #sinon la combobox s'adapte a la recherche
                combobox.set("")


        search_entry = CTkEntry(master=content_frame, textvariable=search_var, placeholder_text="Tapez une ville...")
        search_entry.pack(pady=5)
        search_var.trace_add("write", filter_combobox)

        # BUG CORRIGÉ : values=noms_villes (liste de str) au lieu de values=villes (dict)
        combobox = CTkComboBox(master=content_frame, values=noms_villes, state="readonly")
        combobox.pack(pady=5)
        # BUG CORRIGÉ : noms_villes[0] est maintenant défini
        combobox.set(noms_villes[0])


        def action_valider():
            global valeur
            valeur = combobox.get()     #valeur c'est la ville recupéré de la combobox selective
            contenu2("Plants")          #appelle la seconde page
                # ----------------- Menu en bas -----------------
            bottom_frame = CTkFrame(master=app, height=60)
            bottom_frame.pack(side=BOTTOM, fill=X)

            btn_wiki = CTkButton(master=bottom_frame, text="📘", width=60, corner_radius=0,
                         command=lambda: contenu2("Handbook"))
            btn_plante = CTkButton(master=bottom_frame, text="🌱", width=60, corner_radius=0,
                           command=lambda: contenu2("Plants"))
            btn_stats = CTkButton(master=bottom_frame, text="📊", width=60, corner_radius=0,
                          command=lambda: contenu2("Stats"))
            btn_parametre = CTkButton(master=bottom_frame, text="⚙️", width=60, corner_radius=0,
                            command=lambda: contenu2("Settings"))

            for btn in [ btn_wiki, btn_plante, btn_stats, btn_parametre]:
                btn.pack(side=LEFT, expand=True, fill=BOTH)


        btn_home = CTkButton(master=content_frame, text="VALIDER", width=200, command=action_valider)
        btn_home.pack(pady=20)

def contenu2(nom):
    global search_entry, combobox

    # Supprime le contenu précédent
    for widget in content_frame.winfo_children():
        widget.destroy()

    # Supprime Entry et Combobox s'ils existent
    if search_entry is not None:
        search_entry.destroy()
        search_entry = None
    if combobox is not None:
        combobox.destroy()
        combobox = None

    if nom == "Plants":

        label = CTkLabel(master=content_frame, text="Votre Jardin", font=("Arial", 20))
        label.pack(pady=100)

        def ajouter_plante():
            global selection_plante
            selection_plante = (verif_climat_plante(valeur))
            page_ajout_plante()


        btn_ajouter_plante = CTkButton(master=content_frame, text="Ajouter Plante", width=200, command=ajouter_plante)
        btn_ajouter_plante.pack(pady=20)

    #    combobox_plantes = CTkComboBox(master=content_frame, values=)
    elif nom == "Handbook":
        label = CTkLabel(master=content_frame, text="Manuel des plantes", font=("Arial", 20))
        label.pack(pady=100)

    elif nom == "Plants":
        label = CTkLabel(master=content_frame, text="Vos plantes", font=("Arial", 20))
        label.pack(pady=100)

    elif nom == "Stats":
        label = CTkLabel(master=content_frame, text="Statistiques", font=("Arial", 20))
        label.pack(pady=100)

    elif nom == "Settings":
        label = CTkLabel(master=content_frame, text="Paramètres", font=("Arial", 20))
        label.pack(pady=100)

def page_ajout_plante():

    combobox_plantes_dispo = CTkComboBox( activate_scrollbars=False,master=content_frame, values=selection_plante, state="readonly")
    combobox_plantes_dispo.pack(pady=5)


afficher_home("Home")


app.mainloop()


############################################################################################################################################################################################################
############################################################################################################################################################################################################
############################################################################################################################################################################################################
############################################################################################################################################################################################################

################################test le script#######################################


#thread pour executer plusieurs calculs a la fois