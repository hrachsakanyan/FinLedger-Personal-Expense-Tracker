# FinLedger — Personal Expense Tracker (CLI + JSON)

A small terminal app for tracking income and expenses. Every transaction has a
category and a date, everything is stored in one human-readable JSON file, and
the app can show you monthly summaries, a category breakdown, your balance and
how close you are to your monthly budgets.

Written in **plain Python 3.9+** — no third-party libraries, no database, no setup.

---

## Features

- **Full CRUD** — add, list, edit and delete transactions
- **Categories** — food, transport, medical, housing, … or any custom one you type
- **Monthly summary** — income / expense / balance per month
- **Category breakdown** — totals, percentage share and a simple ASCII bar chart
- **Balance** — total income minus total expenses, at any time
- **Search & filter** — by type, category, month, date range or free text
- **Budget limits + alerts** — set a monthly limit per category and get warned at 80% and over 100%
- **CSV export** — export everything or just one month, ready for Excel / Google Sheets
- **Safe by design** — input validation everywhere, `Decimal`-based money math, atomic JSON writes

---

## Project structure

```text
finledger/
├── src/
│   ├── main.py         # CLI menu, user input handling
│   ├── storage.py      # validation, JSON load/save, CRUD
│   └── reports.py      # summaries, breakdowns, budgets, CSV export
├── data/
│   └── transactions.json   # the ledger (sample data included)
├── tests/
│   ├── test_storage.py
│   └── test_reports.py
├── README.md
├── requirements.txt
└── .gitignore
```

The three modules are deliberately separated: `storage.py` never prints,
`reports.py` never touches user input, and `main.py` only handles the menu.
That is what makes the first two easy to unit test.

---

## Installation & usage

```bash
git clone https://github.com/<your-username>/finledger.git
cd finledger

python src/main.py                    # uses data/transactions.json
python src/main.py --data my.json     # or any other ledger file
```

No `pip install` needed — the standard library is enough.

Inside the app you get a numbered menu:

```text
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
```

Handy input shortcuts:

| Input | Meaning |
| --- | --- |
| `c` | cancel the current action and go back to the menu |
| *Enter* | accept the value shown in `[brackets]` |
| `today` or empty date | today's date |
| `i` / `e` | income / expense |
| `12,5` | same as `12.5` |

---

## Screenshots

**Monthly summary**

```text
--- Monthly summary ---
MONTH    INCOME    EXPENSE  BALANCE  COUNT
-------  --------  -------  -------  -----
2026-07  1,200.00  602.30   597.70   5
2026-08  150.00    28.25    121.75   3
```

**Category breakdown** (one `#` per 5%)

```text
--- expense by category - all time ---
CATEGORY       TOTAL   SHARE  COUNT
-------------  ------  -----  -----  ---------------
housing        480.00  76.1%  1      ###############
food           81.15   12.9%  2      ###
medical        34.90   5.5%   1      #
transport      25.00   4.0%   1      #
entertainment  9.50    1.5%   1
```

**Transaction list**

```text
ID  DATE        TYPE     CATEGORY       AMOUNT    NOTE
--  ----------  -------  -------------  --------  ------------------
1   2026-07-01  income   salary         1,200.00  July salary
2   2026-07-01  expense  housing        480.00    rent
3   2026-07-06  expense  food           62.40     groceries
7   2026-08-02  expense  food           18.75     lunch with friends
8   2026-08-02  expense  entertainment  9.50      cinema ticket

8 transaction(s) | income 1,350.00 AMD | expense 630.55 AMD | balance 719.45 AMD
```

**Budget alert after adding an expense**

```text
Saved #10: expense 300.00 AMD (food) on 2026-08-03
! Over budget for 'food' in 2026-08: 364.25 AMD of 300.00 AMD (121%)
```

---

## Data format

Everything lives in a single JSON object:

```json
{
  "version": 1,
  "next_id": 9,
  "budgets": {
    "food": 300.0,
    "transport": 100.0
  },
  "transactions": [
    {
      "id": 7,
      "type": "expense",
      "amount": 18.75,
      "category": "food",
      "date": "2026-08-02",
      "note": "lunch with friends",
      "created_at": "2026-08-02T13:41:09"
    }
  ]
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `id` | int | unique, never reused after a delete |
| `type` | str | `"income"` or `"expense"` |
| `amount` | float | always **positive**, rounded to 2 decimals; the sign comes from `type` |
| `category` | str | lowercase, free text |
| `date` | str | ISO `YYYY-MM-DD` — sortable and comparable as a plain string |
| `note` | str | optional, may be empty |
| `created_at` | str | ISO timestamp of when the record was created |

Notes on robustness:

- Missing keys (`budgets`, `next_id`, `note`) are filled in on load, so older or
  hand-edited files still open.
- `next_id` is recovered from the highest existing id if it is missing or too low.
- A broken file gives a clear error instead of a stack trace, and the app refuses
  to start rather than overwrite it.
- Saving is **atomic**: the data is written to a temp file and then swapped into
  place, so a crash mid-save cannot leave you with half a ledger.

---

## Tests

49 unit tests, standard library only:

```bash
python -m unittest discover -s tests -v
```

They cover input validation, CRUD, filters, JSON round-trips (including Unicode
notes and corrupt files), monthly summaries, category shares, budget alerts and
CSV export.

---

## Roadmap

- [ ] Monthly charts with `matplotlib`
- [ ] SQLite backend as an alternative to JSON
- [ ] Recurring transactions (rent, salary)
- [ ] Multi-currency support
- [ ] Import from bank CSV

---

## What I learned building this

- Designing CRUD around a single source of truth and keeping IDs stable
- Persisting nested dicts/lists to JSON without losing or corrupting data
- Working with money safely (`Decimal`, half-up rounding, no float drift)
- Working with dates: ISO strings sort correctly and group into months for free
- Separating I/O, business logic and presentation so the logic stays testable
- Error handling with custom exception classes instead of scattered `print`s
