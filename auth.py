import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import time
from datetime import timedelta
from pathlib import Path

import click
from flask import g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


def read_users(path):
    users = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(users, list):
        raise ValueError("users.json muss eine Liste von Benutzern enthalten.")
    emails = set()
    for user in users:
        if not isinstance(user, dict) or not isinstance(user.get("email"), str) or not isinstance(user.get("passwordHash"), str):
            raise ValueError("Jeder Benutzer benoetigt email und passwordHash.")
        email = user["email"].strip().lower()
        if not email or "@" not in email or email in emails or not user["passwordHash"].startswith(("scrypt:", "pbkdf2:")):
            raise ValueError("Benutzer-E-Mail oder Passwort-Hash in users.json ist ungueltig oder doppelt.")
        user["email"] = email
        emails.add(email)
    return users


def write_users(path, users):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".users-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(users, output, indent=2, ensure_ascii=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def password_version(user):
    return hashlib.sha256(user["passwordHash"].encode("utf-8")).hexdigest()


def register_auth(app, auth_root):
    root = Path(auth_root)
    root.mkdir(parents=True, exist_ok=True)
    key_path = root / "session-key"
    if not key_path.exists():
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w", encoding="ascii") as output:
                output.write(secrets.token_hex(32))
    app.config.update(
        SECRET_KEY=key_path.read_text(encoding="ascii"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("PHOCA_HTTPS") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    if len(app.secret_key) < 32:
        raise ValueError("Der Sitzungsschluessel ist ungueltig.")
    users_path = root / "users.json"
    app.config["USERS_PATH"] = users_path
    lock = threading.Lock()
    attempts = {}
    dummy_hash = generate_password_hash(secrets.token_urlsafe(24))

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    def failure(message, status):
        if request.path.startswith("/api/"):
            return jsonify(error=message), status
        return render_template("auth.html", profile=request.endpoint == "profile", error=message), status

    @app.before_request
    def require_auth():
        g.user = None
        public = request.endpoint in ("login", "static", "phoca_logo", "phoca_font")
        if not public:
            if not users_path.exists():
                return failure("Benutzerdatei fehlt. Bitte zuerst einen Benutzer mit flask create-user anlegen.", 503)
            users = read_users(users_path)
            user = next((user for user in users if user["email"] == session.get("email")), None)
            if user and hmac.compare_digest(session.get("password_version", ""), password_version(user)):
                g.user = user
            else:
                if "email" in session:
                    session.clear()
                if request.path.startswith("/api/"):
                    return jsonify(error="Bitte zuerst anmelden."), 401
                return redirect(url_for("login"))
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            expected = session.get("csrf_token")
            supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            if not expected or not isinstance(supplied, str) or not hmac.compare_digest(expected, supplied):
                return failure("Sicherheitspruefung fehlgeschlagen. Bitte die Seite neu laden.", 400)

    @app.after_request
    def auth_headers(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("auth.html", profile=False)
        now = time.monotonic()
        address = request.remote_addr or "local"
        with lock:
            for key in list(attempts):
                attempts[key] = [stamp for stamp in attempts[key] if now - stamp < 300]
                if not attempts[key]:
                    del attempts[key]
            recent = attempts.setdefault(address, [])
            if len(recent) >= 10:
                return failure("Zu viele Anmeldeversuche. Bitte in fuenf Minuten erneut versuchen.", 429)
            recent.append(now)
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(password) > 1024:
            return failure("E-Mail oder Passwort ist falsch.", 401)
        if not users_path.exists():
            return failure("Benutzerdatei fehlt. Bitte zuerst einen Benutzer mit flask create-user anlegen.", 503)
        users = read_users(users_path)
        user = next((user for user in users if user["email"] == email), None)
        valid = check_password_hash(user["passwordHash"] if user else dummy_hash, password)
        if not user or not valid:
            return failure("E-Mail oder Passwort ist falsch.", 401)
        session.clear()
        session.permanent = True
        session.update(email=email, password_version=password_version(user), csrf_token=secrets.token_urlsafe(32))
        return redirect(url_for("index"))

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/profile", methods=["GET", "POST"])
    def profile():
        if request.method == "GET":
            return render_template("auth.html", profile=True)
        current = request.form.get("current_password", "")
        password = request.form.get("new_password", "")
        if not 8 <= len(password) <= 1024:
            return failure("Das neue Passwort muss zwischen 8 und 1024 Zeichen lang sein.", 400)
        if password != request.form.get("confirm_password"):
            return failure("Die neuen Passwoerter stimmen nicht ueberein.", 400)
        with lock:
            users = read_users(users_path)
            user = next((user for user in users if user["email"] == g.user["email"]), None)
            if not user or password_version(user) != session["password_version"]:
                session.clear()
                return redirect(url_for("login"))
            if len(current) > 1024 or not check_password_hash(user["passwordHash"], current):
                return failure("Das aktuelle Passwort ist falsch.", 400)
            if current == password:
                return failure("Das neue Passwort muss sich vom bisherigen unterscheiden.", 400)
            user["passwordHash"] = generate_password_hash(password)
            write_users(users_path, users)
            session["password_version"] = password_version(user)
            session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("profile", changed="1"))

    @app.cli.command("create-user")
    @click.option("--email", prompt="E-Mail")
    @click.password_option(confirmation_prompt=True)
    def create_user(email, password):
        """Benutzer mit Passwort-Hash zur lokalen JSON-Datei hinzufuegen."""
        email = email.strip().lower()
        if "@" not in email or not 8 <= len(password) <= 1024:
            raise click.ClickException("Gueltige E-Mail und Passwort mit mindestens 8 Zeichen erwartet.")
        with lock:
            users = read_users(users_path) if users_path.exists() else []
            if any(user["email"] == email for user in users):
                raise click.ClickException("Diese E-Mail existiert bereits.")
            users.append({"email": email, "passwordHash": generate_password_hash(password)})
            write_users(users_path, users)
        click.echo(f"Benutzer in {users_path} hinzugefuegt.")

    @app.cli.command("hash-password")
    @click.password_option(confirmation_prompt=True)
    def hash_password(password):
        """Passwort-Hash fuer einen manuell hinzugefuegten JSON-Benutzer erzeugen."""
        if not 8 <= len(password) <= 1024:
            raise click.ClickException("Passwort muss zwischen 8 und 1024 Zeichen lang sein.")
        click.echo(generate_password_hash(password))
