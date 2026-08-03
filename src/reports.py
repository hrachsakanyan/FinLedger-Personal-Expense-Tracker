"""Summaries, breakdowns and exports built on top of a loaded ledger.

Nothing here touches the disk except :func:`export_csv`; every function takes
plain lists/dicts so it is easy to unit test.
"""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

try:  # works both as "python src/main.py" and as "from src import reports"
    from storage import (
        MONTH_FORMAT,
        StorageError,
        filter_transactions,
        parse_month,
        sort_transactions,
    )
except ImportError:  # pragma: no cover - import fallback
    from .storage import (
        MONTH_FORMAT,
        StorageError,
        filter_transactions,
        parse_month,
        sort_transactions,
    )

CURRENCY = "AMD"


# --------------------------------------------------------------------------
# money helpers
# --------------------------------------------------------------------------

def _round(value) -> float:
    """Round a Decimal/float to 2 decimals, half up (how money is rounded)."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def total(transactions) -> float:
    """Sum amounts using Decimal so 0.1 + 0.2 does not become 0.30000000000000004."""
    result = sum((Decimal(str(t["amount"])) for t in transactions), Decimal("0"))
    return _round(result)


def format_money(value, currency=CURRENCY) -> str:
    """``1234.5`` -> ``'1,234.50 AMD'``."""
    return f"{_round(value):,.2f} {currency}".strip()


# --------------------------------------------------------------------------
# core numbers
# --------------------------------------------------------------------------

def totals(transactions) -> dict:
    """Income, expense and balance for a list of transactions."""
    income = total([t for t in transactions if t["type"] == "income"])
    expense = total([t for t in transactions if t["type"] == "expense"])
    return {
        "income": income,
        "expense": expense,
        "balance": _round(Decimal(str(income)) - Decimal(str(expense))),
        "count": len(transactions),
    }


def balance(transactions) -> float:
    """Income minus expenses."""
    return totals(transactions)["balance"]


def monthly_summary(transactions) -> list:
    """One row per month, oldest first.

    Returns ``[{"month": "2026-08", "income": .., "expense": .., "balance": ..,
    "count": ..}, ...]``.
    """
    buckets: dict[str, list] = {}
    for transaction in transactions:
        buckets.setdefault(transaction["date"][:7], []).append(transaction)

    rows = []
    for month in sorted(buckets):
        row = {"month": month}
        row.update(totals(buckets[month]))
        rows.append(row)
    return rows


def category_breakdown(transactions, tx_type="expense") -> list:
    """Totals per category for one transaction type, biggest first.

    Each row is ``{"category": .., "total": .., "count": .., "share": ..}``
    where ``share`` is the percentage of the type's grand total.
    """
    selected = [t for t in transactions if t["type"] == tx_type]
    grand_total = total(selected)

    buckets: dict[str, list] = {}
    for transaction in selected:
        buckets.setdefault(transaction["category"], []).append(transaction)

    rows = []
    for category, items in buckets.items():
        subtotal = total(items)
        share = _round(subtotal / grand_total * 100) if grand_total else 0.0
        rows.append(
            {
                "category": category,
                "total": subtotal,
                "count": len(items),
                "share": share,
            }
        )
    rows.sort(key=lambda row: (-row["total"], row["category"]))
    return rows


def budget_status(data, month=None) -> list:
    """Compare this month's spending against the configured budget limits."""
    month = parse_month(month) if month else datetime.now().strftime(MONTH_FORMAT)
    rows = []
    for category, limit in sorted(data.get("budgets", {}).items()):
        spent = total(filter_transactions(data, tx_type="expense",
                                          category=category, month=month))
        rows.append(
            {
                "category": category,
                "month": month,
                "limit": limit,
                "spent": spent,
                "left": _round(Decimal(str(limit)) - Decimal(str(spent))),
                "used": _round(spent / limit * 100) if limit else 0.0,
                "over": spent > limit,
            }
        )
    return rows


def budget_alert(data, category, month=None) -> str | None:
    """Return a warning line if ``category`` is near or over its budget."""
    for row in budget_status(data, month):
        if row["category"] != category:
            continue
        if row["over"]:
            return (
                f"! Over budget for '{category}' in {row['month']}: "
                f"{format_money(row['spent'])} of {format_money(row['limit'])} "
                f"({row['used']:.0f}%)"
            )
        if row["used"] >= 80:
            return (
                f"~ {row['used']:.0f}% of the '{category}' budget used in "
                f"{row['month']} ({format_money(row['left'])} left)"
            )
    return None


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def render_table(headers, rows) -> str:
    """Render a list of row-lists as a plain text table."""
    if not rows:
        return "(nothing to show)"

    table = [[str(cell) for cell in row] for row in rows]
    widths = [len(str(h)) for h in headers]
    for row in table:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells):
        return "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    out = [line(headers), "  ".join("-" * width for width in widths)]
    out.extend(line(row) for row in table)
    return "\n".join(out)


def render_transactions(transactions) -> str:
    """The standard transaction table used by list/search."""
    rows = [
        [
            t["id"],
            t["date"],
            t["type"],
            t["category"],
            f"{t['amount']:,.2f}",
            t["note"],
        ]
        for t in sort_transactions(transactions)
    ]
    table = render_table(["ID", "DATE", "TYPE", "CATEGORY", "AMOUNT", "NOTE"], rows)
    if not rows:
        return table
    summary = totals(transactions)
    return (
        f"{table}\n\n"
        f"{len(rows)} transaction(s) | "
        f"income {format_money(summary['income'])} | "
        f"expense {format_money(summary['expense'])} | "
        f"balance {format_money(summary['balance'])}"
    )


def render_monthly_summary(transactions) -> str:
    rows = [
        [
            row["month"],
            f"{row['income']:,.2f}",
            f"{row['expense']:,.2f}",
            f"{row['balance']:,.2f}",
            row["count"],
        ]
        for row in monthly_summary(transactions)
    ]
    return render_table(["MONTH", "INCOME", "EXPENSE", "BALANCE", "COUNT"], rows)


def render_category_breakdown(transactions, tx_type="expense") -> str:
    rows = []
    for row in category_breakdown(transactions, tx_type):
        bar = "#" * int(round(row["share"] / 5))  # one '#' per 5%
        rows.append(
            [row["category"], f"{row['total']:,.2f}", f"{row['share']:.1f}%",
             row["count"], bar]
        )
    return render_table(["CATEGORY", "TOTAL", "SHARE", "COUNT", ""], rows)


def render_budget_status(data, month=None) -> str:
    rows = [
        [
            row["category"],
            f"{row['spent']:,.2f}",
            f"{row['limit']:,.2f}",
            f"{row['left']:,.2f}",
            f"{row['used']:.0f}%",
            "OVER" if row["over"] else "ok",
        ]
        for row in budget_status(data, month)
    ]
    return render_table(
        ["CATEGORY", "SPENT", "LIMIT", "LEFT", "USED", "STATUS"], rows
    )


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------

CSV_FIELDS = ["id", "date", "type", "category", "amount", "note", "created_at"]


def export_csv(transactions, path) -> Path:
    """Write the given transactions to ``path`` as CSV and return the path."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for transaction in sort_transactions(transactions):
                writer.writerow({key: transaction.get(key, "") for key in CSV_FIELDS})
    except OSError as exc:
        raise StorageError(f"Could not write {path}: {exc}") from exc
    return path
