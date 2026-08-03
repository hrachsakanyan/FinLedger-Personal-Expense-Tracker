"""Tests for summaries, breakdowns, budget alerts and CSV export."""

import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import reports  # noqa: E402
import storage  # noqa: E402


def sample_data():
    data = storage.empty_data()
    storage.add_transaction(data, "income", 1000, "salary", "2026-07-01")
    storage.add_transaction(data, "expense", 250, "food", "2026-07-05")
    storage.add_transaction(data, "expense", 150, "transport", "2026-07-20")
    storage.add_transaction(data, "income", 200, "gift", "2026-08-01")
    storage.add_transaction(data, "expense", 100, "food", "2026-08-02")
    return data


class TestTotals(unittest.TestCase):
    def setUp(self):
        self.transactions = sample_data()["transactions"]

    def test_totals(self):
        summary = reports.totals(self.transactions)
        self.assertEqual(summary["income"], 1200.0)
        self.assertEqual(summary["expense"], 500.0)
        self.assertEqual(summary["balance"], 700.0)
        self.assertEqual(summary["count"], 5)

    def test_empty_ledger(self):
        self.assertEqual(
            reports.totals([]),
            {"income": 0.0, "expense": 0.0, "balance": 0.0, "count": 0},
        )
        self.assertEqual(reports.balance([]), 0.0)

    def test_balance_can_be_negative(self):
        data = storage.empty_data()
        storage.add_transaction(data, "expense", 30, "food", "2026-08-02")
        self.assertEqual(reports.balance(data["transactions"]), -30.0)

    def test_float_addition_does_not_drift(self):
        data = storage.empty_data()
        for _ in range(3):
            storage.add_transaction(data, "expense", "0.1", "food", "2026-08-02")
        self.assertEqual(reports.total(data["transactions"]), 0.3)

    def test_format_money(self):
        self.assertEqual(reports.format_money(1234.5), "1,234.50 AMD")
        self.assertEqual(reports.format_money(-7, currency="USD"), "-7.00 USD")


class TestMonthlySummary(unittest.TestCase):
    def test_rows_are_grouped_and_sorted(self):
        rows = reports.monthly_summary(sample_data()["transactions"])
        self.assertEqual([row["month"] for row in rows], ["2026-07", "2026-08"])
        self.assertEqual(rows[0]["income"], 1000.0)
        self.assertEqual(rows[0]["expense"], 400.0)
        self.assertEqual(rows[0]["balance"], 600.0)
        self.assertEqual(rows[1]["balance"], 100.0)
        self.assertEqual(rows[1]["count"], 2)

    def test_empty(self):
        self.assertEqual(reports.monthly_summary([]), [])


class TestCategoryBreakdown(unittest.TestCase):
    def test_expense_breakdown(self):
        rows = reports.category_breakdown(sample_data()["transactions"])
        self.assertEqual([row["category"] for row in rows], ["food", "transport"])
        self.assertEqual(rows[0]["total"], 350.0)
        self.assertEqual(rows[0]["count"], 2)
        self.assertEqual(rows[0]["share"], 70.0)
        self.assertEqual(sum(row["share"] for row in rows), 100.0)

    def test_income_breakdown(self):
        rows = reports.category_breakdown(sample_data()["transactions"], "income")
        self.assertEqual([row["category"] for row in rows], ["salary", "gift"])

    def test_empty_does_not_divide_by_zero(self):
        self.assertEqual(reports.category_breakdown([]), [])


class TestBudgets(unittest.TestCase):
    def setUp(self):
        self.data = sample_data()
        storage.set_budget(self.data, "food", 300)

    def test_status_for_a_month(self):
        row = reports.budget_status(self.data, "2026-07")[0]
        self.assertEqual(row["spent"], 250.0)
        self.assertEqual(row["left"], 50.0)
        self.assertAlmostEqual(row["used"], 83.33, places=2)
        self.assertFalse(row["over"])

    def test_alert_when_close_to_limit(self):
        alert = reports.budget_alert(self.data, "food", "2026-07")
        self.assertIn("83%", alert)

    def test_alert_when_over_limit(self):
        storage.add_transaction(self.data, "expense", 100, "food", "2026-07-25")
        alert = reports.budget_alert(self.data, "food", "2026-07")
        self.assertIn("Over budget", alert)

    def test_no_alert_when_comfortably_inside(self):
        self.assertIsNone(reports.budget_alert(self.data, "food", "2026-08"))

    def test_no_alert_without_a_budget(self):
        self.assertIsNone(reports.budget_alert(self.data, "transport", "2026-07"))

    def test_income_does_not_count_against_a_budget(self):
        storage.set_budget(self.data, "salary", 100)
        row = [r for r in reports.budget_status(self.data, "2026-07")
               if r["category"] == "salary"][0]
        self.assertEqual(row["spent"], 0.0)


class TestRendering(unittest.TestCase):
    def test_transactions_table_contains_data_and_summary(self):
        text = reports.render_transactions(sample_data()["transactions"])
        self.assertIn("CATEGORY", text)
        self.assertIn("transport", text)
        self.assertIn("balance 700.00 AMD", text)

    def test_empty_tables_do_not_crash(self):
        self.assertEqual(reports.render_transactions([]), "(nothing to show)")
        self.assertEqual(reports.render_monthly_summary([]), "(nothing to show)")
        self.assertEqual(reports.render_category_breakdown([]), "(nothing to show)")

    def test_columns_are_aligned(self):
        text = reports.render_monthly_summary(sample_data()["transactions"])
        lines = text.splitlines()
        self.assertTrue(all(line.startswith("2026-0") for line in lines[2:]))


class TestCsvExport(unittest.TestCase):
    def test_export_writes_every_row(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "out" / "export.csv"
            data = sample_data()
            reports.export_csv(data["transactions"], path)

            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 5)
            self.assertEqual(list(rows[0]), reports.CSV_FIELDS)
            self.assertEqual(rows[0]["date"], "2026-07-01")
            self.assertEqual(rows[0]["category"], "salary")

    def test_export_of_a_filtered_selection(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "july.csv"
            data = sample_data()
            july = storage.filter_transactions(data, month="2026-07")
            reports.export_csv(july, path)

            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 3)


if __name__ == "__main__":
    unittest.main()
