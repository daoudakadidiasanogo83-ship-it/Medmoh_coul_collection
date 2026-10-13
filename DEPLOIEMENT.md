# Mettre MEDMOHcoul collection en ligne

Variables à définir (quel que soit l'hébergeur) :
- `SECRET_KEY` : une longue phrase aléatoire (obligatoire)
- `WHATSAPP` : numéro des commandes, format international sans + (ex. 22370000000)
- `DATA_DIR` : dossier où sont gardées la base et les photos (voir plus bas)

Après la mise en ligne, le client ouvre `/register` pour créer le compte gérant.
Faites-le vous-même tout de suite : le premier qui visite /register devient gérant.

## Option 1 : PythonAnywhere (gratuit, les fichiers sont conservés)

1. Créez un compte gratuit (« Beginner »), puis ouvrez l'onglet **Files** et envoyez le zip, ou utilisez **Consoles > Bash** :
   `git clone <votre-depot> shop`  (ou `unzip medmohcoul-boutique.zip`)
2. Dans la console Bash : `cd shop && pip install --user -r requirements.txt`
3. Onglet **Web > Add a new web app** > Manual configuration > choisissez la version de Python.
4. Dans **Code**, ouvrez le fichier WSGI, effacez tout et mettez :

```python
import os, sys
sys.path.insert(0, "/home/VOTRE_NOM/shop")
os.environ["SECRET_KEY"] = "une-longue-phrase-aleatoire"
os.environ["WHATSAPP"] = "22370000000"
from app import app as application
```

5. Cliquez sur **Reload** : le site est sur `VOTRE_NOM.pythonanywhere.com`.
6. Compte gratuit : reconnectez-vous et prolongez l'application dans l'onglet Web environ tous les 3 mois, sinon elle est désactivée.

Les produits et les photos restent dans le dossier `shop` (rien à configurer pour DATA_DIR).

## Option 2 : GitHub + Render

1. Poussez le dossier `shop` sur GitHub (ajoutez un `.gitignore` avec `boutique.db`, `uploads/`, `__pycache__/`).
2. Render > **New > Web Service** > votre dépôt.
3. Build Command : `pip install -r requirements.txt`  
   Start Command : `gunicorn app:app`
4. Ajoutez les variables `SECRET_KEY` et `WHATSAPP`.
5. **Important** : le disque d'un service gratuit est effacé à chaque redéploiement ou redémarrage, donc les produits, les comptes et les photos disparaîtraient.
   Pour les garder, il faut une instance payante avec un **Disk** (Settings > Disks, par exemple monté sur `/data`) et la variable `DATA_DIR=/data`.
6. Un service gratuit s'endort après 15 minutes sans visite : le premier visiteur attend le réveil.

Conseil : pour un vrai client, PythonAnywhere gratuit garde les données ; Render n'est adapté qu'avec le disque payant.

## Fichiers prêts pour GitHub + Render

- `.gitignore` : empêche d'envoyer la base, les photos et vos secrets sur GitHub.
- `render.yaml` : sur Render, choisissez **New > Blueprint**, sélectionnez le dépôt, renseignez `WHATSAPP` : le service et son disque `/data` sont créés d'un coup (instance payante).

## Sécurité

Ce qui est en place : mots de passe hachés, verrouillage après 5 échecs (15 minutes), protection contre les requêtes venant d'autres sites (CSRF), en-têtes de sécurité et CSP stricte (aucun script externe ni inline), cookies HttpOnly + SameSite + Secure, vérification du contenu des images envoyées, couleurs et prix validés côté serveur, clé secrète aléatoire si `SECRET_KEY` n'est pas définie.

Avant chaque mise en ligne : `python tests_securite.py` (contrôles automatiques, sur une base temporaire).

Après la mise en ligne, faites aussi des scans externes sur l'adresse du site :
- https://observatory.mozilla.org (en-têtes, cookies, CSP)
- https://securityheaders.com
- OWASP ZAP « baseline scan » sur l'URL publique (gratuit)

Réglages : `COOKIE_SECURE=0` seulement si le site est servi en http (déconseillé) ; en local sous PyCharm, `app.py` le désactive tout seul.
Bonnes pratiques : mot de passe gérant long et unique, `pip install -U -r requirements.txt` régulièrement, sauvegarde de `boutique.db` et du dossier `uploads/`.

## Démo gratuite, puis passage en payant (Render)

Le dépôt contient deux fichiers : `render.yaml` (gratuit, c'est celui que Render lit) et `render-payant.yaml` (instance payante + disque `/data`).

**Pendant la démo (gratuit)**
1. Déployez avec `render.yaml` tel quel. Render demande `WHATSAPP` et `SETUP_CODE` : choisissez un code que vous seul connaissez.
2. Ouvrez `/register`, saisissez le code d'installation et créez le compte gérant.
3. Prévenez le client : sans disque, les produits et comptes saisis peuvent disparaître quand le service redémarre ou est redéployé. Le code d'installation empêche qu'un inconnu crée un compte gérant après un redémarrage.

**Quand le client valide (payant)**
1. Sur GitHub, remplacez tout le contenu de `render.yaml` par celui de `render-payant.yaml`, puis validez la modification.
2. Render synchronise le Blueprint et demande une carte : c'est là que le paiement commence.
3. Le disque `/data` est vide au départ : recréez le compte gérant sur `/register` (avec le code), puis les produits. Vérifiez que `DATA_DIR=/data` apparaît dans Environment.
