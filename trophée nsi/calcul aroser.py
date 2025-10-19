import json
import requests

with open("stockage.json", "r", encoding="utf-8") as f:                 #fichier json contenant les plantes et leurs infos
    data = json.load(f)


url= "http://api.weatherapi.com/v1/forecast.json?key= 741a648e81bf44c28d7122536251410&q=Honfleur,France&days=14&aqi=no&alerts=no"           #api meteo url
response = requests.get(url)            # JSON directement converti en dictionnaire Python

if response.status_code == 200:                         #verifie si l'url fonctionne bien
    data1 = response.json()  # JSON directement converti en dictionnaire Python
else:
    print("Erreur lors du téléchargement du JSON :", response.status_code)

def aroser(nom_courant,eau_deja_arosé,stade):

    plante = next(p for p in data["plantes"] if p["nom_courant"] == nom_courant)

    # Extraire toutes les valeurs directement depuis le JSON
    eau = plante["eau"]                        # en cl
    besoin_chaleur_min = plante["besoin_chaleur_min"]        # en °C
    besoin_soleil_min = plante["besoin_soleil_min"]          # heures/jour
    humidite_sol_min = plante["humidite_sol_min"]           # %
    humidite_air_min = plante["humidite_air_min"]           # %

    besoin_chaleur_max = plante["besoin_chaleur_max"]      # en °C
    besoin_soleil_max = plante["besoin_soleil_max"]        # heures/jour
    humidite_sol_max = plante["humidite_sol_max"]         # %
    humidite_air_max = plante["humidite_air_max"]         # %

    """choses a def avec l'api météo"""

    humidite_sol = data1["current"]["humidity"]                   #en pourcentage
    humidite_air =data1["current"]["humidity"]                       #en pourcentage
    soleil = data1["current"]["uv"]                       #en indice uv
    chaleur =data1["current"]["temp_c"]                       #en degres

    """def du multiplicateur selon le stade"""

    if stade == 'tout juste planté':         #le stade prend un multiplicateur selon l'etat de la plante pour le calcul qui suit
        stade = 0.65
    elif stade == 'maturité':
        stade = 1
    else:
        stade = 1.35



    o_a_aroser = eau * stade * (                    #formule pour calculer l'eau a aroser selon les resultat meteo et besoins de la plante
    ((besoin_chaleur_min + besoin_chaleur_max) / 2 - chaleur) / ((besoin_chaleur_max - besoin_chaleur_min) / 2)
    + ((besoin_soleil_min + besoin_soleil_max) / 2 - soleil) / ((besoin_soleil_max - besoin_soleil_min) / 2)
    + ((humidite_sol_min + humidite_sol_max) / 2 - humidite_sol) / ((humidite_sol_max - humidite_sol_min) / 2)
    + ((humidite_air_min + humidite_air_max) / 2 - humidite_air) / ((humidite_air_max - humidite_air_min) / 2))
    return int(o_a_aroser)

print("tu dois aroser",aroser("Rose",0,'maturité'),"cl")
