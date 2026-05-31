"""
models.py — Definição das tabelas do banco de dados.

Decisão importante de design:
Todos os valores monetários são armazenados em CENTAVOS (inteiros).
Isso evita erros de arredondamento de ponto flutuante (ex.: 0.1 + 0.2 != 0.3).
A conversão para reais (float com 2 casas) acontece só na borda da API.
"""

from datetime import date, datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Account(db.Model):
    """Conta: corrente, poupança, cartão de crédito, dinheiro, investimento."""
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    # checking | savings | credit | cash | investment
    type = db.Column(db.String(20), nullable=False, default="checking")
    # on_budget=True entra no cálculo do orçamento (contas do dia a dia).
    # on_budget=False são contas de acompanhamento (ex.: investimentos).
    on_budget = db.Column(db.Boolean, nullable=False, default=True)
    starting_balance = db.Column(db.Integer, nullable=False, default=0)  # centavos
    archived = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    # Só para cartões de crédito (type='credit'):
    closing_day = db.Column(db.Integer, nullable=True)   # dia de fechamento da fatura
    due_day = db.Column(db.Integer, nullable=True)       # dia de vencimento
    credit_limit = db.Column(db.Integer, nullable=True)  # limite em centavos (opcional)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship(
        "Transaction", backref="account", lazy=True,
        foreign_keys="Transaction.account_id", cascade="all, delete-orphan"
    )


class CategoryGroup(db.Model):
    """Agrupamento de categorias (ex.: 'Casa', 'Lazer', 'Contas Fixas')."""
    __tablename__ = "category_groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    categories = db.relationship(
        "Category", backref="group", lazy=True,
        order_by="Category.sort_order", cascade="all, delete-orphan"
    )


class Category(db.Model):
    """Categoria de gasto (ex.: 'Mercado', 'Aluguel', 'Streaming')."""
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("category_groups.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    archived = db.Column(db.Boolean, nullable=False, default=False)


class Transaction(db.Model):
    """
    Lançamento (entrada ou saída).
    amount > 0  -> entrada (renda / dinheiro que chega)
    amount < 0  -> saída (gasto)
    category_id NULO = renda 'Pronto para Atribuir' (dinheiro a ser distribuído no orçamento).
    """
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    payee = db.Column(db.String(200), default="")     # quem recebeu / origem
    memo = db.Column(db.String(300), default="")      # observação
    amount = db.Column(db.Integer, nullable=False)    # centavos (negativo = gasto)
    cleared = db.Column(db.Boolean, nullable=False, default=True)  # conciliado
    # Para transferências entre contas (ex.: pagamento de fatura de cartão)
    transfer_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    # Mês da fatura que este pagamento quita (YYYY-MM), só em pagamentos de cartão.
    statement_month = db.Column(db.String(7), nullable=True)
    # Parcelamento: parcelas da mesma compra compartilham o mesmo installment_group.
    installment_group = db.Column(db.String(36), index=True, nullable=True)
    installment_num = db.Column(db.Integer, nullable=True)    # nº desta parcela (1, 2, 3...)
    installment_total = db.Column(db.Integer, nullable=True)  # total de parcelas
    import_hash = db.Column(db.String(64), index=True)  # evita importar duplicado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship("Category", backref="transactions")


class BudgetAllocation(db.Model):
    """
    Quanto foi ATRIBUÍDO a uma categoria em determinado mês.
    month no formato 'YYYY-MM'. É o coração do método YNAB ('dê uma função a cada real').
    """
    __tablename__ = "budget_allocations"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    month = db.Column(db.String(7), nullable=False)   # 'YYYY-MM'
    assigned = db.Column(db.Integer, nullable=False, default=0)  # centavos
    __table_args__ = (db.UniqueConstraint("category_id", "month", name="uq_cat_month"),)


class CategoryGoal(db.Model):
    """Meta de uma categoria: valor alvo e mês desejado."""
    __tablename__ = "category_goals"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    target_amount = db.Column(db.Integer, nullable=False, default=0)
    target_month = db.Column(db.String(7), nullable=True)
    note = db.Column(db.String(200), default="")
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship("Category")


class TransactionTemplate(db.Model):
    """Modelo/atalho para criar lançamentos frequentes com poucos toques."""
    __tablename__ = "transaction_templates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    payee = db.Column(db.String(200), default="")
    memo = db.Column(db.String(300), default="")
    amount = db.Column(db.Integer, nullable=False, default=0)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship("Account")
    category = db.relationship("Category")


class ScheduledTransaction(db.Model):
    """
    Lançamento previsto/recorrente. Alimenta a previsão de orçamento e os 'próximos a vencer'.
    frequency: once | weekly | biweekly | monthly | yearly
    """
    __tablename__ = "scheduled_transactions"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    payee = db.Column(db.String(200), default="")
    memo = db.Column(db.String(300), default="")
    amount = db.Column(db.Integer, nullable=False)    # centavos (negativo = gasto)
    frequency = db.Column(db.String(20), nullable=False, default="monthly")
    next_date = db.Column(db.Date, nullable=False, default=date.today)
    active = db.Column(db.Boolean, nullable=False, default=True)

    account = db.relationship("Account")
    category = db.relationship("Category")


class Setting(db.Model):
    """Configurações chave/valor do app (ex.: hash da senha, secret key da sessão)."""
    __tablename__ = "settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(300))


class NetWorthItem(db.Model):
    """
    Item de patrimônio que NÃO é uma conta do dia a dia: imóvel, carro,
    previdência, financiamento, empréstimo, etc.
    kind: 'asset' (algo que você tem) | 'liability' (algo que você deve).
    O valor de cada mês fica em NetWorthSnapshot.
    """
    __tablename__ = "networth_items"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(12), nullable=False, default="asset")  # asset | liability
    # categoria livre para agrupar no relatório (ex.: Imóveis, Veículos, Renda Fixa)
    category = db.Column(db.String(60), default="")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    snapshots = db.relationship(
        "NetWorthSnapshot", backref="item", lazy=True,
        cascade="all, delete-orphan"
    )


class NetWorthSnapshot(db.Model):
    """
    Foto do valor de um item em um mês (YYYY-MM). Valor em centavos.
    Para passivos, value é o quanto você devia naquele mês (positivo).
    """
    __tablename__ = "networth_snapshots"
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("networth_items.id"), nullable=False)
    month = db.Column(db.String(7), nullable=False)   # YYYY-MM
    value = db.Column(db.Integer, nullable=False, default=0)  # centavos
    __table_args__ = (db.UniqueConstraint("item_id", "month", name="uq_item_month"),)


def get_setting(key, default=None):
    s = Setting.query.get(key)
    return s.value if s else default


def set_setting(key, value):
    s = Setting.query.get(key)
    if s:
        s.value = value
    else:
        db.session.add(Setting(key=key, value=value))
    db.session.commit()
