"""
forecast.py — Previsão de orçamento.

Combina duas fontes para projetar os próximos meses:
1) Lançamentos previstos/recorrentes (ScheduledTransaction) — o que você SABE que vai acontecer.
2) Média de gastos por categoria nos últimos meses — o padrão histórico.

Retorna a trajetória de saldo projetada + detalhamento por categoria.
"""

from datetime import date
from collections import defaultdict
from sqlalchemy import func
from models import db, Account, Transaction, ScheduledTransaction
from budget import account_balance, _on_budget_account_ids


def _add_months(y, m, k):
    total = (y * 12 + (m - 1)) + k
    return total // 12, total % 12 + 1


def _last_day(y, m):
    if m == 12:
        return date(y, 12, 31)
    return date(y, m + 1, 1).fromordinal(date(y, m + 1, 1).toordinal() - 1)


def _occurrences_in_month(sched, y, m):
    """Quantas vezes um lançamento recorrente cai dentro de um mês específico."""
    start = date(y, m, 1)
    end = _last_day(y, m)
    if sched.next_date > end:
        return 0
    freq = sched.frequency
    if freq == "once":
        return 1 if start <= sched.next_date <= end else 0
    if freq == "monthly":
        return 1 if sched.next_date <= end else 0
    if freq == "yearly":
        return 1 if (sched.next_date.month == m and sched.next_date <= end) else 0
    if freq in ("weekly", "biweekly"):
        step = 7 if freq == "weekly" else 14
        d = sched.next_date
        count = 0
        # avança até a janela do mês
        while d < start:
            d = date.fromordinal(d.toordinal() + step)
        while d <= end:
            count += 1
            d = date.fromordinal(d.toordinal() + step)
        return count
    return 0


def average_spending(months_back=3):
    """Média mensal de gasto por categoria (centavos, negativo) nos últimos N meses."""
    acc_ids = _on_budget_account_ids()
    if not acc_ids:
        return {}
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(months_back):
        y, m = _add_months(y, m, -1)
        months.append(f"{y:04d}-{m:02d}")
    totals = defaultdict(int)
    rows = db.session.query(
        Transaction.category_id,
        func.coalesce(func.sum(Transaction.amount), 0),
    ).filter(
        Transaction.account_id.in_(acc_ids),
        Transaction.category_id.isnot(None),
        Transaction.amount < 0,
        func.strftime("%Y-%m", Transaction.date).in_(months),
    ).group_by(Transaction.category_id).all()
    for cid, total in rows:
        totals[cid] = int(total) / months_back
    return totals


def forecast(months_ahead=6, use_average=True):
    """Projeta saldo total das contas do orçamento para os próximos meses."""
    acc_ids = _on_budget_account_ids()
    current = sum(account_balance(a) for a in acc_ids)  # centavos

    scheduled = ScheduledTransaction.query.filter_by(active=True).all()
    avg = average_spending() if use_average else {}
    # Não contar duas vezes: categorias que já têm recorrência não usam a média.
    sched_cats = {s.category_id for s in scheduled if s.category_id}

    today = date.today()
    y, m = today.year, today.month
    points = [{
        "month": f"{y:04d}-{m:02d}",
        "label": "Hoje",
        "balance": current / 100,
        "income": 0,
        "expense": 0,
    }]

    running = current
    for i in range(1, months_ahead + 1):
        ny, nm = _add_months(y, m, i)
        income = expense = 0
        for s in scheduled:
            occ = _occurrences_in_month(s, ny, nm)
            if occ:
                val = s.amount * occ
                if val >= 0:
                    income += val
                else:
                    expense += val
        if use_average:
            for cid, val in avg.items():
                if cid not in sched_cats:
                    expense += int(val)  # val já é negativo
        running += income + expense
        points.append({
            "month": f"{ny:04d}-{nm:02d}",
            "label": f"{nm:02d}/{ny}",
            "balance": running / 100,
            "income": income / 100,
            "expense": expense / 100,
        })

    return {
        "current_balance": current / 100,
        "points": points,
        "used_average": use_average,
    }
