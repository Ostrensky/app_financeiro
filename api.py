"""
api.py — Endpoints JSON consumidos pelo frontend.

Convenção de valores: a API recebe e devolve REAIS (float, 2 casas).
A conversão para centavos (armazenamento) acontece aqui.
"""

from datetime import date, datetime, timedelta
from collections import defaultdict
import uuid
from flask import Blueprint, request, jsonify
from sqlalchemy import func

from models import (db, Account, CategoryGroup, Category, Transaction,
                    BudgetAllocation, ScheduledTransaction,
                    NetWorthItem, NetWorthSnapshot, CategoryGoal,
                    TransactionTemplate)
import budget as budget_mod
import forecast as forecast_mod
import cards as cards_mod
import networth as networth_mod
import importer

api = Blueprint("api", __name__)


# ---------- helpers ----------
def cents(v):
    if v is None or v == "":
        return 0
    return int(round(float(v) * 100))


def reais(c):
    return (c or 0) / 100


def parse_date(s):
    if not s:
        return date.today()
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def add_months(d, k):
    """Soma k meses a uma data, ajustando o dia ao último dia do mês quando necessário."""
    total = (d.year * 12 + (d.month - 1)) + k
    y, m = total // 12, total % 12 + 1
    # último dia do mês alvo
    if m == 12:
        last = 31
    else:
        last = (date(y, m + 1, 1) - __import__("datetime").timedelta(days=1)).day
    return date(y, m, min(d.day, last))


def last_day_of_month(month: str) -> date:
    y, m = int(month[:4]), int(month[5:7])
    if m == 12:
        return date(y, 12, 31)
    return date(y, m + 1, 1) - timedelta(days=1)


def spending_account_ids():
    """Accounts included in spending reports.

    Reports should match what appears in the transaction ledger, including
    off-budget checking/cash/credit accounts. Archived accounts stay hidden.
    """
    return [a.id for a in Account.query.filter_by(archived=False).all()]


# ---------- contas ----------
@api.get("/accounts")
def list_accounts():
    accs = Account.query.order_by(Account.sort_order, Account.id).all()
    return jsonify([{
        "id": a.id, "name": a.name, "type": a.type,
        "on_budget": a.on_budget, "archived": a.archived,
        "starting_balance": reais(a.starting_balance),
        "balance": reais(budget_mod.account_balance(a.id)),
        "closing_day": a.closing_day, "due_day": a.due_day,
        "credit_limit": reais(a.credit_limit) if a.credit_limit else None,
    } for a in accs])


@api.post("/accounts")
def create_account():
    d = request.get_json(force=True)
    a = Account(
        name=d.get("name", "Conta"),
        type=d.get("type", "checking"),
        on_budget=bool(d.get("on_budget", True)),
        starting_balance=cents(d.get("starting_balance", 0)),
        closing_day=d.get("closing_day") or None,
        due_day=d.get("due_day") or None,
        credit_limit=cents(d["credit_limit"]) if d.get("credit_limit") else None,
        sort_order=Account.query.count(),
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({"id": a.id}), 201


@api.put("/accounts/<int:aid>")
def update_account(aid):
    a = Account.query.get_or_404(aid)
    d = request.get_json(force=True)
    if "name" in d: a.name = d["name"]
    if "type" in d: a.type = d["type"]
    if "on_budget" in d: a.on_budget = bool(d["on_budget"])
    if "archived" in d: a.archived = bool(d["archived"])
    if "starting_balance" in d: a.starting_balance = cents(d["starting_balance"])
    if "closing_day" in d: a.closing_day = d["closing_day"] or None
    if "due_day" in d: a.due_day = d["due_day"] or None
    if "credit_limit" in d: a.credit_limit = cents(d["credit_limit"]) if d["credit_limit"] else None
    db.session.commit()
    return jsonify({"ok": True})


@api.delete("/accounts/<int:aid>")
def delete_account(aid):
    a = Account.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    return jsonify({"ok": True})


# ---------- grupos e categorias ----------
@api.get("/categories")
def list_categories():
    groups = CategoryGroup.query.order_by(CategoryGroup.sort_order).all()
    return jsonify([{
        "id": g.id, "name": g.name,
        "categories": [
            {"id": c.id, "name": c.name, "archived": c.archived}
            for c in sorted(g.categories, key=lambda c: c.sort_order) if not c.archived
        ],
    } for g in groups])


@api.post("/category-groups")
def create_group():
    d = request.get_json(force=True)
    g = CategoryGroup(name=d.get("name", "Novo grupo"), sort_order=CategoryGroup.query.count())
    db.session.add(g)
    db.session.commit()
    return jsonify({"id": g.id}), 201


@api.put("/category-groups/<int:gid>")
def update_group(gid):
    g = CategoryGroup.query.get_or_404(gid)
    d = request.get_json(force=True)
    if "name" in d: g.name = d["name"]
    db.session.commit()
    return jsonify({"ok": True})


@api.delete("/category-groups/<int:gid>")
def delete_group(gid):
    g = CategoryGroup.query.get_or_404(gid)
    db.session.delete(g)
    db.session.commit()
    return jsonify({"ok": True})


@api.post("/categories")
def create_category():
    d = request.get_json(force=True)
    gid = d["group_id"]
    c = Category(group_id=gid, name=d.get("name", "Nova categoria"),
                 sort_order=Category.query.filter_by(group_id=gid).count())
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id}), 201


@api.put("/categories/<int:cid>")
def update_category(cid):
    c = Category.query.get_or_404(cid)
    d = request.get_json(force=True)
    if "name" in d: c.name = d["name"]
    if "group_id" in d: c.group_id = d["group_id"]
    if "archived" in d: c.archived = bool(d["archived"])
    db.session.commit()
    return jsonify({"ok": True})


@api.delete("/categories/<int:cid>")
def delete_category(cid):
    c = Category.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})


# ---------- transações ----------
def txn_to_dict(t):
    return {
        "id": t.id,
        "account_id": t.account_id,
        "account_name": t.account.name if t.account else "",
        "category_id": t.category_id,
        "category_name": t.category.name if t.category else None,
        "date": t.date.isoformat(),
        "payee": t.payee,
        "memo": t.memo,
        "amount": reais(t.amount),
        "cleared": t.cleared,
        "installment_num": t.installment_num,
        "installment_total": t.installment_total,
        "installment_group": t.installment_group,
    }


@api.get("/transactions")
def list_transactions():
    q = Transaction.query
    if request.args.get("account_id"):
        q = q.filter(Transaction.account_id == int(request.args["account_id"]))
    if request.args.get("category_id"):
        q = q.filter(Transaction.category_id == int(request.args["category_id"]))
    if request.args.get("month"):
        q = q.filter(func.strftime("%Y-%m", Transaction.date) == request.args["month"])
    if request.args.get("search"):
        s = f"%{request.args['search']}%"
        q = q.filter(db.or_(Transaction.payee.ilike(s), Transaction.memo.ilike(s)))
    q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
    limit = int(request.args.get("limit", 200))
    return jsonify([txn_to_dict(t) for t in q.limit(limit).all()])


@api.post("/transactions")
def create_transaction():
    d = request.get_json(force=True)
    installments = int(d.get("installments") or 1)
    base_date = parse_date(d.get("date"))
    account_id = d["account_id"]
    category_id = d.get("category_id") or None
    payee = d.get("payee", "")
    memo = d.get("memo", "")
    cleared = bool(d.get("cleared", True))
    splits = d.get("splits") or []

    if splits:
        signed_total = cents(d.get("amount", 0))
        total_cents = abs(signed_total)
        sign = -1 if signed_total < 0 else 1
        split_rows = []
        split_total = 0
        for item in splits:
            amount = abs(cents(item.get("amount", 0)))
            if amount <= 0:
                continue
            split_total += amount
            split_rows.append({
                "category_id": item.get("category_id") or None,
                "amount": amount,
            })
        if not split_rows:
            return jsonify({"error": "Informe ao menos uma divisão."}), 400
        if split_total != total_cents:
            return jsonify({"error": "A soma das divisões precisa bater com o valor total."}), 400

        group = uuid.uuid4().hex if installments > 1 else None
        ids = []
        for item in split_rows:
            base = item["amount"] // installments
            remainder = item["amount"] - base * installments
            for i in range(installments):
                part = base + (remainder if i == 0 else 0)
                t = Transaction(
                    account_id=account_id, category_id=item["category_id"],
                    date=add_months(base_date, i),
                    payee=payee, memo=memo, amount=sign * part, cleared=cleared,
                    installment_group=group,
                    installment_num=i + 1 if installments > 1 else None,
                    installment_total=installments if installments > 1 else None,
                )
                db.session.add(t)
                db.session.flush()
                ids.append(t.id)
        db.session.commit()
        return jsonify({"ids": ids, "splits": len(split_rows), "installments": installments}), 201

    # Parcela única: comportamento normal.
    if installments <= 1:
        t = Transaction(
            account_id=account_id, category_id=category_id, date=base_date,
            payee=payee, memo=memo, amount=cents(d.get("amount", 0)), cleared=cleared,
        )
        db.session.add(t)
        db.session.commit()
        return jsonify({"id": t.id, "installments": 1}), 201

    # Compra parcelada: divide o total e cria uma transação por mês.
    # 'amount' é o valor TOTAL da compra (ex.: 12x de 200 -> total 2400).
    total_cents = cents(d.get("amount", 0))
    # Divide igualmente; ajusta a 1ª parcela para fechar a soma exata (evita erro de centavo).
    base = total_cents // installments
    remainder = total_cents - base * installments
    group = uuid.uuid4().hex
    ids = []
    for i in range(installments):
        part = base + (remainder if i == 0 else 0)  # sobra de centavos vai na 1ª parcela
        t = Transaction(
            account_id=account_id, category_id=category_id,
            date=add_months(base_date, i),
            payee=payee, memo=memo, amount=part, cleared=cleared,
            installment_group=group, installment_num=i + 1, installment_total=installments,
        )
        db.session.add(t)
        db.session.flush()
        ids.append(t.id)
    db.session.commit()
    return jsonify({"ids": ids, "installments": installments, "group": group}), 201


@api.put("/transactions/<int:tid>")
def update_transaction(tid):
    t = Transaction.query.get_or_404(tid)
    d = request.get_json(force=True)
    if "account_id" in d: t.account_id = d["account_id"]
    if "category_id" in d: t.category_id = d["category_id"] or None
    if "date" in d: t.date = parse_date(d["date"])
    if "payee" in d: t.payee = d["payee"]
    if "memo" in d: t.memo = d["memo"]
    if "amount" in d: t.amount = cents(d["amount"])
    if "cleared" in d: t.cleared = bool(d["cleared"])
    db.session.commit()
    return jsonify({"ok": True})


@api.delete("/transactions/<int:tid>")
def delete_transaction(tid):
    t = Transaction.query.get_or_404(tid)
    # ?scope=all remove todas as parcelas da mesma compra (futuras e passadas).
    if request.args.get("scope") == "all" and t.installment_group:
        n = Transaction.query.filter_by(installment_group=t.installment_group).delete()
        db.session.commit()
        return jsonify({"ok": True, "deleted": n})
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True, "deleted": 1})


# ---------- orçamento ----------
def template_to_dict(t):
    return {
        "id": t.id,
        "name": t.name,
        "account_id": t.account_id,
        "account_name": t.account.name if t.account else "",
        "category_id": t.category_id,
        "category_name": t.category.name if t.category else None,
        "payee": t.payee,
        "memo": t.memo,
        "amount": reais(t.amount),
    }


@api.get("/templates")
def list_templates():
    items = TransactionTemplate.query.filter_by(archived=False).order_by(
        TransactionTemplate.sort_order, TransactionTemplate.id).all()
    return jsonify([template_to_dict(t) for t in items])


@api.post("/templates")
def create_template():
    d = request.get_json(force=True)
    t = TransactionTemplate(
        name=d.get("name") or d.get("payee") or "Modelo",
        account_id=d["account_id"],
        category_id=d.get("category_id") or None,
        payee=d.get("payee", ""),
        memo=d.get("memo", ""),
        amount=cents(d.get("amount", 0)),
        sort_order=TransactionTemplate.query.count(),
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(template_to_dict(t)), 201


@api.put("/templates/<int:tid>")
def update_template(tid):
    t = TransactionTemplate.query.get_or_404(tid)
    d = request.get_json(force=True)
    for f in ("name", "payee", "memo"):
        if f in d: setattr(t, f, d[f])
    if "account_id" in d: t.account_id = d["account_id"]
    if "category_id" in d: t.category_id = d["category_id"] or None
    if "amount" in d: t.amount = cents(d["amount"])
    if "archived" in d: t.archived = bool(d["archived"])
    db.session.commit()
    return jsonify(template_to_dict(t))


@api.delete("/templates/<int:tid>")
def delete_template(tid):
    t = TransactionTemplate.query.get_or_404(tid)
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})


@api.post("/templates/<int:tid>/post")
def post_template(tid):
    t = TransactionTemplate.query.get_or_404(tid)
    d = request.get_json(silent=True) or {}
    txn = Transaction(
        account_id=t.account_id,
        category_id=t.category_id,
        date=parse_date(d.get("date")),
        payee=t.payee or t.name,
        memo=t.memo,
        amount=t.amount,
        cleared=True,
    )
    db.session.add(txn)
    db.session.commit()
    return jsonify({"id": txn.id}), 201


@api.get("/budget")
def get_budget():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    return jsonify(budget_mod.budget_for_month(month))


@api.post("/budget/assign")
def assign_budget():
    d = request.get_json(force=True)
    cid = d["category_id"]
    month = d["month"]
    val = cents(d.get("assigned", 0))
    alloc = BudgetAllocation.query.filter_by(category_id=cid, month=month).first()
    if alloc:
        alloc.assigned = val
    else:
        db.session.add(BudgetAllocation(category_id=cid, month=month, assigned=val))
    db.session.commit()
    return jsonify(budget_mod.budget_for_month(month))


def _shift_month(month: str, k: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    total = y * 12 + (m - 1) + k
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


@api.post("/budget/copy")
def copy_budget():
    """
    Copia os valores atribuídos de um mês de origem para um mês de destino.
    Body:
      target  (YYYY-MM)  obrigatório  -> mês que recebe os valores
      source  (YYYY-MM)  opcional     -> origem (padrão: mês anterior ao target)
      mode    'fill' | 'overwrite'    -> 'fill' só preenche categorias zeradas/vazias;
                                          'overwrite' substitui tudo (padrão: fill)
    """
    d = request.get_json(force=True)
    target = d["target"]
    source = d.get("source") or _shift_month(target, -1)
    mode = d.get("mode", "fill")

    src = {a.category_id: a.assigned
           for a in BudgetAllocation.query.filter_by(month=source).all()}
    tgt = {a.category_id: a for a in BudgetAllocation.query.filter_by(month=target).all()}

    copied = 0
    for cid, val in src.items():
        if val == 0:
            continue
        existing = tgt.get(cid)
        if existing:
            if mode == "overwrite" or existing.assigned == 0:
                if existing.assigned != val:
                    existing.assigned = val
                    copied += 1
        else:
            db.session.add(BudgetAllocation(category_id=cid, month=target, assigned=val))
            copied += 1
    db.session.commit()
    result = budget_mod.budget_for_month(target)
    result["copied"] = copied
    result["source"] = source
    return jsonify(result)


def goal_to_dict(g):
    current_month = date.today().strftime("%Y-%m")
    budget = budget_mod.budget_for_month(current_month)
    available = 0
    group_name = ""
    for group in budget["groups"]:
        for cat in group["categories"]:
            if cat["id"] == g.category_id:
                available = cents(cat["available"])
                group_name = group["name"]
                break
    remaining = max(0, g.target_amount - available)
    months_left = None
    suggested = None
    if g.target_month:
        ty, tm = int(g.target_month[:4]), int(g.target_month[5:7])
        cy, cm = int(current_month[:4]), int(current_month[5:7])
        months_left = max(1, (ty - cy) * 12 + (tm - cm) + 1)
        suggested = remaining // months_left
    progress = 100 if g.target_amount <= 0 else min(100, round(available / g.target_amount * 100))
    return {
        "id": g.id,
        "category_id": g.category_id,
        "category_name": g.category.name if g.category else "",
        "group_name": group_name,
        "target_amount": reais(g.target_amount),
        "target_month": g.target_month,
        "note": g.note,
        "available": reais(available),
        "remaining": reais(remaining),
        "months_left": months_left,
        "suggested_monthly": reais(suggested) if suggested is not None else None,
        "progress": progress,
    }


@api.get("/goals")
def list_goals():
    goals = CategoryGoal.query.filter_by(archived=False).order_by(CategoryGoal.id).all()
    return jsonify([goal_to_dict(g) for g in goals])


@api.post("/goals")
def create_goal():
    d = request.get_json(force=True)
    g = CategoryGoal(
        category_id=d["category_id"],
        target_amount=cents(d.get("target_amount", 0)),
        target_month=d.get("target_month") or None,
        note=d.get("note", ""),
    )
    db.session.add(g)
    db.session.commit()
    return jsonify(goal_to_dict(g)), 201


@api.put("/goals/<int:gid>")
def update_goal(gid):
    g = CategoryGoal.query.get_or_404(gid)
    d = request.get_json(force=True)
    if "category_id" in d: g.category_id = d["category_id"]
    if "target_amount" in d: g.target_amount = cents(d["target_amount"])
    if "target_month" in d: g.target_month = d["target_month"] or None
    if "note" in d: g.note = d["note"]
    if "archived" in d: g.archived = bool(d["archived"])
    db.session.commit()
    return jsonify(goal_to_dict(g))


@api.delete("/goals/<int:gid>")
def delete_goal(gid):
    g = CategoryGoal.query.get_or_404(gid)
    db.session.delete(g)
    db.session.commit()
    return jsonify({"ok": True})


# ---------- previsões / recorrências ----------
def sched_to_dict(s):
    return {
        "id": s.id,
        "account_id": s.account_id,
        "category_id": s.category_id,
        "category_name": s.category.name if s.category else None,
        "payee": s.payee,
        "memo": s.memo,
        "amount": reais(s.amount),
        "frequency": s.frequency,
        "next_date": s.next_date.isoformat(),
        "active": s.active,
    }


@api.get("/scheduled")
def list_scheduled():
    items = ScheduledTransaction.query.order_by(ScheduledTransaction.next_date).all()
    return jsonify([sched_to_dict(s) for s in items])


@api.post("/scheduled")
def create_scheduled():
    d = request.get_json(force=True)
    s = ScheduledTransaction(
        account_id=d["account_id"],
        category_id=d.get("category_id") or None,
        payee=d.get("payee", ""),
        memo=d.get("memo", ""),
        amount=cents(d.get("amount", 0)),
        frequency=d.get("frequency", "monthly"),
        next_date=parse_date(d.get("next_date")),
        active=bool(d.get("active", True)),
    )
    db.session.add(s)
    db.session.commit()
    return jsonify({"id": s.id}), 201


@api.put("/scheduled/<int:sid>")
def update_scheduled(sid):
    s = ScheduledTransaction.query.get_or_404(sid)
    d = request.get_json(force=True)
    for f in ("payee", "memo", "frequency"):
        if f in d: setattr(s, f, d[f])
    if "account_id" in d: s.account_id = d["account_id"]
    if "category_id" in d: s.category_id = d["category_id"] or None
    if "amount" in d: s.amount = cents(d["amount"])
    if "next_date" in d: s.next_date = parse_date(d["next_date"])
    if "active" in d: s.active = bool(d["active"])
    db.session.commit()
    return jsonify({"ok": True})


@api.delete("/scheduled/<int:sid>")
def delete_scheduled(sid):
    s = ScheduledTransaction.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    return jsonify({"ok": True})


@api.post("/scheduled/<int:sid>/post")
def post_scheduled(sid):
    """Confirma um lançamento previsto como real e avança a próxima data."""
    s = ScheduledTransaction.query.get_or_404(sid)
    t = Transaction(
        account_id=s.account_id, category_id=s.category_id,
        date=s.next_date, payee=s.payee, memo=s.memo, amount=s.amount, cleared=True,
    )
    db.session.add(t)
    # avança a próxima ocorrência
    nd = s.next_date
    if s.frequency == "weekly":
        nd = date.fromordinal(nd.toordinal() + 7)
    elif s.frequency == "biweekly":
        nd = date.fromordinal(nd.toordinal() + 14)
    elif s.frequency == "monthly":
        ny, nm = (nd.year + (nd.month // 12)), (nd.month % 12 + 1)
        day = min(nd.day, 28)
        nd = date(ny, nm, day)
    elif s.frequency == "yearly":
        nd = date(nd.year + 1, nd.month, nd.day)
    elif s.frequency == "once":
        s.active = False
    s.next_date = nd
    db.session.commit()
    return jsonify({"id": t.id})


# ---------- previsão de orçamento ----------
@api.get("/forecast")
def get_forecast():
    months = int(request.args.get("months", 6))
    use_avg = request.args.get("use_average", "1") != "0"
    return jsonify(forecast_mod.forecast(months, use_avg))


# ---------- relatórios ----------
@api.get("/reports/spending")
def report_spending():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    acc_ids = spending_account_ids()
    rows = db.session.query(
        Category.name, func.coalesce(func.sum(Transaction.amount), 0),
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.amount < 0,
        func.strftime("%Y-%m", Transaction.date) == month,
    ).group_by(Category.id).order_by(func.sum(Transaction.amount)).all()
    return jsonify([{"category": name, "amount": reais(-total)} for name, total in rows])


@api.get("/reports/trend")
def report_trend():
    months = int(request.args.get("months", 6))
    acc_ids = spending_account_ids()
    today = date.today()
    out = []
    y, m = today.year, today.month
    seq = []
    for _ in range(months):
        seq.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    seq.reverse()
    for mon in seq:
        income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.account_id.in_(acc_ids), Transaction.amount > 0,
            func.strftime("%Y-%m", Transaction.date) == mon,
        ).scalar() or 0
        expense = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.account_id.in_(acc_ids), Transaction.amount < 0,
            func.strftime("%Y-%m", Transaction.date) == mon,
        ).scalar() or 0
        out.append({"month": mon, "income": reais(income), "expense": reais(-expense)})
    return jsonify(out)


def _month_sequence_ending(month: str, count: int):
    seq = []
    y, m = int(month[:4]), int(month[5:7])
    for _ in range(count):
        seq.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(seq))


@api.get("/reports/category-evolution")
def report_category_evolution():
    """Evolucao mensal de gastos de uma categoria."""
    months = max(3, min(24, int(request.args.get("months", 12))))
    end_month = request.args.get("month") or date.today().strftime("%Y-%m")
    acc_ids = spending_account_ids()
    seq = _month_sequence_ending(end_month, months)

    cid = request.args.get("category_id")
    if cid:
        category = Category.query.get_or_404(int(cid))
    else:
        top = db.session.query(
            Transaction.category_id, func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.account_id.in_(acc_ids),
            Transaction.category_id.isnot(None),
            Transaction.amount < 0,
            func.strftime("%Y-%m", Transaction.date).in_(seq),
        ).group_by(Transaction.category_id).order_by(func.sum(Transaction.amount)).first() if acc_ids else None
        category = Category.query.get(top[0]) if top else Category.query.filter_by(archived=False).first()

    if not category:
        return jsonify({"category": None, "months": seq, "points": [], "summary": {}})

    rows = db.session.query(
        func.strftime("%Y-%m", Transaction.date),
        func.coalesce(func.sum(Transaction.amount), 0),
    ).filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.category_id == category.id,
        Transaction.amount < 0,
        func.strftime("%Y-%m", Transaction.date).in_(seq),
    ).group_by(func.strftime("%Y-%m", Transaction.date)).all() if acc_ids else []
    by_month = {mon: -int(total) for mon, total in rows}
    points = [{"month": mon, "amount": reais(by_month.get(mon, 0))} for mon in seq]
    values = [by_month.get(mon, 0) for mon in seq]
    total = sum(values)
    avg = total / months if months else 0
    nonzero = [v for v in values if v > 0]
    current = values[-1] if values else 0
    previous = values[-2] if len(values) > 1 else 0

    payees = db.session.query(
        Transaction.payee, func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.category_id == category.id,
        Transaction.amount < 0,
        func.strftime("%Y-%m", Transaction.date).in_(seq),
    ).group_by(Transaction.payee).order_by(func.sum(Transaction.amount)).limit(8).all() if acc_ids else []

    return jsonify({
        "category": {
            "id": category.id,
            "name": category.name,
            "group": category.group.name if category.group else "",
        },
        "months": seq,
        "points": points,
        "summary": {
            "total": reais(total),
            "average": reais(avg),
            "current": reais(current),
            "previous": reais(previous),
            "change": reais(current - previous),
            "max": reais(max(values) if values else 0),
            "min_nonzero": reais(min(nonzero) if nonzero else 0),
        },
        "top_payees": [{"payee": p or "Sem descricao", "amount": reais(-total)} for p, total in payees],
    })


def _scheduled_dates_in_month(sched, month: str):
    y, m = int(month[:4]), int(month[5:7])
    start = date(y, m, 1)
    end = last_day_of_month(month)
    if sched.next_date > end:
        return []
    freq = sched.frequency
    if freq == "once":
        return [sched.next_date] if start <= sched.next_date <= end else []
    if freq == "monthly":
        return [date(y, m, min(sched.next_date.day, end.day))] if sched.next_date <= end else []
    if freq == "yearly":
        return [date(y, m, min(sched.next_date.day, end.day))] if sched.next_date.month == m and sched.next_date <= end else []
    if freq in ("weekly", "biweekly"):
        step = 7 if freq == "weekly" else 14
        d = sched.next_date
        while d < start:
            d = date.fromordinal(d.toordinal() + step)
        out = []
        while d <= end:
            out.append(d)
            d = date.fromordinal(d.toordinal() + step)
        return out
    return []


@api.get("/reports/spending-timeline")
def report_spending_timeline():
    """Linha diaria de gasto real, previsto e meta do mes."""
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    category_id = request.args.get("category_id")
    cid = int(category_id) if category_id and category_id != "all" else None
    start = date(int(month[:4]), int(month[5:7]), 1)
    end = last_day_of_month(month)
    today = date.today()
    acc_ids = spending_account_ids()

    q = Transaction.query.filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.amount < 0,
        Transaction.transfer_account_id.is_(None),
        Transaction.date >= start,
        Transaction.date <= end,
    )
    if cid:
        q = q.filter(Transaction.category_id == cid)
    else:
        q = q.filter(Transaction.category_id.isnot(None))

    actual_by_day = defaultdict(int)
    for t in q.all() if acc_ids else []:
        actual_by_day[t.date.isoformat()] += -int(t.amount)

    expected_by_day = defaultdict(int)
    sched_q = ScheduledTransaction.query.filter(
        ScheduledTransaction.active.is_(True),
        ScheduledTransaction.amount < 0,
    )
    if cid:
        sched_q = sched_q.filter(ScheduledTransaction.category_id == cid)
    else:
        sched_q = sched_q.filter(ScheduledTransaction.category_id.isnot(None))
    for sched in sched_q.all():
        for d in _scheduled_dates_in_month(sched, month):
            # Future and overdue expected spends should still affect the projection.
            if month == today.strftime("%Y-%m") and d < today:
                d = today
            expected_by_day[d.isoformat()] += -int(sched.amount)

    budget = budget_mod.budget_for_month(month)
    if cid:
        assigned = 0
        category = None
        for group in budget["groups"]:
            for cat in group["categories"]:
                if cat["id"] == cid:
                    assigned = cents(cat["assigned"])
                    category = {"id": cid, "name": cat["name"], "group": group["name"]}
                    break
        goal = assigned
        label = category["name"] if category else "Categoria"
    else:
        goal = sum(cents(cat["assigned"]) for group in budget["groups"] for cat in group["categories"] if cat["assigned"] > 0)
        category = None
        label = "Todas as categorias"

    days = []
    actual_running = 0
    projected_running = 0
    for day in range(1, end.day + 1):
        d = date(start.year, start.month, day)
        key = d.isoformat()
        actual_running += actual_by_day.get(key, 0)
        projected_running += actual_by_day.get(key, 0)
        projected_running += expected_by_day.get(key, 0)
        goal_line = goal * day / end.day if goal else 0
        days.append({
            "date": key,
            "day": day,
            "actual": reais(actual_running),
            "projected": reais(projected_running),
            "goal_line": reais(goal_line),
            "daily_actual": reais(actual_by_day.get(key, 0)),
            "daily_expected": reais(expected_by_day.get(key, 0)),
        })

    actual_total = sum(actual_by_day.values())
    expected_total = sum(expected_by_day.values())
    projected_total = actual_total + expected_total
    elapsed_days = min(end.day, max(1, (today - start).days + 1)) if month == today.strftime("%Y-%m") else end.day
    remaining_days = max(0, end.day - elapsed_days)
    as_of_day = min(today, end) if month == today.strftime("%Y-%m") else end

    actual_by_category = defaultdict(int)
    actual_q = Transaction.query.filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.amount < 0,
        Transaction.transfer_account_id.is_(None),
        Transaction.category_id.isnot(None),
        Transaction.date >= start,
        Transaction.date <= as_of_day,
    )
    for t in actual_q.all() if acc_ids else []:
        actual_by_category[t.category_id] += -int(t.amount)

    expected_by_category = defaultdict(int)
    sched_all = ScheduledTransaction.query.filter(
        ScheduledTransaction.active.is_(True),
        ScheduledTransaction.amount < 0,
        ScheduledTransaction.category_id.isnot(None),
    ).all()
    for sched in sched_all:
        for d in _scheduled_dates_in_month(sched, month):
            if month != today.strftime("%Y-%m") or d >= today:
                expected_by_category[sched.category_id] += -int(sched.amount)

    pace = []
    for group in budget["groups"]:
        for cat in group["categories"]:
            assigned = cents(cat["assigned"])
            if assigned <= 0 and not actual_by_category.get(cat["id"]) and not expected_by_category.get(cat["id"]):
                continue
            spent = actual_by_category.get(cat["id"], 0)
            expected = expected_by_category.get(cat["id"], 0)
            projected = spent + expected
            left_after_expected = assigned - projected
            daily_safe = left_after_expected / remaining_days if remaining_days > 0 else left_after_expected
            expected_progress = assigned * elapsed_days / end.day if assigned else 0
            pace_delta = spent - expected_progress
            status = "ok"
            message = "Dentro do ritmo."
            if assigned <= 0 and projected > 0:
                status = "danger"
                message = "Sem meta definida para estes gastos."
            elif projected > assigned:
                status = "danger"
                message = f"Reduza cerca de R$ {(projected - assigned) / 100:.2f} ou mova dinheiro para esta categoria."
            elif daily_safe <= 0 and remaining_days > 0:
                status = "danger"
                message = "Os previstos ja consomem o restante da meta."
            elif pace_delta > max(1000, assigned * 0.15):
                status = "warn"
                message = "Gasto acima do ritmo ideal do mes."
            elif left_after_expected > 0 and remaining_days > 0:
                message = f"Seguro gastar ate R$ {daily_safe / 100:.2f}/dia ate o fim do mes."
            pace.append({
                "category_id": cat["id"],
                "category": cat["name"],
                "group": group["name"],
                "goal": reais(assigned),
                "actual": reais(spent),
                "expected": reais(expected),
                "projected": reais(projected),
                "left_after_expected": reais(left_after_expected),
                "daily_safe": reais(max(0, daily_safe)),
                "pace_delta": reais(pace_delta),
                "status": status,
                "message": message,
            })
    status_rank = {"danger": 0, "warn": 1, "ok": 2}
    pace.sort(key=lambda x: (status_rank.get(x["status"], 9), x["left_after_expected"]))
    return jsonify({
        "month": month,
        "category": category,
        "label": label,
        "goal": reais(goal),
        "actual_total": reais(actual_total),
        "expected_total": reais(expected_total),
        "projected_total": reais(projected_total),
        "remaining_goal": reais(goal - projected_total),
        "elapsed_days": elapsed_days,
        "remaining_days": remaining_days,
        "category_pace": pace,
        "days": days,
    })


@api.get("/health")
def financial_health():
    """Indicadores simples de saude financeira."""
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    accs = Account.query.filter_by(on_budget=True, archived=False).all()
    acc_ids = [a.id for a in accs]
    cash_ids = [a.id for a in accs if a.type != "credit"]
    months = _month_sequence_ending(month, 4)
    history_months = months[:-1]

    def sums_for(mon):
        income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.account_id.in_(acc_ids), Transaction.amount > 0,
            Transaction.transfer_account_id.is_(None),
            func.strftime("%Y-%m", Transaction.date) == mon,
        ).scalar() or 0
        expense = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.account_id.in_(acc_ids), Transaction.amount < 0,
            Transaction.transfer_account_id.is_(None),
            func.strftime("%Y-%m", Transaction.date) == mon,
        ).scalar() or 0
        return int(income), -int(expense)

    cur_income, cur_expense = sums_for(month) if acc_ids else (0, 0)
    hist = [sums_for(mon) for mon in history_months] if acc_ids else []
    avg_income = sum(x[0] for x in hist) / len(hist) if hist else 0
    avg_expense = sum(x[1] for x in hist) / len(hist) if hist else 0
    cash_balance = sum(budget_mod.account_balance(aid) for aid in cash_ids)
    total_balance = sum(budget_mod.account_balance(a.id) for a in accs)

    credit_cards = Account.query.filter_by(type="credit", archived=False).all()
    credit_debt = 0
    credit_limit = 0
    for card in credit_cards:
        bal = budget_mod.account_balance(card.id)
        if bal < 0:
            credit_debt += -bal
        if card.credit_limit:
            credit_limit += card.credit_limit

    fixed_monthly = 0
    for s in ScheduledTransaction.query.filter(
        ScheduledTransaction.active.is_(True),
        ScheduledTransaction.amount < 0,
        ScheduledTransaction.frequency.in_(["weekly", "biweekly", "monthly", "yearly"]),
    ).all():
        multiplier = {"weekly": 52 / 12, "biweekly": 26 / 12, "monthly": 1, "yearly": 1 / 12}.get(s.frequency, 1)
        fixed_monthly += abs(s.amount) * multiplier

    b = budget_mod.budget_for_month(month)
    over = []
    available_total = 0
    for group in b["groups"]:
        for cat in group["categories"]:
            available_total += cents(cat["available"])
            if cat["available"] < 0:
                over.append({"name": cat["name"], "group": group["name"], "available": cat["available"]})

    savings_rate = ((cur_income - cur_expense) / cur_income * 100) if cur_income > 0 else None
    emergency_months = (cash_balance / avg_expense) if avg_expense > 0 else None
    debt_utilization = (credit_debt / credit_limit * 100) if credit_limit > 0 else None
    fixed_ratio = (fixed_monthly / max(avg_income, cur_income) * 100) if max(avg_income, cur_income) > 0 else None

    notes = []
    if savings_rate is not None and savings_rate < 10:
        notes.append("Taxa de poupanca baixa neste mes.")
    if emergency_months is not None and emergency_months < 3:
        notes.append("Reserva abaixo de 3 meses de gastos medios.")
    if debt_utilization is not None and debt_utilization > 50:
        notes.append("Uso de limite de cartao acima de 50%.")
    if over:
        notes.append(f"{len(over)} categoria(s) com saldo negativo.")
    if not notes:
        notes.append("Nenhum sinal critico nos indicadores principais.")

    return jsonify({
        "month": month,
        "cards": {
            "cash_balance": reais(cash_balance),
            "total_balance": reais(total_balance),
            "month_income": reais(cur_income),
            "month_expense": reais(cur_expense),
            "avg_income": reais(avg_income),
            "avg_expense": reais(avg_expense),
            "ready_to_assign": b["ready_to_assign"],
            "budget_available": reais(available_total),
            "credit_debt": reais(credit_debt),
            "credit_limit": reais(credit_limit),
        },
        "indicators": {
            "savings_rate": savings_rate,
            "emergency_months": emergency_months,
            "debt_utilization": debt_utilization,
            "fixed_ratio": fixed_ratio,
        },
        "overbudget": over[:8],
        "notes": notes,
    })


@api.post("/simulator")
def simulator():
    """Simula compra parcelada ou plano de meta usando a previsao atual como base."""
    d = request.get_json(force=True)
    kind = d.get("kind", "purchase")
    months = max(3, min(36, int(d.get("months", 12))))
    base = forecast_mod.forecast(months, True)
    adjusted = [{**p, "delta": 0} for p in base["points"]]

    result = {"kind": kind, "base": base["points"], "adjusted": adjusted, "summary": {}}
    if kind == "purchase":
        amount = cents(d.get("amount", 0))
        installments = max(1, min(48, int(d.get("installments") or 1)))
        monthly = amount // installments
        remainder = amount - monthly * installments
        running_delta = 0
        for idx in range(1, len(adjusted)):
            if idx <= installments:
                charge = monthly + (remainder if idx == 1 else 0)
                running_delta -= charge
            adjusted[idx]["delta"] = reais(running_delta)
            adjusted[idx]["balance"] = adjusted[idx]["balance"] + reais(running_delta)
        result["summary"] = {
            "amount": reais(amount),
            "installments": installments,
            "monthly": reais(monthly),
            "final_impact": reais(running_delta),
            "final_balance": adjusted[-1]["balance"],
        }
    elif kind == "goal":
        goal = cents(d.get("goal_amount", 0))
        monthly = cents(d.get("monthly_amount", 0))
        saved = 0
        hit_month = None
        for idx in range(1, len(adjusted)):
            saved += monthly
            adjusted[idx]["saved"] = reais(saved)
            if not hit_month and goal > 0 and saved >= goal:
                hit_month = adjusted[idx]["month"]
        months_needed = (goal + monthly - 1) // monthly if monthly > 0 and goal > 0 else None
        result["summary"] = {
            "goal_amount": reais(goal),
            "monthly_amount": reais(monthly),
            "saved_in_period": reais(saved),
            "hit_month": hit_month,
            "months_needed": months_needed,
        }
    return jsonify(result)


@api.get("/summary")
def summary():
    """Resumo para o dashboard."""
    acc_ids = [a.id for a in Account.query.filter_by(on_budget=True).all()]
    total = sum(budget_mod.account_balance(a) for a in acc_ids)
    month = date.today().strftime("%Y-%m")
    income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.account_id.in_(acc_ids), Transaction.amount > 0,
        func.strftime("%Y-%m", Transaction.date) == month,
    ).scalar() or 0
    expense = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.account_id.in_(acc_ids), Transaction.amount < 0,
        func.strftime("%Y-%m", Transaction.date) == month,
    ).scalar() or 0
    upcoming = ScheduledTransaction.query.filter_by(active=True).order_by(
        ScheduledTransaction.next_date).limit(5).all()
    return jsonify({
        "total_balance": reais(total),
        "month_income": reais(income),
        "month_expense": reais(-expense),
        "ready_to_assign": reais(budget_mod.ready_to_assign()),
        "upcoming": [sched_to_dict(s) for s in upcoming],
    })


@api.get("/insights/month")
def month_insights():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    acc_ids = [a.id for a in Account.query.filter_by(on_budget=True, archived=False).all()]
    start = date(int(month[:4]), int(month[5:7]), 1)
    end = last_day_of_month(month)
    days_left = max(1, (end - date.today()).days + 1) if month == date.today().strftime("%Y-%m") else end.day

    biggest = Transaction.query.filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.amount < 0,
        func.strftime("%Y-%m", Transaction.date) == month,
    ).order_by(Transaction.amount.asc()).first() if acc_ids else None

    top = db.session.query(
        Category.name, func.coalesce(func.sum(Transaction.amount), 0)
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.amount < 0,
        func.strftime("%Y-%m", Transaction.date) == month,
    ).group_by(Category.id).order_by(func.sum(Transaction.amount)).first() if acc_ids else None

    b = budget_mod.budget_for_month(month)
    positive_available = sum(cents(c["available"]) for g in b["groups"] for c in g["categories"] if c["available"] > 0)
    next_income = ScheduledTransaction.query.filter(
        ScheduledTransaction.active.is_(True),
        ScheduledTransaction.amount > 0,
        ScheduledTransaction.next_date >= date.today(),
    ).order_by(ScheduledTransaction.next_date).first()

    return jsonify({
        "biggest_expense": txn_to_dict(biggest) if biggest else None,
        "top_category": {"name": top[0], "amount": reais(-top[1])} if top else None,
        "days_left": days_left,
        "daily_available": reais(positive_available // days_left),
        "next_income": sched_to_dict(next_income) if next_income else None,
    })


@api.get("/calendar")
def calendar():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    start = date(int(month[:4]), int(month[5:7]), 1)
    end = last_day_of_month(month)
    events = []

    for t in Transaction.query.filter(Transaction.date >= start, Transaction.date <= end).order_by(Transaction.date).all():
        events.append({
            "date": t.date.isoformat(),
            "kind": "transaction",
            "title": t.payee or (t.category.name if t.category else "Lançamento"),
            "detail": t.category.name if t.category else t.account.name,
            "amount": reais(t.amount),
            "view": "transactions",
        })

    for s in ScheduledTransaction.query.filter_by(active=True).filter(
        ScheduledTransaction.next_date >= start,
        ScheduledTransaction.next_date <= end,
    ).order_by(ScheduledTransaction.next_date).all():
        events.append({
            "date": s.next_date.isoformat(),
            "kind": "scheduled",
            "title": s.payee or (s.category.name if s.category else "Previsto"),
            "detail": "Recorrente",
            "amount": reais(s.amount),
            "view": "scheduled",
        })

    for a in Account.query.filter_by(type="credit", archived=False).all():
        for offset in (-1, 0, 1):
            sm = _shift_month(month, offset)
            st = cards_mod.statement(a, sm)
            due = parse_date(st["due_date"])
            remaining = cents(st.get("remaining", 0))
            if start <= due <= end and remaining > 0:
                events.append({
                    "date": due.isoformat(),
                    "kind": "card",
                    "title": f"Fatura {a.name}",
                    "detail": f"Fatura {sm}",
                    "amount": reais(-remaining),
                    "view": "cards",
                })

    events.sort(key=lambda e: (e["date"], e["kind"]))
    return jsonify({"month": month, "events": events})


@api.get("/review")
def weekly_review():
    month = date.today().strftime("%Y-%m")
    acc_ids = [a.id for a in Account.query.filter_by(on_budget=True, archived=False).all()]
    uncategorized = Transaction.query.filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.amount < 0,
        Transaction.category_id.is_(None),
        Transaction.transfer_account_id.is_(None),
    ).order_by(Transaction.date.desc()).limit(10).all() if acc_ids else []
    b = budget_mod.budget_for_month(month)
    over = []
    near = []
    for group in b["groups"]:
        for cat in group["categories"]:
            assigned = cents(cat["assigned"])
            spent = -cents(cat["activity"]) if cat["activity"] < 0 else 0
            item = {"name": cat["name"], "group": group["name"], "available": cat["available"]}
            if cat["available"] < 0:
                over.append(item)
            elif assigned > 0 and spent >= int(assigned * 0.8):
                near.append(item)
    due = ScheduledTransaction.query.filter_by(active=True).filter(
        ScheduledTransaction.next_date <= date.today() + timedelta(days=7)
    ).order_by(ScheduledTransaction.next_date).limit(8).all()
    goals = [g for g in (goal_to_dict(x) for x in CategoryGoal.query.filter_by(archived=False).all())
             if g["remaining"] > 0]
    return jsonify({
        "uncategorized": [txn_to_dict(t) for t in uncategorized],
        "overbudget": over,
        "near_limit": near,
        "due": [sched_to_dict(s) for s in due],
        "goals": goals,
    })


@api.get("/alerts")
def alerts():
    """Alertas práticos para o painel: orçamento, vencimentos e desvios de gasto."""
    today = date.today()
    month = today.strftime("%Y-%m")
    out = []

    def add(kind, level, title, detail="", amount=None, due_date=None, view=None):
        out.append({
            "kind": kind, "level": level, "title": title, "detail": detail,
            "amount": reais(amount) if amount is not None else None,
            "due_date": due_date.isoformat() if due_date else None,
            "view": view,
        })

    rta = budget_mod.ready_to_assign()
    if rta < 0:
        add("budget", "danger", "Pronto para atribuir negativo",
            "Você atribuiu mais dinheiro do que entrou.", rta, view="budget")

    b = budget_mod.budget_for_month(month)
    for group in b["groups"]:
        for cat in group["categories"]:
            assigned = cents(cat["assigned"])
            activity = cents(cat["activity"])
            available = cents(cat["available"])
            spent = -activity if activity < 0 else 0
            full_name = f"{group['name']} › {cat['name']}"
            if available < 0:
                add("category", "danger", f"{cat['name']} estourou",
                    f"{full_name} está abaixo do planejado.", available, view="budget")
            elif assigned > 0 and spent >= int(assigned * 0.8):
                add("category", "warn", f"{cat['name']} perto do limite",
                    f"Já foi usado {round(spent / assigned * 100)}% do valor atribuído.",
                    assigned - spent, view="budget")

    due_limit = today + timedelta(days=7)
    scheduled = ScheduledTransaction.query.filter_by(active=True).filter(
        ScheduledTransaction.next_date <= due_limit
    ).order_by(ScheduledTransaction.next_date).limit(8).all()
    for s in scheduled:
        overdue = s.next_date < today
        title_base = s.payee or (s.category.name if s.category else "Previsto")
        add("scheduled", "danger" if overdue else "warn",
            f"{title_base} {'vencido' if overdue else 'vence em breve'}",
            s.category.name if s.category else "", s.amount, s.next_date, "scheduled")

    for a in Account.query.filter_by(type="credit", archived=False).all():
        st = cards_mod.statement(a, cards_mod.open_statement_month(a))
        remaining = cents(st.get("remaining", 0))
        due = parse_date(st["due_date"])
        if remaining > 0 and due <= due_limit:
            overdue = due < today
            add("card", "danger" if overdue else "warn",
                f"Fatura {a.name} {'vencida' if overdue else 'vence em breve'}",
                f"Fatura de {st['month']}.", remaining, due, "cards")

    for a in Account.query.filter(Account.type != "credit", Account.archived.is_(False)).all():
        bal = budget_mod.account_balance(a.id)
        if bal < 0:
            add("account", "danger", f"{a.name} está negativa",
                "Confira lançamentos recentes ou uma transferência.", bal, view="accounts")

    acc_ids = [a.id for a in Account.query.filter_by(on_budget=True, archived=False).all()]
    if acc_ids:
        prev_months = [_shift_month(month, -i) for i in (1, 2, 3)]
        current = dict(db.session.query(
            Transaction.category_id, func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.account_id.in_(acc_ids),
            Transaction.category_id.isnot(None),
            Transaction.amount < 0,
            func.strftime("%Y-%m", Transaction.date) == month,
        ).group_by(Transaction.category_id).all())
        previous = defaultdict(list)
        rows = db.session.query(
            Transaction.category_id, func.strftime("%Y-%m", Transaction.date),
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.account_id.in_(acc_ids),
            Transaction.category_id.isnot(None),
            Transaction.amount < 0,
            func.strftime("%Y-%m", Transaction.date).in_(prev_months),
        ).group_by(Transaction.category_id, func.strftime("%Y-%m", Transaction.date)).all()
        for cid, _, total in rows:
            previous[cid].append(-int(total))
        cats = {c.id: c for c in Category.query.all()}
        for cid, total in current.items():
            spent = -int(total)
            vals = previous.get(cid, [])
            if not vals:
                continue
            avg = sum(vals) / len(vals)
            if spent >= avg * 1.5 and spent - avg >= 5000:
                c = cats.get(cid)
                if c:
                    add("unusual", "info", f"Gasto acima do normal em {c.name}",
                        f"Média recente: R$ {avg / 100:.2f}.", spent, view="transactions")

    rank = {"danger": 0, "warn": 1, "info": 2}
    out.sort(key=lambda x: (rank.get(x["level"], 9), x["due_date"] or "9999-99-99"))
    return jsonify(out[:12])


# ---------- cartões de crédito / faturas ----------
@api.get("/cards")
def list_cards():
    out = []
    for a in Account.query.filter_by(type="credit", archived=False).all():
        bal = budget_mod.account_balance(a.id)  # negativo = dívida
        debt = -bal if bal < 0 else 0
        open_m = cards_mod.open_statement_month(a)
        st = cards_mod.statement(a, open_m)
        out.append({
            "id": a.id, "name": a.name,
            "debt": reais(debt),
            "credit_limit": reais(a.credit_limit) if a.credit_limit else None,
            "available_limit": reais(a.credit_limit - debt) if a.credit_limit else None,
            "closing_day": a.closing_day, "due_day": a.due_day,
            "open_statement": {"month": st["month"], "total": st["total"],
                               "due_date": st["due_date"], "cycle_end": st["cycle_end"]},
        })
    return jsonify(out)


@api.get("/cards/<int:aid>/statement")
def card_statement(aid):
    a = Account.query.get_or_404(aid)
    month = request.args.get("month") or cards_mod.open_statement_month(a)
    return jsonify(cards_mod.statement(a, month))


@api.post("/cards/<int:aid>/pay")
def pay_card(aid):
    """Paga (total ou parcial) uma fatura: transferência conta -> cartão."""
    card = Account.query.get_or_404(aid)
    d = request.get_json(force=True)
    src_id = d["from_account_id"]
    src = Account.query.get_or_404(src_id)
    amount = cents(d["amount"])
    when = parse_date(d.get("date"))
    month = d["statement_month"]
    if amount <= 0:
        return jsonify({"error": "Valor inválido"}), 400

    # Lado da conta de origem: saída (transferência).
    db.session.add(Transaction(
        account_id=src.id, category_id=None, date=when,
        payee=f"Pagamento fatura {card.name}", amount=-amount,
        cleared=True, transfer_account_id=card.id,
    ))
    # Lado do cartão: entrada que abate a dívida, marcada com a fatura quitada.
    db.session.add(Transaction(
        account_id=card.id, category_id=None, date=when,
        payee=f"Pagamento recebido de {src.name}", amount=amount,
        cleared=True, transfer_account_id=src.id, statement_month=month,
    ))
    db.session.commit()
    return jsonify({"ok": True})


# ---------- patrimônio líquido ----------
@api.get("/networth")
def get_networth():
    months = int(request.args.get("months", 12))
    return jsonify({
        "breakdown": networth_mod.current_breakdown(),
        "history": networth_mod.history(months),
    })


@api.get("/networth/items")
def list_nw_items():
    items = NetWorthItem.query.filter_by(archived=False).order_by(
        NetWorthItem.kind, NetWorthItem.sort_order).all()
    out = []
    for it in items:
        snaps = sorted(it.snapshots, key=lambda s: s.month)
        latest = snaps[-1] if snaps else None
        out.append({
            "id": it.id, "name": it.name, "kind": it.kind,
            "category": it.category,
            "latest_month": latest.month if latest else None,
            "latest_value": reais(latest.value) if latest else None,
            "snapshots": [{"month": s.month, "value": reais(s.value)} for s in snaps],
        })
    return jsonify(out)


@api.post("/networth/items")
def create_nw_item():
    d = request.get_json(force=True)
    it = NetWorthItem(
        name=d.get("name", "Item"),
        kind=d.get("kind", "asset"),
        category=d.get("category", ""),
        sort_order=NetWorthItem.query.count(),
    )
    db.session.add(it)
    db.session.flush()
    # valor inicial opcional, no mês informado (padrão: mês atual)
    if d.get("value") not in (None, ""):
        month = d.get("month") or date.today().strftime("%Y-%m")
        db.session.add(NetWorthSnapshot(item_id=it.id, month=month, value=cents(d["value"])))
    db.session.commit()
    return jsonify({"id": it.id}), 201


@api.put("/networth/items/<int:iid>")
def update_nw_item(iid):
    it = NetWorthItem.query.get_or_404(iid)
    d = request.get_json(force=True)
    if "name" in d: it.name = d["name"]
    if "kind" in d: it.kind = d["kind"]
    if "category" in d: it.category = d["category"]
    if "archived" in d: it.archived = bool(d["archived"])
    db.session.commit()
    return jsonify({"ok": True})


@api.delete("/networth/items/<int:iid>")
def delete_nw_item(iid):
    it = NetWorthItem.query.get_or_404(iid)
    db.session.delete(it)
    db.session.commit()
    return jsonify({"ok": True})


@api.post("/networth/items/<int:iid>/snapshot")
def set_nw_snapshot(iid):
    """Define (ou atualiza) o valor de um item em um mês."""
    NetWorthItem.query.get_or_404(iid)
    d = request.get_json(force=True)
    month = d.get("month") or date.today().strftime("%Y-%m")
    val = cents(d.get("value", 0))
    snap = NetWorthSnapshot.query.filter_by(item_id=iid, month=month).first()
    if snap:
        snap.value = val
    else:
        db.session.add(NetWorthSnapshot(item_id=iid, month=month, value=val))
    db.session.commit()
    return jsonify({"ok": True})


@api.delete("/networth/items/<int:iid>/snapshot/<month>")
def delete_nw_snapshot(iid, month):
    snap = NetWorthSnapshot.query.filter_by(item_id=iid, month=month).first()
    if snap:
        db.session.delete(snap)
        db.session.commit()
    return jsonify({"ok": True})


# ---------- importação ----------
@api.post("/import/preview")
def import_preview():
    account_id = int(request.form["account_id"])
    f = request.files["file"]
    data = f.read()
    try:
        items = importer.parse_file(f.filename, data, account_id)
    except Exception as e:  # noqa
        return jsonify({"error": f"Não consegui ler o arquivo: {e}"}), 400
    existing = {h for (h,) in db.session.query(Transaction.import_hash)
                .filter(Transaction.import_hash.isnot(None)).all()}
    out = []
    for it in items:
        out.append({
            "date": it["date"].isoformat(),
            "payee": it["payee"],
            "amount": reais(it["amount"]),
            "import_hash": it["import_hash"],
            "duplicate": it["import_hash"] in existing,
        })
    return jsonify({"items": out, "account_id": account_id})


@api.post("/import/commit")
def import_commit():
    d = request.get_json(force=True)
    account_id = d["account_id"]
    items = d["items"]  # lista de {date, payee, amount, category_id, import_hash}
    existing = {h for (h,) in db.session.query(Transaction.import_hash)
                .filter(Transaction.import_hash.isnot(None)).all()}
    added = 0
    for it in items:
        h = it.get("import_hash")
        if h and h in existing:
            continue
        db.session.add(Transaction(
            account_id=account_id,
            category_id=it.get("category_id") or None,
            date=parse_date(it["date"]),
            payee=it.get("payee", ""),
            amount=cents(it["amount"]),
            cleared=True,
            import_hash=h,
        ))
        if h:
            existing.add(h)
        added += 1
    db.session.commit()
    return jsonify({"added": added})
