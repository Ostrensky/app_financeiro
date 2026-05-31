"""
importer.py — Importação semiautomática de extratos.

Suporta:
- OFX (.ofx) — formato que a maioria dos bancos brasileiros exporta.
- CSV — com detecção flexível das colunas de data, descrição e valor.

A ideia é você baixar o extrato do app do banco, jogar aqui e revisar/categorizar.
Cada transação ganha um 'import_hash' para não duplicar se você importar de novo.
"""

import csv
import hashlib
import io
from datetime import datetime, date


def _hash(account_id, dt, amount_cents, payee):
    raw = f"{account_id}|{dt}|{amount_cents}|{(payee or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _to_cents(value):
    """Converte string de valor em centavos. Aceita '1.234,56', '1234.56', '-50,00'."""
    if isinstance(value, (int, float)):
        return int(round(float(value) * 100))
    s = str(value).strip()
    if not s:
        return 0
    neg = s.startswith("-") or "(" in s
    s = s.replace("(", "").replace(")", "").replace("R$", "").replace(" ", "")
    s = s.lstrip("+-")
    # Formato brasileiro: 1.234,56  -> ponto é milhar, vírgula é decimal
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        cents = int(round(float(s) * 100))
    except ValueError:
        cents = 0
    return -cents if neg else cents


def parse_ofx(file_bytes, account_id):
    from ofxparse import OfxParser
    ofx = OfxParser.parse(io.BytesIO(file_bytes))
    out = []
    for acct in ofx.accounts:
        for t in acct.statement.transactions:
            dt = t.date.date() if hasattr(t.date, "date") else t.date
            cents = int(round(float(t.amount) * 100))
            payee = (t.payee or t.memo or "").strip()
            out.append({
                "account_id": account_id,
                "date": dt,
                "payee": payee,
                "memo": (t.memo or "").strip(),
                "amount": cents,
                "import_hash": _hash(account_id, dt, cents, payee),
            })
    return out


def _detect(headers, options):
    low = [h.lower().strip() for h in headers]
    for i, h in enumerate(low):
        for opt in options:
            if opt in h:
                return i
    return None


def parse_csv(file_bytes, account_id):
    text = file_bytes.decode("utf-8-sig", errors="replace")
    # Detecta o separador (vírgula ou ponto e vírgula)
    sample = text[:2000]
    delim = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = list(reader)
    if not rows:
        return []
    headers = rows[0]
    i_date = _detect(headers, ["data", "date"])
    i_desc = _detect(headers, ["desc", "histó", "histo", "memo", "lançamento", "lancamento", "payee", "estabelecimento"])
    i_val = _detect(headers, ["valor", "amount", "value", "montante"])
    i_in = _detect(headers, ["entrada", "crédito", "credito", "credit"])
    i_out = _detect(headers, ["saída", "saida", "débito", "debito", "debit"])

    out = []
    for r in rows[1:]:
        if not r or all(not c.strip() for c in r):
            continue
        # Data
        dt = None
        if i_date is not None and i_date < len(r):
            dt = _parse_date(r[i_date])
        if not dt:
            continue
        # Valor
        if i_val is not None and i_val < len(r):
            cents = _to_cents(r[i_val])
        else:
            inc = _to_cents(r[i_in]) if (i_in is not None and i_in < len(r)) else 0
            out_v = _to_cents(r[i_out]) if (i_out is not None and i_out < len(r)) else 0
            cents = abs(inc) - abs(out_v)
        payee = r[i_desc].strip() if (i_desc is not None and i_desc < len(r)) else ""
        out.append({
            "account_id": account_id,
            "date": dt,
            "payee": payee,
            "memo": "",
            "amount": cents,
            "import_hash": _hash(account_id, dt, cents, payee),
        })
    return out


def _parse_date(s):
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_file(filename, file_bytes, account_id):
    name = (filename or "").lower()
    if name.endswith(".ofx"):
        return parse_ofx(file_bytes, account_id)
    return parse_csv(file_bytes, account_id)
