"""Tests de sécurité automatiques. Lancer :  python tests_securite.py
Ils tournent sur une base temporaire et ne touchent pas à vos vraies données."""
import io
import os
import re
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["COOKIE_SECURE"] = "0"          # le client de test parle en http
os.environ.pop("SECRET_KEY", None)
sys.path.insert(0, ICI)
import app as A  # noqa: E402

RES = []


def check(nom, cond, detail=""):
    RES.append((nom, bool(cond)))
    print(("  OK    " if cond else "  ECHEC ") + nom + ("" if cond else f"  -> {detail}"))


def client():
    return A.app.test_client()


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
G, V, ANON = client(), client(), client()
OR_OK = {"Origin": "http://localhost"}

print("\n[1] En-têtes de sécurité")
r = ANON.get("/")
csp = r.headers.get("Content-Security-Policy", "")
script_src = re.search(r"script-src ([^;]*)", csp)
check("CSP : scripts uniquement depuis le site (pas de unsafe-inline)", script_src and "'unsafe-inline'" not in script_src.group(1) and "'self'" in script_src.group(1), csp)
check("CSP : pas d'iframe externe, pas d'objet, base-uri fermée", "frame-ancestors 'none'" in csp and "object-src 'none'" in csp and "base-uri 'none'" in csp)
check("X-Frame-Options = DENY", r.headers.get("X-Frame-Options") == "DENY")
check("X-Content-Type-Options = nosniff", r.headers.get("X-Content-Type-Options") == "nosniff")
check("Referrer-Policy défini", bool(r.headers.get("Referrer-Policy")))
check("Pages admin non mises en cache", "no-store" in ANON.get("/register").headers.get("Cache-Control", ""))
check("Clé secrète aléatoire (pas la valeur par défaut)", len(A.app.secret_key) >= 32 and "changez" not in A.app.secret_key)
out = subprocess.run([sys.executable, "-c", "import app;print(app.app.config['SESSION_COOKIE_SECURE'])"],
                     cwd=ICI, capture_output=True, text=True, env={**os.environ, "DATA_DIR": tempfile.mkdtemp(), "COOKIE_SECURE": "1"})
check("Cookie de session 'Secure' par défaut en production", out.stdout.strip() == "True", out.stderr[-200:])

print("\n[2] Accès sans connexion")
check("API admin GET refusée (401)", ANON.get("/api/admin/produits").status_code == 401)
check("API admin POST refusée (401)", ANON.post("/api/admin/produits", data={"nom": "x", "cat": "y", "prix": "1"}).status_code == 401)
check("API admin DELETE refusée (401)", ANON.delete("/api/admin/produits/1").status_code == 401)
check("Gestion des vendeurs refusée (401)", ANON.get("/api/admin/vendeurs").status_code == 401)
check("/admin sans compte redirige vers l'inscription", ANON.get("/admin").status_code == 302)

print("\n[3] Inscription du gérant")
bad = [({"nom": "K", "email": "k@x.ml", "mdp": "123"}, "mot de passe trop court"),
       ({"nom": "K", "email": "pasunemail", "mdp": "motdepasse1"}, "email invalide"),
       ({"nom": "K", "email": "k@x.ml", "mdp": "a" * 500}, "mot de passe énorme"),
       ({"nom": "", "email": "k@x.ml", "mdp": "motdepasse1"}, "nom vide")]
for d, n in bad:
    check(f"Refusé : {n}", ANON.post("/api/register", data=d).status_code == 400)
r = G.post("/api/register", data={"nom": "Koné", "email": "K@X.ml", "mdp": "motdepasse1"})
check("Premier compte accepté", r.status_code == 200)
ck = r.headers.get("Set-Cookie", "")
check("Cookie de session HttpOnly + SameSite=Lax", "HttpOnly" in ck and "SameSite=Lax" in ck, ck)
check("Deuxième inscription refusée (403)", ANON.post("/api/register", data={"nom": "Pirate", "email": "p@x.ml", "mdp": "motdepasse1"}).status_code == 403)
check("Page /register fermée après le 1er compte", ANON.get("/register").status_code == 302)
import sqlite3  # noqa: E402
h = sqlite3.connect(A.DB).execute("SELECT mdp FROM users").fetchone()[0]
check("Mot de passe stocké haché (jamais en clair)", "motdepasse1" not in h and h.split(":")[0] in ("scrypt", "pbkdf2"), h[:20])

print("\n[4] CSRF (requêtes venant d'un autre site)")
d = {"nom": "T", "cat": "C", "prix": "100"}
check("POST avec Origin étranger refusé (403)", G.post("/api/admin/produits", data=d, headers={"Origin": "https://evil.example"}).status_code == 403)
check("POST avec Origin 'null' refusé (403)", G.post("/api/admin/produits", data=d, headers={"Origin": "null"}).status_code == 403)
check("POST avec Referer étranger refusé (403)", G.post("/api/admin/produits", data=d, headers={"Referer": "https://evil.example/x"}).status_code == 403)
check("POST depuis le site accepté (200)", G.post("/api/admin/produits", data=d, headers=OR_OK).status_code == 200)

print("\n[5] Injections")
sqli = "x'); DROP TABLE produits;--"
check("Produit avec payload SQL stocké comme simple texte", G.post("/api/admin/produits", data={"nom": sqli, "cat": "C", "prix": "5", "actif": "1"}).status_code == 200)
noms = [p["nom"] for p in G.get("/api/produits").json["items"]]
check("Table produits intacte, texte conservé tel quel", sqli in noms)
check("Connexion avec ' OR '1'='1 refusée", client().post("/admin", data={"email": "' OR '1'='1", "mdp": "x"}).status_code == 401)
check("Identifiant produit non numérique refusé", G.post("/api/admin/produits", data={**d, "pid": "1 OR 1=1"}).status_code == 400)
check("Route DELETE non numérique → 404", G.delete("/api/admin/produits/1%20OR%201=1").status_code == 404)
check("Prix négatif refusé", G.post("/api/admin/produits", data={**d, "prix": "-5"}).status_code == 400)
check("Prix absurde refusé", G.post("/api/admin/produits", data={**d, "prix": "999999999999"}).status_code == 400)
G.post("/api/admin/produits", data={"nom": "Couleur", "cat": "C", "prix": "1", "actif": "1", "c": "red;background:url(//evil.example/x)"})
col = [p for p in G.get("/api/produits").json["items"] if p["nom"] == "Couleur"][0]["c"]
check("Injection CSS via la couleur neutralisée", col == "#1B2A6B", col)
G.post("/api/admin/produits", data={"nom": "<img src=x onerror=alert(1)>", "cat": "C", "prix": "1", "actif": "1"})
check("Texte HTML renvoyé comme donnée JSON (la page l'échappe, voir [11])", any("<img" in p["nom"] for p in G.get("/api/produits").json["items"]))

print("\n[6] Envoi de fichiers")
def envoi(nom, contenu):
    return G.post("/api/admin/produits", data={"nom": "Photo", "cat": "C", "prix": "1", "actif": "1", "image": (io.BytesIO(contenu), nom)}, content_type="multipart/form-data").status_code
check("Fichier .php refusé", envoi("shell.php", b"<?php system($_GET[0]); ?>") == 400)
check("Fichier .svg (peut contenir du script) refusé", envoi("a.svg", b"<svg onload=alert(1)>") == 400)
check("Fichier .html refusé", envoi("a.html", b"<script>alert(1)</script>") == 400)
check("Script déguisé en .png refusé (contenu vérifié)", envoi("a.png", b"<script>alert(1)</script>") == 400)
check("Double extension .png.php refusée", envoi("a.png.php", PNG) == 400)
check("Vraie image PNG acceptée", envoi("ok.png", PNG) == 200)
img = [p["img"] for p in G.get("/api/produits").json["items"] if p["img"]][0]
r = ANON.get(img)
check("Image servie avec CSP restrictive + nosniff", r.status_code == 200 and "default-src 'none'" in r.headers.get("Content-Security-Policy", "") and r.headers.get("X-Content-Type-Options") == "nosniff")
big = G.post("/api/admin/produits", data={"nom": "G", "cat": "C", "prix": "1", "image": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024)), "g.png")}, content_type="multipart/form-data")
check("Fichier de plus de 5 Mo refusé (413)", big.status_code == 413)

print("\n[7] Traversée de dossiers")
for u in ("/uploads/../app.py", "/uploads/%2e%2e/app.py", "/uploads/..%2fapp.py", "/static/../app.py", "/static/%2e%2e/boutique.db", "/templates/admin.html"):
    r = ANON.get(u)
    check(f"{u} ne livre pas de fichier sensible", r.status_code in (404, 400) and b"SECRET" not in r.data and b"import " not in r.data, r.status_code)

print("\n[8] Force brute et comptes")
L = client()
codes = [L.post("/admin", data={"email": "k@x.ml", "mdp": f"faux{i}"}).status_code for i in range(7)]
check("Verrouillage après 5 échecs (429)", codes[:5] == [401] * 5 and 429 in codes[5:], codes)
check("Même le bon mot de passe est refusé pendant le blocage", L.post("/admin", data={"email": "k@x.ml", "mdp": "motdepasse1"}).status_code == 429)
r = G.post("/api/admin/vendeurs", data={"nom": "Awa", "email": "awa@x.ml", "mdp": "vendeur123"}, headers=OR_OK)
check("Gérant peut créer un vendeur", r.status_code == 200)
check("Email vendeur en doublon refusé (409)", G.post("/api/admin/vendeurs", data={"nom": "Awa", "email": "AWA@x.ml", "mdp": "vendeur123"}, headers=OR_OK).status_code == 409)
check("Vendeur avec mot de passe faible refusé", G.post("/api/admin/vendeurs", data={"nom": "B", "email": "b@x.ml", "mdp": "123"}, headers=OR_OK).status_code == 400)
check("Connexion vendeur OK", V.post("/admin", data={"email": "awa@x.ml", "mdp": "vendeur123"}).status_code == 302)

print("\n[9] Droits (élévation de privilèges)")
check("Vendeur : gestion des vendeurs interdite (403)", V.get("/api/admin/vendeurs").status_code == 403)
check("Vendeur : création de vendeur interdite (403)", V.post("/api/admin/vendeurs", data={"nom": "Z", "email": "z@x.ml", "mdp": "vendeur123"}, headers=OR_OK).status_code == 403)
check("Vendeur : changement de mot de passe d'un autre interdit", V.post("/api/admin/vendeurs/1/mdp", data={"mdp": "nouveau1234"}, headers=OR_OK).status_code == 403)
V.post("/api/admin/produits", data={"nom": "Pagne", "cat": "F", "prix": "5", "actif": "1"}, headers=OR_OK)
check("Vendeur ne voit que ses produits", [p["nom"] for p in V.get("/api/admin/produits").json] == ["Pagne"])
autre = [p["id"] for p in G.get("/api/admin/produits").json if p["vendeur"] is None][0]
check("Vendeur ne peut pas modifier un produit du gérant (403)", V.post("/api/admin/produits", data={**d, "pid": str(autre)}, headers=OR_OK).status_code == 403)
check("Vendeur ne peut pas supprimer un produit du gérant (403)", V.delete(f"/api/admin/produits/{autre}", headers=OR_OK).status_code == 403)
cles = set(G.get("/api/produits").json["items"][0].keys())
check("L'API publique ne fuit ni email ni mot de passe", cles <= {"id", "nom", "cat", "prix", "c", "img", "description", "tailles", "vendeur"}, cles)

print("\n[10] Erreurs et méthodes")
r = ANON.get("/nimporte-quoi")
check("Page inconnue : message simple, pas de trace technique", r.status_code == 404 and b"Traceback" not in r.data and b"werkzeug" not in r.data.lower())
check("Méthode interdite (405)", ANON.put("/api/produits").status_code == 405)
check("Débogueur désactivé en production", A.app.debug is False)

print("\n[11] Analyse statique du code")
fichiers = [os.path.join(ICI, "app.py")] + [os.path.join(ICI, d, f) for d in ("static", "templates") for f in os.listdir(os.path.join(ICI, d))]
motifs = [(r"\beval\(", "eval()"), (r"\bexec\(", "exec()"), (r"os\.system|subprocess|shell=True", "commande système"),
          (r"pickle|yaml\.load\(", "désérialisation dangereuse"), (r"render_template_string|\|safe\b", "gabarit non échappé"),
          (r"document\.write|new Function\(", "JS dynamique"), (r"\son[a-z]+\s*=\s*[\"']", "gestionnaire JS dans le HTML"),
          (r"<script>[^<]", "script inline dans le HTML"), (r"\bhttp://(?!127\.0\.0\.1|localhost)", "lien http non chiffré")]
for motif, nom in motifs:
    trouves = [os.path.basename(f) for f in fichiers if re.search(motif, open(f, encoding="utf-8").read())]
    check(f"Aucun {nom}", not trouves, trouves)
src = open(os.path.join(ICI, "app.py"), encoding="utf-8").read()
check("debug=True seulement dans le lancement local", src.count("debug=True") == 1 and src.index("debug=True") > src.index('if __name__'))
js = open(os.path.join(ICI, "static", "boutique.js"), encoding="utf-8").read()
# On ignore les lignes qui fabriquent du texte brut (message WhatsApp, partage), pas du HTML
TEXTE_BRUT = ("encodeURIComponent", "navigator.share", "return`- ")
nus = [m for l in js.splitlines() if not any(t in l for t in TEXTE_BRUT)
       for m in re.findall(r"\$\{(?:p\.(?:nom|cat|vendeur|description|tailles|img|c)|tl|t|cur\.nom)\}", l)]
check("Toutes les données produit sont échappées avant affichage (esc)", not nus, nus)
adm = open(os.path.join(ICI, "static", "admin.js"), encoding="utf-8").read()
check("Admin : données échappées avant affichage", not re.findall(r"\+p\.(?:nom|cat|vendeur|description|tailles)\+", adm))
check("Liens externes ouverts avec noopener", "noopener" in js)

ko = [n for n, ok in RES if not ok]
print(f"\n{len(RES) - len(ko)}/{len(RES)} contrôles réussis.")
if ko:
    print("À corriger :", *ko, sep="\n - ")
    sys.exit(1)
