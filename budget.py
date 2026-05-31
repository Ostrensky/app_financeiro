"""
budget.py — Cálculos do orçamento no estilo YNAB.

Conceitos:
- "Pronto para Atribuir": dinheiro que entrou nas contas do orçamento e ainda
  não foi distribuído em nenhuma categoria. (global, somando todos os meses)
- Por categoria/mês: Disponível = soma acumulada de (atribuído + atividade)
  desde o começo até aquele mês. Saldo positivo "rola" para o mês seguinte.
"""

from collections import defaultdict
from sqlalchemy import func
from models import db, Account, Category, CategoryGroup, Transaction, BudgetAllocation


def months_until(month: str):
    """Lista de meses 'YYYY-MM' do início dos tempos até 'month' (inclusive)."""
    # Pega o primeiro mês com qualquer movimentação; senão usa o próprio mês.
    first_alloc = db.session.query(func.min(BudgetAllocation.month)).scalar()
    first_txn = db.session.query(func.min(Transaction.date)).scalar()
    candidates = []
    if first_alloc:
        candidates.append(first_alloc)
    if first_txn:
        candidates.append(first_txn.strftime("%Y-%m"))
    start = min(candidates) if candidates else month
    start = min(start, month)
    y, m = int(start[:4]), int(start[5:7])
    ty, tm = int(month[:4]), int(month[5:7])
    out = []
    while (y, m) <= (ty, tm):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _on_budget_account_ids():
    return [a.id for a in Account.query.filter_by(on_budget=True, archived=False).all()]


def ready_to_assign() -> int:
    """
    Dinheiro disponível para atribuir (em centavos), global.
    = saldo inicial das contas do orçamento
      + toda entrada SEM categoria (renda 'Pronto para Atribuir')
      - tudo que já foi atribuído a categorias.
    """
    acc_ids = _on_budget_account_ids()
    if not acc_ids:
        return 0
    starting = db.session.query(func.coalesce(func.sum(Account.starting_balance), 0)) \
        .filter(Account.id.in_(acc_ids)).scalar() or 0
    # Entradas não categorizadas (renda) nas contas do orçamento.
    income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)) \
        .filter(Transaction.account_id.in_(acc_ids)) \
        .filter(Transaction.category_id.is_(None)) \
        .filter(Transaction.amount > 0) \
        .filter(Transaction.transfer_account_id.is_(None)) \
        .scalar() or 0
    assigned = db.session.query(func.coalesce(func.sum(BudgetAllocation.assigned), 0)).scalar() or 0
    return int(starting) + int(income) - int(assigned)


def category_activity(month: str):
    """Soma das transações por categoria DENTRO do mês (centavos, negativo = gasto)."""
    acc_ids = _on_budget_account_ids()
    rows = db.session.query(
        Transaction.category_id,
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.category_id.isnot(None),
        func.strftime("%Y-%m", Transaction.date) == month,
    ).group_by(Transaction.category_id).all()
    return {cid: int(total) for cid, total in rows}


def budget_for_month(month: str):
    """
    Monta a visão completa do orçamento do mês: grupos -> categorias com
    atribuído, atividade e disponível (com rollover dos meses anteriores).
    """
    all_months = months_until(month)

    # Atribuído por (categoria, mês)
    allocs = defaultdict(int)
    for a in BudgetAllocation.query.filter(BudgetAllocation.month.in_(all_months)).all():
        allocs[(a.category_id, a.month)] = a.assigned

    # Atividade por (categoria, mês)
    activity_by_month = {m: category_activity(m) for m in all_months}

    groups_out = []
    total_assigned = total_activity = total_available = 0

    groups = CategoryGroup.query.order_by(CategoryGroup.sort_order).all()
    for g in groups:
        cats_out = []
        cats = [c for c in sorted(g.categories, key=lambda c: c.sort_order) if not c.archived]
        for c in cats:
            # Disponível = acumulado de (atribuído + atividade) até o mês atual.
            available = 0
            for m in all_months:
                available += allocs.get((c.id, m), 0)
                available += activity_by_month[m].get(c.id, 0)

            assigned = allocs.get((c.id, month), 0)
            activity = activity_by_month[month].get(c.id, 0)
            cats_out.append({
                "id": c.id,
                "name": c.name,
                "assigned": assigned / 100,
                "activity": activity / 100,
                "available": available / 100,
            })
            total_assigned += assigned
            total_activity += activity
            total_available += available
        groups_out.append({
            "id": g.id,
            "name": g.name,
            "categories": cats_out,
        })

    return {
        "month": month,
        "ready_to_assign": ready_to_assign() / 100,
        "groups": groups_out,
        "totals": {
            "assigned": total_assigned / 100,
            "activity": total_activity / 100,
            "available": total_available / 100,
        },
    }


def account_balance(account_id: int) -> int:
    """Saldo atual da conta (centavos) = saldo inicial + soma das transações."""
    acc = Account.query.get(account_id)
    if not acc:
        return 0
    s = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)) \
        .filter(Transaction.account_id == account_id).scalar() or 0
    return int(acc.starting_balance) + int(s)
