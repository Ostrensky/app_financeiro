"""
cards.py — Lógica de cartão de crédito e fatura.

Como funciona o modelo:
- Um cartão é uma conta do tipo 'credit', com dia de fechamento e dia de vencimento.
- Compras no cartão são lançamentos normais (valor negativo) e já entram na categoria
  escolhida — o orçamento "sente" o gasto na hora (filosofia YNAB: orce quando gasta).
- O saldo do cartão é negativo = quanto você DEVE no total.
- A FATURA agrupa as compras de um ciclo de fechamento.
- Pagar a fatura é uma TRANSFERÊNCIA da conta corrente para o cartão (dois lançamentos
  ligados). O lançamento do lado do cartão é marcado com statement_month, indicando
  qual fatura ele quita.
"""

from datetime import date, timedelta
from sqlalchemy import func
from models import db, Account, Transaction


def _last_day(y, m):
    if m == 12:
        return 31
    return (date(y, m + 1, 1) - timedelta(days=1)).day


def _clamp(y, m, day):
    return date(y, m, min(day or 1, _last_day(y, m)))


def _prev_month(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def _next_month(y, m):
    return (y + 1, 1) if m == 12 else (y, m + 1)


def open_statement_month(account, ref=None):
    """Qual fatura (YYYY-MM) está aberta hoje — onde caem as compras atuais."""
    ref = ref or date.today()
    closing = account.closing_day or 28
    close_this = _clamp(ref.year, ref.month, closing)
    if ref <= close_this:
        y, m = ref.year, ref.month
    else:
        y, m = _next_month(ref.year, ref.month)
    return f"{y:04d}-{m:02d}"


def statement(account, closing_month):
    """
    Monta a fatura que FECHA no mês informado (YYYY-MM):
    período, data de vencimento, compras, total e status de pagamento.
    """
    y, m = int(closing_month[:4]), int(closing_month[5:7])
    closing = account.closing_day or 28
    due = account.due_day or closing

    cycle_end = _clamp(y, m, closing)
    py, pm = _prev_month(y, m)
    cycle_start = _clamp(py, pm, closing) + timedelta(days=1)

    # Vencimento: se o dia de vencimento <= dia de fechamento, vence no mês seguinte.
    if due > closing:
        due_date = _clamp(y, m, due)
    else:
        ny, nm = _next_month(y, m)
        due_date = _clamp(ny, nm, due)

    # Compras do ciclo (exclui pagamentos/transferências).
    txns = Transaction.query.filter(
        Transaction.account_id == account.id,
        Transaction.transfer_account_id.is_(None),
        Transaction.date >= cycle_start,
        Transaction.date <= cycle_end,
    ).order_by(Transaction.date).all()
    total = -sum(t.amount for t in txns)  # positivo = valor devido

    # Pagamentos marcados para esta fatura.
    paid_amount = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.account_id == account.id,
        Transaction.statement_month == closing_month,
    ).scalar() or 0

    return {
        "month": closing_month,
        "cycle_start": cycle_start.isoformat(),
        "cycle_end": cycle_end.isoformat(),
        "due_date": due_date.isoformat(),
        "total": total / 100,
        "paid": paid_amount / 100,
        "remaining": (total - paid_amount) / 100,
        "is_paid": total > 0 and paid_amount >= total,
        "transactions": [{
            "id": t.id, "date": t.date.isoformat(),
            "payee": t.payee, "amount": t.amount / 100,
            "installment_num": t.installment_num, "installment_total": t.installment_total,
            "category_name": t.category.name if t.category else None,
        } for t in txns],
    }
