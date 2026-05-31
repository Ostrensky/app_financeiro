"""
auth.py — Autenticação simples de usuário único.

Fluxo:
- Primeira vez: não há senha -> tela /setup para você criar uma.
- Depois: /login pede a senha. A sessão fica ativa via cookie assinado.
- /logout encerra a sessão.

A senha é guardada como HASH (nunca em texto puro) na tabela 'settings'.
"""

from flask import Blueprint, request, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, get_setting, set_setting

auth = Blueprint("auth", __name__)


def password_is_set():
    return bool(get_setting("password_hash"))


@auth.route("/setup", methods=["GET", "POST"])
def setup():
    # Se já existe senha, não deixa recriar por aqui.
    if password_is_set():
        return redirect(url_for("auth.login"))
    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        pw2 = request.form.get("password2", "")
        if len(pw) < 4:
            error = "A senha precisa ter pelo menos 4 caracteres."
        elif pw != pw2:
            error = "As senhas não conferem."
        else:
            set_setting("password_hash", generate_password_hash(pw))
            session["auth"] = True
            return redirect(url_for("index"))
    return render_template("setup.html", error=error)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if not password_is_set():
        return redirect(url_for("auth.setup"))
    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        if check_password_hash(get_setting("password_hash"), pw):
            session.permanent = True
            session["auth"] = True
            return redirect(url_for("index"))
        error = "Senha incorreta."
    return render_template("login.html", error=error)


@auth.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
