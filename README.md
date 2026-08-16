# 💰 FinLedger — Personal Expense Tracker  

> A lightweight command-line personal finance tracker built with **plain Python 3.9+** and the standard library.

Track your **income and expenses**, manage **monthly budgets**, analyze spending by category, search and filter transactions, and export your financial data to **CSV** — all stored in a single human-readable JSON file.

No database. No third-party dependencies. No complicated setup. 

---

## ✨ Features 

| Feature                    | Description                                                     |
| -------------------------- | --------------------------------------------------------------- |
| 📝 **Full CRUD**           | Add, list, edit and delete transactions                         |
| 🏷️ **Categories**         | Food, transport, medical, housing, or any custom category       |
| 📊 **Monthly Summary**     | View income, expenses and balance for each month                |
| 📈 **Category Breakdown**  | See totals, percentage shares and ASCII bar charts              |
| 💰 **Balance**             | Calculate total income minus total expenses                     |
| 🔎 **Search & Filter**     | Filter by type, category, month, date range or free text        |
| 🎯 **Budget Limits**       | Set monthly category budgets and receive alerts                 |
| 🚨 **Budget Alerts**       | Warnings at 80% usage and when exceeding 100%                   |
| 📤 **CSV Export**          | Export all transactions or a specific month                     |
| 🛡️ **Safe Data Handling** | Validation, `Decimal` money calculations and atomic JSON writes |
| 🧪 **Unit Tested**         | 49 tests covering core functionality                            |

---

## 🛠️ Tech Stack

* 🐍 **Python 3.9+**
* 📦 **Python Standard Library only**
* 🗂️ **JSON** — data persistence
* 📄 **CSV** — data export
* 🧪 **unittest** — testing
* 💵 **Decimal** — accurate money calculations
* 📅 **datetime** — date handling

> **No third-party libraries required.**

---

## 📁 Project Structure

```text
finledger/
│
├── 📂 src/
│   ├── main.py          # CLI menu and user input handling
│   ├── storage.py       # Validation, JSON persistence and CRUD
│   └── reports.py       # Summaries, breakdowns, budgets and CSV export
│
├── 📂 data/
│   └── transactions.json    # Ledger with sample data
│
├── 📂 tests/
│   ├── test_storage.py      # Storage and CRUD tests
│   └── test_reports.py      # Reports and analytics tests
│
├── 📄 README.md
├── 📄 requirements.txt
└── 📄 .gitignore
```

### 🧩 Architecture

The application is intentionally split into three responsibilities:

```text
                 ┌─────────────────┐
                 │    main.py      │
                 │   CLI / Menu    │
                 └────────┬────────┘
                          │
                User Interaction
                          │
                          ▼
                 ┌─────────────────┐
                 │   storage.py    │
                 │ CRUD / JSON /    │
                 │   Validation    │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   reports.py    │
                 │ Analytics /     │
                 │ Budgets / CSV   │
                 └─────────────────┘
```

* `storage.py` never handles user interaction or printing.
* `reports.py` focuses only on business logic and reporting.
* `main.py` is responsible for the CLI and menu flow.

This separation keeps the core logic **clean, reusable and easy to unit test**.

---

## 🚀 Installation & Usage

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/finledger.git
cd finledger
```

### 2. Run the application

```bash
python src/main.py
```

By default, FinLedger uses:

```text
data/transactions.json
```

You can also provide a custom data file:

```bash
python src/main.py --data my.json
```

### 3. No installation required

FinLedger uses only the Python standard library.

```text
pip install ...
```

No need. 🎉

---

## 🖥️ Main Menu

When you start the application, you'll see:

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

---

## ⌨️ Input Shortcuts

| Input      | Meaning                                          |
| ---------- | ------------------------------------------------ |
| `c`        | Cancel the current action and return to the menu |
| `Enter`    | Accept the default value shown in `[brackets]`   |
| `today`    | Use today's date                                 |
| Empty date | Also uses today's date                           |
| `i`        | Income                                           |
| `e`        | Expense                                          |
| `12,5`     | Same as `12.5`                                   |

---

## 📊 Example Output

### Monthly Summary

```text
--- Monthly summary ---
MONTH    INCOME    EXPENSE  BALANCE  COUNT
-------  --------  -------  -------  -----
2026-07  1,200.00  602.30   597.70   5
2026-08  150.00    28.25    121.75   3
```

### Category Breakdown 

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

> Each `#` represents approximately **5%** of total expenses.

### Transaction List

```text
ID  DATE        TYPE     CATEGORY       AMOUNT    NOTE
--  ----------  -------  -------------  --------  ------------------
1   2026-07-01  income   salary         1,200.00  July salary
2   2026-07-01  expense  housing        480.00    rent
7   2026-08-02  expense  food           18.75     lunch with friends
8   2026-08-02  expense  entertainment  9.50      cinema ticket

8 transaction(s) | income 1,350.00 AMD | expense 630.55 AMD | balance 719.45 AMD
```

### Budget Alert

```text
Saved #10: expense 300.00 AMD (food) on 2026-08-03

! Over budget for 'food' in 2026-08:
  364.25 AMD of 300.00 AMD (121%)
```

---

## 🗃️ Data Format

FinLedger stores everything in a single JSON object:

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

### Transaction Fields

| Field        | Type    | Description                            |
| ------------ | ------- | -------------------------------------- |
| `id`         | `int`   | Unique ID, never reused after deletion |
| `type`       | `str`   | Either `"income"` or `"expense"`       |
| `amount`     | `float` | Positive amount rounded to 2 decimals  |
| `category`   | `str`   | Lowercase, free-text category          |
| `date`       | `str`   | ISO format: `YYYY-MM-DD`               |
| `note`       | `str`   | Optional transaction description       |
| `created_at` | `str`   | ISO timestamp of record creation       |

> The transaction amount is always positive. The transaction `type` determines whether it is treated as income or expense.

---

## 🛡️ Data Safety & Robustness

FinLedger is designed to handle common data problems safely.

### Automatic Data Recovery

* Missing `budgets`, `next_id` or `note` fields are filled automatically.
* `next_id` is recovered from the highest existing transaction ID if necessary.
* Older or manually edited JSON files can still be loaded when valid.

### Corrupted Data Protection

A broken JSON file produces a clear error message instead of an uncontrolled stack trace.

The application refuses to start rather than accidentally overwriting corrupted data.

### Atomic Writes

Data is saved using an **atomic write process**:

```text
Application
    │
    ▼
Write to temporary file
    │
    ▼
Save completed successfully
    │
    ▼
Replace original JSON file
```

This prevents the ledger from being left partially written if the application crashes during saving.

---

## 🧪 Testing

FinLedger includes **49 unit tests** using Python's built-in `unittest` framework.

Run the complete test suite with:

```bash
python -m unittest discover -s tests -v
```

The tests cover:

* ✅ Input validation
* ✅ CRUD operations
* ✅ Transaction filtering
* ✅ JSON round-trips
* ✅ Unicode transaction notes
* ✅ Corrupted JSON files
* ✅ Monthly summaries
* ✅ Category breakdowns
* ✅ Percentage calculations
* ✅ Budget alerts
* ✅ CSV export

---

## 🗺️ Roadmap

Future improvements planned for FinLedger:

* [ ] 📊 Monthly charts with `matplotlib`
* [ ] 🗄️ SQLite backend as an alternative to JSON
* [ ] 🔄 Recurring transactions (rent, salary, subscriptions)
* [ ] 🌍 Multi-currency support
* [ ] 🏦 Import transactions from bank CSV files

---

## 📚 What I Learned

Building FinLedger helped me practice and understand:

* Designing CRUD operations around a single source of truth
* Keeping transaction IDs stable and unique
* Persisting nested dictionaries and lists using JSON
* Working safely with money using `Decimal`
* Avoiding floating-point precision issues
* Using `datetime` and ISO date formats
* Filtering and grouping data by date and category
* Separating I/O, business logic and presentation
* Writing unit tests for application logic
* Handling corrupted files with custom exceptions
* Implementing atomic file writes
* Exporting structured data to CSV

---

## 🎯 Project Goals

FinLedger was built as a practical Python project to strengthen:

```text
Python Fundamentals
       │
       ├── File Handling
       ├── JSON
       ├── CSV
       ├── OOP / Modular Design
       ├── Error Handling
       ├── Date & Time
       ├── Decimal
       ├── Unit Testing
       └── CLI Applications
```

---

## 📌 Project Status

🟢 **Completed — Version 1.0**

The current version provides a fully functional CLI expense tracker with JSON persistence, reporting, budgets, filtering, CSV export and automated tests.

---

## 👨‍💻 Author

**Hrach Sakanhan**

Built with Python 🐍
