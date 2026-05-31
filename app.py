"""
app.py — Aplicativo Cofre (controle financeiro pessoal).

Para rodar:
    pip install -r requirements.txt
    python app.py
Depois abra http://localhost:5000 no PC.
No celular (mesma rede Wi-Fi): http://SEU_IP_LOCAL:5000
"""

import os
import secrets
from datetime import date, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

from models import db, Account, CategoryGroup, Category, get_setting, set_setting

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Rotas que não exigem login.
PUBLIC_PATHS = {"/login", "/setup", "/logout", "/manifest.json", "/favicon.ico"}


def create_app():
    app = Flask(__name__)
    db_path = os.environ.get("COFRE_DB_PATH") or os.path.join(BASE_DIR, "cofre.db")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB para uploads
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COFRE_COOKIE_SECURE", "0") == "1"
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)

    from api import api
    from auth import auth
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(auth)

    @app.before_request
    def require_login():
        """Bloqueia tudo até o usuário estar autenticado."""
        p = request.path
        if p.startswith("/static/") or p in PUBLIC_PATHS:
            return None
        if not get_setting("password_hash"):
            # Ainda não há senha cadastrada -> ir para o setup.
            if p.startswith("/api/"):
                return jsonify({"error": "setup_required"}), 401
            return redirect(url_for("auth.setup"))
        if not session.get("auth"):
            if p.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("auth.login"))
        return None

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/manifest.json")
    def manifest():
        return jsonify({
            "name": "Cofre — Controle Financeiro",
            "short_name": "Cofre",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0f1115",
            "theme_color": "#0f1115",
            "icons": [
                {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        })

    with app.app_context():
        db.create_all()
        migrate_schema()
        seed_if_empty()
        # Secret key persistente (sessões sobrevivem a reinícios do servidor).
        key = get_setting("secret_key")
        if not key:
            key = secrets.token_hex(32)
            set_setting("secret_key", key)
        app.secret_key = key

    return app


def migrate_schema():
    """Aplica pequenas migrações SQLite para bancos criados por versões anteriores."""
    rows = db.session.execute(text("PRAGMA table_info(transactions)")).fetchall()
    cols = {r[1] for r in rows}
    migrations = {
        "transfer_account_id": "ALTER TABLE transactions ADD COLUMN transfer_account_id INTEGER",
        "statement_month": "ALTER TABLE transactions ADD COLUMN statement_month VARCHAR(7)",
        "installment_group": "ALTER TABLE transactions ADD COLUMN installment_group VARCHAR(36)",
        "installment_num": "ALTER TABLE transactions ADD COLUMN installment_num INTEGER",
        "installment_total": "ALTER TABLE transactions ADD COLUMN installment_total INTEGER",
        "import_hash": "ALTER TABLE transactions ADD COLUMN import_hash VARCHAR(64)",
    }
    for col, sql in migrations.items():
        if col not in cols:
            db.session.execute(text(sql))
    db.session.commit()


def seed_if_empty():
    """Cria dados iniciais (conta + categorias do dia a dia) na primeira execução."""
    if Account.query.first():
        return

    conta = Account(name="Conta Corrente", type="checking", on_budget=True,
                    starting_balance=0, sort_order=0)
    dinheiro = Account(name="Dinheiro", type="cash", on_budget=True,
                       starting_balance=0, sort_order=1)
    cartao = Account(name="Cartão de Crédito", type="credit", on_budget=True,
                     starting_balance=0, closing_day=28, due_day=8, sort_order=2)
    db.session.add_all([conta, dinheiro, cartao])

    estrutura = {
        "Contas Fixas": ["Aluguel/Moradia", "Energia", "Água", "Internet", "Telefone"],
        "Dia a Dia": ["Mercado", "Transporte", "Restaurante", "Saúde", "Farmácia"],
        "Lazer": ["Streaming", "Passeios", "Hobbies"],
        "Metas": ["Reserva de Emergência", "Viagem"],
    }
    for gi, (gname, cats) in enumerate(estrutura.items()):
        g = CategoryGroup(name=gname, sort_order=gi)
        db.session.add(g)
        db.session.flush()
        for ci, cname in enumerate(cats):
            db.session.add(Category(group_id=g.id, name=cname, sort_order=ci))
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    # host 0.0.0.0 permite acessar pelo celular na mesma rede.
    app.run(host="0.0.0.0", port=5000, debug=True)
