import hmac
import os
import re
import secrets
import sqlite3
import time
import uuid
from functools import wraps
from urllib.parse import urlparse

from flask import (Flask, abort, g, jsonify, redirect, request,
                   send_from_directory, session)
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(BASE, "templates")
DATA = os.environ.get("DATA_DIR", BASE)  # dossier de la base, des photos et de la clé secrète
DB = os.path.join(DATA, "boutique.db")
UP = os.path.join(DATA, "uploads")
os.makedirs(UP, exist_ok=True)

# Variables d'environnement : WHATSAPP, SECRET_KEY (facultative), COOKIE_SECURE, TRUST_PROXY
WHATSAPP = re.sub(r"\D", "", os.environ.get("WHATSAPP", "22300000000")) or "22300000000"


def cle_secrete():
    """SECRET_KEY de l'hébergeur, sinon une clé aléatoire créée une fois et gardée sur le disque."""
    k = os.environ.get("SECRET_KEY")
    if k:
        return k
    chemin = os.path.join(DATA, ".secret_key")
    try:
        fd = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    with open(chemin) as f:
        return f.read().strip()


app = Flask(__name__)
if os.environ.get("TRUST_PROXY", "1") == "1":  # Render et PythonAnywhere sont derrière un proxy HTTPS
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.secret_key = cle_secrete()
app.config.update(
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1") == "1",
    PERMANENT_SESSION_LIFETIME=8 * 3600,
)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
COULEUR = re.compile(r"^#[0-9a-fA-F]{6}$")
FAUX_HASH = generate_password_hash("mot-de-passe-factice")  # temps de réponse identique si l'email n'existe pas


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


with db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS produits(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL, cat TEXT NOT NULL,
        prix INTEGER NOT NULL, c TEXT DEFAULT '#1B2A6B', img TEXT DEFAULT '',
        actif INTEGER DEFAULT 1, vendeur_id INTEGER,
        description TEXT DEFAULT '', tailles TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE, mdp TEXT NOT NULL, role TEXT NOT NULL)""")
    c.execute("CREATE TABLE IF NOT EXISTS echecs(cle TEXT PRIMARY KEY, n INTEGER, debut REAL)")
    cols = [r[1] for r in c.execute("PRAGMA table_info(produits)")]
    for col, typ in (("vendeur_id", "INTEGER"), ("description", "TEXT DEFAULT ''"), ("tailles", "TEXT DEFAULT ''")):
        if col not in cols:
            c.execute(f"ALTER TABLE produits ADD COLUMN {col} {typ}")
    if c.execute("SELECT COUNT(*) FROM produits").fetchone()[0] == 0:
        c.executemany("INSERT INTO produits(nom,cat,prix,c) VALUES(?,?,?,?)", [
            ("Boubou brodé", "Homme", 25000, "#1B2A6B"),
            ("Robe longue wax", "Femme", 18000, "#B5452F"),
            ("Sac à dos", "Accessoires", 7000, "#3B3F58")])


# ---------- Sécurité : en-têtes, origine des requêtes, erreurs ----------
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


@app.before_request
def verifier_origine():
    """Refuse les requêtes qui modifient des données si elles viennent d'un autre site (CSRF)."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        src = request.headers.get("Origin") or request.headers.get("Referer")
        if src and urlparse(src).netloc != request.host:
            abort(403)


@app.after_request
def entetes(r):
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"] = "DENY"
    r.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    r.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    r.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    r.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; sandbox" if request.path.startswith("/uploads/") else CSP)
    if request.is_secure:
        r.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.path.startswith(("/admin", "/api/admin", "/register", "/api/register")):
        r.headers["Cache-Control"] = "no-store"
    return r


MESSAGES = {400: "Requête invalide.", 401: "Connexion requise.", 403: "Accès refusé.", 404: "Page introuvable.",
            405: "Méthode non autorisée.", 409: "Cet email est déjà utilisé.",
            413: "Fichier trop volumineux (5 Mo maximum).", 429: "Trop de tentatives, réessayez plus tard."}


@app.errorhandler(HTTPException)
def erreur(e):
    msg = MESSAGES.get(e.code, "Erreur.")
    if request.path.startswith("/api/"):
        return jsonify(erreur=msg), e.code
    return msg, e.code


# ---------- Anti force brute (compteurs gardés en base : valables avec plusieurs processus) ----------
def verrouille(cle, limite, fenetre=900):
    with db() as c:
        r = c.execute("SELECT n,debut FROM echecs WHERE cle=?", (cle,)).fetchone()
    return bool(r) and time.time() - r["debut"] < fenetre and r["n"] >= limite


def echec(cle, fenetre=900):
    now = time.time()
    with db() as c:
        r = c.execute("SELECT n,debut FROM echecs WHERE cle=?", (cle,)).fetchone()
        if not r or now - r["debut"] >= fenetre:
            c.execute("INSERT OR REPLACE INTO echecs(cle,n,debut) VALUES(?,1,?)", (cle, now))
        else:
            c.execute("UPDATE echecs SET n=n+1 WHERE cle=?", (cle,))


def reussite(cle):
    with db() as c:
        c.execute("DELETE FROM echecs WHERE cle=?", (cle,))


# ---------- Comptes ----------
def nb_users():
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def connecte(role=None):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **k):
            uid = session.get("uid")
            if not uid:
                abort(401)
            with db() as c:
                u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not u:
                session.clear()
                abort(401)
            if role and u["role"] != role:
                abort(403)
            g.user = u
            return f(*a, **k)
        return wrapper
    return deco


def valider(nom, email, mdp):
    nom, email = nom.strip()[:80], email.strip().lower()[:120]
    if not nom or not EMAIL.match(email) or not 8 <= len(mdp) <= 128:
        abort(400)
    return nom, email, generate_password_hash(mdp)


def ouvrir_session(uid):
    session.clear()  # nouvelle session à chaque connexion
    session.permanent = True
    session["uid"] = uid


@app.get("/")
def accueil():
    return send_from_directory(TPL, "index.html")


@app.get("/uploads/<path:nom>")
def photo(nom):
    return send_from_directory(UP, nom)


@app.get("/api/produits")
def produits():
    with db() as c:
        rows = c.execute("SELECT p.id,p.nom,p.cat,p.prix,p.c,p.img,p.description,p.tailles,u.nom AS vendeur FROM produits p "
                         "LEFT JOIN users u ON u.id=p.vendeur_id WHERE p.actif=1 ORDER BY p.id DESC").fetchall()
    return jsonify(wa=WHATSAPP, items=[dict(r) for r in rows])


@app.get("/register")
@app.get("/register.html")
def register_page():
    if nb_users():
        return redirect("/admin")
    return send_from_directory(TPL, "register.html")


@app.post("/api/register")
def register():
    f = request.form
    code = os.environ.get("SETUP_CODE")  # facultatif : code à fournir pour créer le compte gérant
    if code and not hmac.compare_digest(f.get("code", "")[:128], code):
        abort(401)
    nom, email, h = valider(f.get("nom", ""), f.get("email", ""), f.get("mdp", ""))
    with db() as c:  # insertion atomique : seul le tout premier compte est accepté
        n = c.execute("INSERT INTO users(nom,email,mdp,role) SELECT ?,?,?,'gerant' "
                      "WHERE NOT EXISTS (SELECT 1 FROM users)", (nom, email, h)).rowcount
        if n != 1:
            abort(403)
        uid = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
    ouvrir_session(uid)
    return jsonify(ok=True)


LOGIN = """<!DOCTYPE html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connexion – MEDMOHcoul collection</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0C1713;font:16px/1.55 Inter,system-ui,sans-serif;color:#17191B;padding:18px}
form{background:#FAF8F4;width:min(420px,100%);padding:34px 30px;border-radius:16px;display:grid;gap:10px}
.b{font:700 24px/1 'Cormorant Garamond',Georgia,serif}.b small{display:block;font:500 10px Inter,sans-serif;letter-spacing:.34em;text-transform:uppercase;color:#A9803A;margin-top:5px}
h1{margin:18px 0 4px;font:600 30px/1.15 'Cormorant Garamond',Georgia,serif}
input,button{font:inherit;font-size:15px;padding:13px 15px;border-radius:10px;border:1px solid #E7E3DB;background:#fff}
button{background:#0F3D2E;border:0;color:#fff;font-weight:600;cursor:pointer;min-height:50px}.e{color:#B3261E;margin:0;font-size:14px}</style>
<form method="post"><div class="b">MEDMOHcoul<small>collection</small></div><h1>Espace de gestion</h1>
<input type="email" name="email" placeholder="Adresse e-mail" autocomplete="username" autofocus required>
<input type="password" name="mdp" placeholder="Mot de passe" autocomplete="current-password" required>
<button>Se connecter</button>@@MSG@@</form>"""


def login(msg=""):
    return LOGIN.replace("@@MSG@@", msg)


@app.route("/admin", methods=["GET", "POST"])
def admin_page():
    if not nb_users():
        return redirect("/register")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:120]
        mdp = request.form.get("mdp", "")[:128]
        k1, k2 = f"ip:{request.remote_addr}", f"mail:{request.remote_addr}|{email}"
        if verrouille(k1, 20) or verrouille(k2, 5):
            return login('<p class="e">Trop de tentatives. Veuillez réessayer dans 15 minutes.</p>'), 429
        with db() as c:
            u = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        ok = check_password_hash(u["mdp"] if u else FAUX_HASH, mdp) and u is not None
        if ok:
            reussite(k2)
            ouvrir_session(u["id"])
            return redirect("/admin")
        echec(k1)
        echec(k2)
        return login('<p class="e">Adresse e-mail ou mot de passe incorrect.</p>'), 401
    if not session.get("uid"):
        return login("")
    return send_from_directory(TPL, "admin.html")


@app.get("/admin/logout")
def logout():
    session.clear()
    return redirect("/admin")


def proprio_id():
    """Le propriétaire est le premier compte créé : il ne peut être ni retiré ni modifié par un autre gérant."""
    with db() as c:
        return c.execute("SELECT MIN(id) FROM users").fetchone()[0]


@app.get("/api/admin/moi")
@connecte()
def moi():
    return jsonify(nom=g.user["nom"], role=g.user["role"], proprio=g.user["id"] == proprio_id())


# ---------- Produits (le gérant voit tout, un vendeur voit les siens) ----------
@app.get("/api/admin/produits")
@connecte()
def liste():
    sql = "SELECT p.*, u.nom AS vendeur FROM produits p LEFT JOIN users u ON u.id=p.vendeur_id"
    args = ()
    if g.user["role"] != "gerant":
        sql += " WHERE p.vendeur_id=?"
        args = (g.user["id"],)
    with db() as c:
        return jsonify([dict(r) for r in c.execute(sql + " ORDER BY p.id DESC", args)])


def peut(c, pid):
    if g.user["role"] == "gerant":
        return True
    r = c.execute("SELECT vendeur_id FROM produits WHERE id=?", (pid,)).fetchone()
    return bool(r) and r["vendeur_id"] == g.user["id"]


SIGNATURES = {".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG\r\n\x1a\n", ".webp": b"RIFF"}


def enregistrer_photo(fichier):
    if not fichier or not fichier.filename:
        return None
    ext = os.path.splitext(secure_filename(fichier.filename))[1].lower()
    if ext not in SIGNATURES:
        abort(400)
    tete = fichier.stream.read(12)
    fichier.stream.seek(0)
    # Le contenu doit vraiment être une image (et pas un script renommé en .png)
    if not tete.startswith(SIGNATURES[ext]) or (ext == ".webp" and tete[8:12] != b"WEBP"):
        abort(400)
    nom = uuid.uuid4().hex + ext
    fichier.save(os.path.join(UP, nom))
    return "/uploads/" + nom


def effacer_photo(img):
    if img and img.startswith("/uploads/"):
        try:
            os.remove(os.path.join(UP, os.path.basename(img)))
        except OSError:
            pass


@app.post("/api/admin/produits")
@connecte()
def sauver():
    f = request.form
    nom, cat = f.get("nom", "").strip()[:120], f.get("cat", "").strip()[:40]
    try:
        prix = int(f.get("prix", ""))
        pid = int(f["pid"]) if f.get("pid") else None
    except ValueError:
        abort(400)
    if not nom or not cat or not 0 <= prix <= 100_000_000:
        abort(400)
    coul = f.get("c", "")
    if not COULEUR.match(coul):
        coul = "#1B2A6B"
    actif = 1 if f.get("actif") else 0
    desc = f.get("description", "").strip()[:1000]
    tailles = ",".join(t.strip()[:12] for t in f.get("tailles", "").split(",") if t.strip())[:120]
    with db() as c:
        if pid and not peut(c, pid):
            abort(403)
        img = enregistrer_photo(request.files.get("image"))
        if pid:
            ancienne = c.execute("SELECT img FROM produits WHERE id=?", (pid,)).fetchone()
            c.execute("UPDATE produits SET nom=?,cat=?,prix=?,c=?,actif=?,description=?,tailles=? WHERE id=?",
                      (nom, cat, prix, coul, actif, desc, tailles, pid))
            if img:
                c.execute("UPDATE produits SET img=? WHERE id=?", (img, pid))
                if ancienne:
                    effacer_photo(ancienne["img"])
        else:
            c.execute("INSERT INTO produits(nom,cat,prix,c,img,actif,vendeur_id,description,tailles) VALUES(?,?,?,?,?,?,?,?,?)",
                      (nom, cat, prix, coul, img or "", actif,
                       None if g.user["role"] == "gerant" else g.user["id"], desc, tailles))
    return jsonify(ok=True)


@app.delete("/api/admin/produits/<int:pid>")
@connecte()
def supprimer(pid):
    with db() as c:
        if not peut(c, pid):
            abort(403)
        r = c.execute("SELECT img FROM produits WHERE id=?", (pid,)).fetchone()
        c.execute("DELETE FROM produits WHERE id=?", (pid,))
    if r:
        effacer_photo(r["img"])
    return jsonify(ok=True)


# ---------- Vendeurs (réservé au gérant) ----------
@app.get("/api/admin/vendeurs")
@connecte("gerant")
def vendeurs():
    with db() as c:
        return jsonify([dict(r) for r in c.execute(
            "SELECT id,nom,email,role FROM users WHERE id<>? ORDER BY id", (g.user["id"],))])


@app.post("/api/admin/vendeurs")
@connecte("gerant")
def ajouter_vendeur():
    f = request.form
    role = f.get("role", "vendeur")
    if role not in ("vendeur", "gerant"):
        abort(400)
    if role == "gerant" and g.user["id"] != proprio_id():
        abort(403)  # seul le propriétaire nomme un gérant
    nom, email, h = valider(f.get("nom", ""), f.get("email", ""), f.get("mdp", ""))
    try:
        with db() as c:
            c.execute("INSERT INTO users(nom,email,mdp,role) VALUES(?,?,?,?)", (nom, email, h, role))
    except sqlite3.IntegrityError:
        abort(409)
    return jsonify(ok=True)


@app.post("/api/admin/vendeurs/<int:uid>/mdp")
@connecte("gerant")
def mdp_vendeur(uid):
    mdp = request.form.get("mdp", "")
    if not 8 <= len(mdp) <= 128:
        abort(400)
    with db() as c:
        cible = c.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
        if not cible:
            abort(404)
        if uid == g.user["id"] or (cible["role"] == "gerant" and g.user["id"] != proprio_id()):
            abort(403)
        c.execute("UPDATE users SET mdp=? WHERE id=?", (generate_password_hash(mdp), uid))
    return jsonify(ok=True)


@app.delete("/api/admin/vendeurs/<int:uid>")
@connecte("gerant")
def retirer_vendeur(uid):
    with db() as c:
        cible = c.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
        if not cible:
            abort(404)
        if uid == g.user["id"] or (cible["role"] == "gerant" and g.user["id"] != proprio_id()):
            abort(403)
        c.execute("UPDATE produits SET vendeur_id=NULL WHERE vendeur_id=?", (uid,))
        c.execute("DELETE FROM users WHERE id=?", (uid,))
    return jsonify(ok=True)


@app.post("/api/admin/mon-mdp")
@connecte()
def mon_mdp():
    cle = f"pw:{g.user['id']}"
    if verrouille(cle, 5):
        abort(429)
    f = request.form
    if not check_password_hash(g.user["mdp"], f.get("ancien", "")[:128]):
        echec(cle)
        abort(401)
    nouveau = f.get("nouveau", "")
    if not 8 <= len(nouveau) <= 128:
        abort(400)
    reussite(cle)
    with db() as c:
        c.execute("UPDATE users SET mdp=? WHERE id=?", (generate_password_hash(nouveau), g.user["id"]))
    return jsonify(ok=True)


if __name__ == "__main__":
    app.config["SESSION_COOKIE_SECURE"] = False  # test local en http://127.0.0.1
    app.run(debug=True)
