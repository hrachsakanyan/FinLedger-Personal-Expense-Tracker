"""Persistence and CRUD logic for FinLedger.

The whole ledger lives in a single JSON document::

    {
      "version": 1,
      "next_id": 4,
      "budgets": {"food": 300.0},
      "transactions": [
        {
          "id": 1,
          "type": "expense",
          "amount": 12.5,
          "category": "food",
          "date": "2026-08-02",
          "note": "lunch",
          "created_at": "2026-08-02T14:31:05"
        }
      ]
    }

Amounts are always positive numbers; the sign is implied by ``type``.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

SCHEMA_VERSION = 1

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "transactions.json"

TYPES = ("income", "expense")

# Suggested categories only - the user may type anything else.
DEFAULT_CATEGORIES = [
    "food",
    "transport",
    "medical",
    "housing",
    "utilities",
    "entertainment",
    "education",
    "salary",
    "gift",
    "other",
]

DATE_FORMAT = "%Y-%m-%d"
MONTH_FORMAT = "%Y-%m"


class FinLedgerError(Exception):
    """Base class for every error this app raises on purpose."""


class ValidationError(FinLedgerError):
    """Raised when user supplied data does not make sense."""


class StorageError(FinLedgerError):
    """Raised when the JSON file cannot be read or written."""


class TransactionNotFound(FinLedgerError):
    """Raised when an id does not exist in the ledger."""


# --------------------------------------------------------------------------
# validation helpers
# --------------------------------------------------------------------------

def parse_amount(value) -> float:
    """Return ``value`` as a positive amount rounded to 2 decimals.

    Accepts ``"12"``, ``"12.5"``, ``"12,5"``, ints and floats.
    """
    if isinstance(value, bool):  # bool is an int subclass - reject it early
        raise ValidationError("Amount must be a number.")
    text = str(value).strip().replace(",", ".")
    if not text:
        raise ValidationError("Amount cannot be empty.")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValidationError(f"'{value}' is not a valid number.") from None
    if not amount.is_finite():
        raise ValidationError("Amount must be a finite number.")
    if amount <= 0:
        raise ValidationError("Amount must be greater than 0.")
    if amount >= Decimal("1e12"):
        raise ValidationError("Amount is unrealistically large.")
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_type(value) -> str:
    """Normalize a transaction type. ``i``/``e`` shortcuts are allowed."""
    text = str(value).strip().lower()
    shortcuts = {"i": "income", "e": "expense", "+": "income", "-": "expense"}
    text = shortcuts.get(text, text)
    if text not in TYPES:
        raise ValidationError("Type must be 'income' or 'expense'.")
    return text


def parse_date(value=None) -> str:
    """Return an ISO ``YYYY-MM-DD`` string. Empty input means today."""
    if value is None or str(value).strip() == "":
        return date.today().strftime(DATE_FORMAT)
    if isinstance(value, datetime):
        return value.date().strftime(DATE_FORMAT)
    if isinstance(value, date):
        return value.strftime(DATE_FORMAT)
    text = str(value).strip()
    if text.lower() in ("today", "now"):
        return date.today().strftime(DATE_FORMAT)
    try:
        return datetime.strptime(text, DATE_FORMAT).date().strftime(DATE_FORMAT)
    except ValueError:
        raise ValidationError(
            f"'{value}' is not a valid date. Use YYYY-MM-DD (e.g. 2026-08-02)."
        ) from None


def parse_month(value) -> str:
    """Return a ``YYYY-MM`` string, accepting ``YYYY-MM`` or a full date."""
    text = str(value).strip()
    if not text:
        raise ValidationError("Month cannot be empty.")
    for fmt in (MONTH_FORMAT, DATE_FORMAT):
        try:
            return datetime.strptime(text, fmt).strftime(MONTH_FORMAT)
        except ValueError:
            continue
    raise ValidationError(f"'{value}' is not a valid month. Use YYYY-MM (e.g. 2026-08).")


def parse_category(value) -> str:
    """Lowercase and trim a category name."""
    text = " ".join(str(value).strip().lower().split())
    if not text:
        raise ValidationError("Category cannot be empty.")
    if len(text) > 40:
        raise ValidationError("Category name is too long (max 40 characters).")
    return text


def parse_note(value) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) > 200:
        raise ValidationError("Note is too long (max 200 characters).")
    return text


# --------------------------------------------------------------------------
# load / save
# --------------------------------------------------------------------------

def empty_data() -> dict:
    """A brand new, empty ledger."""
    return {
        "version": SCHEMA_VERSION,
        "next_id": 1,
        "budgets": {},
        "transactions": [],
    }


def _normalize(data: dict) -> dict:
    """Fill in missing keys so older / hand-edited files still load."""
    if not isinstance(data, dict):
        raise StorageError("Data file must contain a JSON object.")

    data.setdefault("version", SCHEMA_VERSION)
    data.setdefault("budgets", {})
    data.setdefault("transactions", [])

    if not isinstance(data["transactions"], list):
        raise StorageError("'transactions' must be a JSON list.")
    if not isinstance(data["budgets"], dict):
        raise StorageError("'budgets' must be a JSON object.")

    clean = []
    for raw in data["transactions"]:
        if not isinstance(raw, dict):
            raise StorageError("Every transaction must be a JSON object.")
        try:
            clean.append(
                {
                    "id": int(raw["id"]),
                    "type": parse_type(raw["type"]),
                    "amount": parse_amount(raw["amount"]),
                    "category": parse_category(raw["category"]),
                    "date": parse_date(raw["date"]),
                    "note": parse_note(raw.get("note", "")),
                    "created_at": str(raw.get("created_at", "")),
                }
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise StorageError(f"Broken transaction in data file: {exc}") from exc
    data["transactions"] = clean

    data["budgets"] = {
        parse_category(cat): parse_amount(limit)
        for cat, limit in data["budgets"].items()
    }

    highest = max((tx["id"] for tx in clean), default=0)
    next_id = int(data.get("next_id", highest + 1))
    data["next_id"] = max(next_id, highest + 1)
    return data


def load_data(path=DATA_FILE) -> dict:
    """Read the ledger from ``path``; return an empty one if it does not exist."""
    path = Path(path)
    if not path.exists():
        return empty_data()
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise StorageError(
            f"{path} is not valid JSON (line {exc.lineno}): {exc.msg}"
        ) from exc
    except OSError as exc:
        raise StorageError(f"Could not read {path}: {exc}") from exc
    return _normalize(raw)


def save_data(data: dict, path=DATA_FILE) -> None:
    """Write the ledger to ``path`` atomically, so a crash cannot truncate it."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a sibling temp file first, then swap it into place.
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(tmp_name, path)
        except BaseException:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise
    except OSError as exc:
        raise StorageError(f"Could not write {path}: {exc}") from exc


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------

def add_transaction(data, tx_type, amount, category, tx_date=None, note="") -> dict:
    """Validate the input, append a new transaction and return it."""
    transaction = {
        "id": int(data.get("next_id", 1)),
        "type": parse_type(tx_type),
        "amount": parse_amount(amount),
        "category": parse_category(category),
        "date": parse_date(tx_date),
        "note": parse_note(note),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    data["transactions"].append(transaction)
    data["next_id"] = transaction["id"] + 1
    return transaction


def get_transaction(data, tx_id) -> dict:
    """Return the transaction with ``tx_id`` or raise :class:`TransactionNotFound`."""
    try:
        wanted = int(tx_id)
    except (TypeError, ValueError):
        raise ValidationError(f"'{tx_id}' is not a valid id.") from None
    for transaction in data["transactions"]:
        if transaction["id"] == wanted:
            return transaction
    raise TransactionNotFound(f"No transaction with id {wanted}.")


def update_transaction(data, tx_id, **fields) -> dict:
    """Update any of type/amount/category/date/note on one transaction.

    ``None`` values are ignored, so callers can pass "leave unchanged".
    """
    transaction = get_transaction(data, tx_id)
    parsers = {
        "type": parse_type,
        "amount": parse_amount,
        "category": parse_category,
        "date": parse_date,
        "note": parse_note,
    }
    unknown = set(fields) - set(parsers)
    if unknown:
        raise ValidationError(f"Cannot update unknown field(s): {', '.join(sorted(unknown))}.")

    # Validate everything before touching the transaction, so a bad value
    # cannot leave it half updated.
    updates = {
        key: parsers[key](value)
        for key, value in fields.items()
        if value is not None
    }
    transaction.update(updates)
    return transaction


def delete_transaction(data, tx_id) -> dict:
    """Remove and return one transaction."""
    transaction = get_transaction(data, tx_id)
    data["transactions"].remove(transaction)
    return transaction


def filter_transactions(
    data,
    tx_type=None,
    category=None,
    month=None,
    date_from=None,
    date_to=None,
    text=None,
) -> list:
    """Return the transactions matching every filter that was given."""
    result = list(data["transactions"])

    if tx_type:
        wanted_type = parse_type(tx_type)
        result = [t for t in result if t["type"] == wanted_type]

    if category:
        wanted_category = parse_category(category)
        result = [t for t in result if t["category"] == wanted_category]

    if month:
        wanted_month = parse_month(month)
        result = [t for t in result if t["date"].startswith(wanted_month)]

    if date_from:
        start = parse_date(date_from)
        result = [t for t in result if t["date"] >= start]

    if date_to:
        end = parse_date(date_to)
        result = [t for t in result if t["date"] <= end]

    if text:
        needle = str(text).strip().lower()
        result = [
            t for t in result
            if needle in t["note"].lower() or needle in t["category"].lower()
        ]

    return sort_transactions(result)


def sort_transactions(transactions) -> list:
    """Oldest first, ties broken by id so the order is always stable."""
    return sorted(transactions, key=lambda t: (t["date"], t["id"]))


def known_categories(data) -> list:
    """Default categories plus every category already used or budgeted."""
    used = {t["category"] for t in data["transactions"]}
    used.update(data.get("budgets", {}))
    extra = sorted(used - set(DEFAULT_CATEGORIES))
    return DEFAULT_CATEGORIES + extra


# --------------------------------------------------------------------------
# budgets
# --------------------------------------------------------------------------

def set_budget(data, category, limit) -> float:
    """Set a monthly spending limit for one category."""
    cat = parse_category(category)
    value = parse_amount(limit)
    data.setdefault("budgets", {})[cat] = value
    return value


def remove_budget(data, category) -> None:
    cat = parse_category(category)
    if cat not in data.get("budgets", {}):
        raise ValidationError(f"No budget set for '{cat}'.")
    del data["budgets"][cat]
