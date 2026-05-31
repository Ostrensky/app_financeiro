"""
networth.py — Patrimônio líquido (ativos − passivos) e sua evolução mensal.

Duas fontes de dados se combinam:

1) CONTAS (automático): o saldo de cada conta já existente entra direto.
   - saldo positivo  -> ativo (conta corrente, poupança, investimento, dinheiro)
   - saldo negativo  -> passivo (cartão de crédito com fatura em aberto)
   O saldo de conta é sempre o de HOJE (não temos histórico de saldo por mês),
   então ele aparece no mês corrente e nos meses sem snapshot é estimado como o atual.

2) ITENS MANUAIS (NetWorthItem + NetWorthSnapshot): imóvel, carro, financiamento…
   Você informa o valor de cada mês. Entre meses sem registro, repetimos o último
   valor conhecido (carry-forward), que é o comportamento natural para patrimônio.
"""

from datetime import date
from sqlalchemy import func
from models import db, Account, NetWorthItem, NetWorthSnapshot
import budget as budget_mod


def _month_range(n_back: int):
    """Lista dos últimos n meses (YYYY-MM), do mais antigo ao atual."""
    today = date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(n_back):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    out.reverse()
    return out


def _accounts_split():
    """Saldos atuais das contas separados em ativos e passivos (centavos)."""
    assets, liabilities = [], []
    for a in Account.query.filter_by(archived=False).all():
        bal = budget_mod.account_balance(a.id)
        if bal >= 0:
            assets.append({"id": f"acc-{a.id}", "name": a.name, "value": bal,
                           "category": "Contas", "source": "account"})
        else:
            liabilities.append({"id": f"acc-{a.id}", "name": a.name, "value": -bal,
                                "category": "Cartões/Dívidas", "source": "account"})
    return assets, liabilities


def _item_value_for_month(item, month, snap_cache):
    """Valor de um item no mês: usa o snapshot do mês; senão, o último anterior."""
    snaps = snap_cache.get(item.id, [])
    val = None
    for s in snaps:  # já vem ordenado por mês ascendente
        if s.month <= month:
            val = s.value
        else:
            break
    return val  # None = nunca teve valor até esse mês


def current_breakdown():
    """Composição do patrimônio HOJE: lista de ativos e passivos com totais."""
    month = date.today().strftime("%Y-%m")
    assets, liabilities = _accounts_split()

    snap_cache = {}
    for it in NetWorthItem.query.filter_by(archived=False).all():
        snap_cache[it.id] = sorted(it.snapshots, key=lambda s: s.month)

    for it in NetWorthItem.query.filter_by(archived=False).all():
        v = _item_value_for_month(it, month, snap_cache)
        if v is None:
            continue
        entry = {"id": f"item-{it.id}", "name": it.name, "value": v,
                 "category": it.category or ("Ativos" if it.kind == "asset" else "Passivos"),
                 "source": "item"}
        (assets if it.kind == "asset" else liabilities).append(entry)

    total_assets = sum(a["value"] for a in assets)
    total_liab = sum(l["value"] for l in liabilities)
    return {
        "assets": sorted(assets, key=lambda x: -x["value"]),
        "liabilities": sorted(liabilities, key=lambda x: -x["value"]),
        "total_assets": total_assets / 100,
        "total_liabilities": total_liab / 100,
        "net_worth": (total_assets - total_liab) / 100,
    }


def history(months_back=12):
    """Série mensal de ativos, passivos e patrimônio líquido (em reais)."""
    months = _month_range(months_back)
    current_month = date.today().strftime("%Y-%m")

    # saldo atual das contas (aplicado a todos os meses, pois não há histórico de saldo)
    acc_assets, acc_liab = _accounts_split()
    acc_asset_total = sum(a["value"] for a in acc_assets)
    acc_liab_total = sum(l["value"] for l in acc_liab)

    snap_cache = {}
    items = NetWorthItem.query.filter_by(archived=False).all()
    for it in items:
        snap_cache[it.id] = sorted(it.snapshots, key=lambda s: s.month)

    points = []
    for mon in months:
        a_total = acc_asset_total
        l_total = acc_liab_total
        for it in items:
            v = _item_value_for_month(it, mon, snap_cache)
            if v is None:
                continue
            if it.kind == "asset":
                a_total += v
            else:
                l_total += v
        points.append({
            "month": mon,
            "assets": a_total / 100,
            "liabilities": l_total / 100,
            "net_worth": (a_total - l_total) / 100,
        })
    return {"points": points, "current_month": current_month}
