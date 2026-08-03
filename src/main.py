"""FinLedger - a personal expense tracker that runs in the terminal.

Usage:
    python src/main.py                 # use data/transactions.json
    python src/main.py --data my.json  # use another ledger file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow both "python src/main.py" and "python -m src.main".
sys.path.insert(0, str(Path(__file__).resolve().parent))

import reports  # noqa: E402
import storage  # noqa: E402
from storage import (  # noqa: E402
    FinLedgerError,
    TransactionNotFound,
    ValidationError,
)

MENU = """
=====================================
        FinLedger - main menu
=====================================
 1) Add transaction
 2) List all transactions
 3) Search / filter transactions
 4) Edit transaction
 5) Delete transaction
 6) Monthly summary
 7) Category breakdown
 8) Balance
 9) Budgets
10) Export to CSV
 0) Exit
"""


class Cancelled(Exception):
    """The user typed 'c' to abort the current action."""


# --------------------------------------------------------------------------
# input helpers
# --------------------------------------------------------------------------

def ask(question, default=None, allow_empty=False) -> str:
    """Ask one question. 'c' cancels the current action, EOF quits the app."""
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        try:
            answer = input(f"{question}{suffix}: ").strip()
        except EOFError:
            print()
            raise SystemExit(0)
        if answer.lower() == "c":
            raise Cancelled
        if not answer and default is not None:
            return str(default)
        if answer or allow_empty:
            return answer
        print("  This field is required (or type 'c' to cancel).")


def ask_valid(question, parser, default=None, allow_empty=False):
    """Ask until ``parser`` accepts the answer."""
    while True:
        answer = ask(question, default=default, allow_empty=allow_empty)
        if allow_empty and answer == "":
            return None
        try:
            return parser(answer)
        except ValidationError as exc:
            print(f"  {exc}")


def confirm(question) -> bool:
    return ask(f"{question} (y/n)", default="n").lower() in ("y", "yes")


def pause() -> None:
    try:
        input("\nPress Enter to continue...")
    except EOFError:
        print()
        raise SystemExit(0)


def show(title, body="") -> None:
    print(f"\n--- {title} ---")
    if body:
        print(body)


# --------------------------------------------------------------------------
# actions
# --------------------------------------------------------------------------

def action_add(data, path) -> None:
    show("Add transaction", "(type 'c' at any prompt to cancel)")
    print("Categories: " + ", ".join(storage.known_categories(data)))

    tx_type = ask_valid("Type (income/expense)", storage.parse_type, default="expense")
    amount = ask_valid("Amount", storage.parse_amount)
    category = ask_valid("Category", storage.parse_category, default="other")
    tx_date = ask_valid("Date (YYYY-MM-DD)", storage.parse_date, default="today")
    note = ask("Note", default="", allow_empty=True)

    transaction = storage.add_transaction(data, tx_type, amount, category, tx_date, note)
    storage.save_data(data, path)

    print(
        f"\nSaved #{transaction['id']}: {transaction['type']} "
        f"{reports.format_money(transaction['amount'])} "
        f"({transaction['category']}) on {transaction['date']}"
    )
    if transaction["type"] == "expense":
        alert = reports.budget_alert(data, transaction["category"], transaction["date"][:7])
        if alert:
            print(alert)


def action_list(data, path) -> None:
    show("All transactions", reports.render_transactions(data["transactions"]))


def action_search(data, path) -> None:
    show("Search / filter", "(leave a filter empty to skip it)")
    filters = {
        "tx_type": ask_valid("Type (income/expense)", storage.parse_type, allow_empty=True),
        "category": ask_valid("Category", storage.parse_category, allow_empty=True),
        "month": ask_valid("Month (YYYY-MM)", storage.parse_month, allow_empty=True),
        "date_from": ask_valid("From date (YYYY-MM-DD)", storage.parse_date, allow_empty=True),
        "date_to": ask_valid("To date (YYYY-MM-DD)", storage.parse_date, allow_empty=True),
        "text": ask("Text in note/category", default="", allow_empty=True) or None,
    }
    found = storage.filter_transactions(data, **filters)
    show("Results", reports.render_transactions(found))


def action_edit(data, path) -> None:
    show("Edit transaction", reports.render_transactions(data["transactions"]))
    if not data["transactions"]:
        return

    tx_id = ask("Id to edit")
    transaction = storage.get_transaction(data, tx_id)
    print("\nPress Enter to keep the current value.")

    updates = {
        "type": ask_valid("Type", storage.parse_type, default=transaction["type"]),
        "amount": ask_valid("Amount", storage.parse_amount, default=transaction["amount"]),
        "category": ask_valid("Category", storage.parse_category,
                              default=transaction["category"]),
        "date": ask_valid("Date", storage.parse_date, default=transaction["date"]),
        "note": ask("Note", default=transaction["note"], allow_empty=True),
    }
    storage.update_transaction(data, tx_id, **updates)
    storage.save_data(data, path)
    show("Updated", reports.render_transactions([storage.get_transaction(data, tx_id)]))


def action_delete(data, path) -> None:
    show("Delete transaction", reports.render_transactions(data["transactions"]))
    if not data["transactions"]:
        return

    tx_id = ask("Id to delete")
    transaction = storage.get_transaction(data, tx_id)
    print(
        f"\n#{transaction['id']} {transaction['date']} {transaction['type']} "
        f"{reports.format_money(transaction['amount'])} ({transaction['category']}) "
        f"{transaction['note']}"
    )
    if not confirm("Really delete this transaction?"):
        print("Cancelled.")
        return

    storage.delete_transaction(data, tx_id)
    storage.save_data(data, path)
    print(f"Deleted #{transaction['id']}.")


def action_monthly(data, path) -> None:
    show("Monthly summary", reports.render_monthly_summary(data["transactions"]))


def action_breakdown(data, path) -> None:
    tx_type = ask_valid("Breakdown of (income/expense)", storage.parse_type,
                        default="expense")
    month = ask_valid("Month (YYYY-MM, empty = all time)", storage.parse_month,
                      allow_empty=True)
    transactions = storage.filter_transactions(data, month=month) if month \
        else data["transactions"]
    title = f"{tx_type} by category" + (f" - {month}" if month else " - all time")
    show(title, reports.render_category_breakdown(transactions, tx_type))


def action_balance(data, path) -> None:
    summary = reports.totals(data["transactions"])
    show(
        "Balance",
        f"Transactions : {summary['count']}\n"
        f"Total income : {reports.format_money(summary['income'])}\n"
        f"Total expense: {reports.format_money(summary['expense'])}\n"
        f"Balance      : {reports.format_money(summary['balance'])}",
    )


def action_budgets(data, path) -> None:
    show("Budgets (monthly limits)", reports.render_budget_status(data))
    print("\n 1) Set / update a budget\n 2) Remove a budget\n 0) Back")
    choice = ask("Choice", default="0")

    if choice == "1":
        category = ask_valid("Category", storage.parse_category)
        limit = ask_valid("Monthly limit", storage.parse_amount)
        storage.set_budget(data, category, limit)
        storage.save_data(data, path)
        print(f"Budget for '{category}' set to {reports.format_money(limit)} / month.")
    elif choice == "2":
        category = ask_valid("Category", storage.parse_category)
        storage.remove_budget(data, category)
        storage.save_data(data, path)
        print(f"Budget for '{category}' removed.")


def action_export(data, path) -> None:
    show("Export to CSV")
    month = ask_valid("Month (YYYY-MM, empty = everything)", storage.parse_month,
                      allow_empty=True)
    transactions = storage.filter_transactions(data, month=month) if month \
        else data["transactions"]
    default_name = f"finledger_{month or 'all'}.csv"
    target = ask("File path", default=str(Path(path).parent / default_name))

    written = reports.export_csv(transactions, target)
    print(f"Exported {len(transactions)} transaction(s) to {written.resolve()}")


ACTIONS = {
    "1": action_add,
    "2": action_list,
    "3": action_search,
    "4": action_edit,
    "5": action_delete,
    "6": action_monthly,
    "7": action_breakdown,
    "8": action_balance,
    "9": action_budgets,
    "10": action_export,
}


# --------------------------------------------------------------------------
# app loop
# --------------------------------------------------------------------------

def run(path) -> int:
    try:
        data = storage.load_data(path)
    except FinLedgerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Fix the file or move it aside, then start FinLedger again.",
              file=sys.stderr)
        return 1

    print(f"FinLedger - {len(data['transactions'])} transaction(s) loaded from {path}")

    while True:
        print(MENU)
        try:
            choice = ask("Choose an option")
        except Cancelled:
            continue

        if choice == "0":
            print("Bye!")
            return 0

        action = ACTIONS.get(choice)
        if action is None:
            print("Unknown option - please pick a number from the menu.")
            continue

        try:
            action(data, path)
        except Cancelled:
            print("Cancelled.")
        except (ValidationError, TransactionNotFound) as exc:
            print(f"Error: {exc}")
        except FinLedgerError as exc:
            print(f"Storage error: {exc}")
        pause()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="finledger", description="Personal expense tracker (CLI + JSON)."
    )
    parser.add_argument(
        "--data",
        default=str(storage.DATA_FILE),
        help="path to the JSON ledger (default: data/transactions.json)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return run(Path(args.data))
    except KeyboardInterrupt:
        print("\nInterrupted. Bye!")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
