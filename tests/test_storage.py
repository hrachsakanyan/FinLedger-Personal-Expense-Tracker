"""Tests for validation, JSON persistence and CRUD."""

import json
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import storage  # noqa: E402
from storage import StorageError, TransactionNotFound, ValidationError  # noqa: E402


def sample_data():
    data = storage.empty_data()
    storage.add_transaction(data, "income", 1000, "salary", "2026-07-01", "July pay")
    storage.add_transaction(data, "expense", 12.5, "food", "2026-07-03", "lunch")
    storage.add_transaction(data, "expense", 40, "transport", "2026-08-02", "taxi")
    return data


class TestParsing(unittest.TestCase):
    def test_parse_amount_accepts_common_formats(self):
        self.assertEqual(storage.parse_amount("12"), 12.0)
        self.assertEqual(storage.parse_amount("12,5"), 12.5)
        self.assertEqual(storage.parse_amount(" 3.999 "), 4.0)  # rounded to 2 decimals
        self.assertEqual(storage.parse_amount(0.125), 0.13)     # half up

    def test_parse_amount_rejects_bad_values(self):
        for bad in ("", "abc", "0", "-5", "nan", True):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    storage.parse_amount(bad)

    def test_parse_type(self):
        self.assertEqual(storage.parse_type("EXPENSE"), "expense")
        self.assertEqual(storage.parse_type("i"), "income")
        with self.assertRaises(ValidationError):
            storage.parse_type("spending")

    def test_parse_date_defaults_to_today(self):
        today = date.today().strftime("%Y-%m-%d")
        self.assertEqual(storage.parse_date(""), today)
        self.assertEqual(storage.parse_date(None), today)
        self.assertEqual(storage.parse_date("today"), today)
        self.assertEqual(storage.parse_date("2026-08-02"), "2026-08-02")

    def test_parse_date_rejects_invalid(self):
        for bad in ("02-08-2026", "2026-13-01", "2026-02-30", "tomorrow"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    storage.parse_date(bad)

    def test_parse_month(self):
        self.assertEqual(storage.parse_month("2026-08"), "2026-08")
        self.assertEqual(storage.parse_month("2026-08-17"), "2026-08")
        with self.assertRaises(ValidationError):
            storage.parse_month("august")

    def test_parse_category_normalizes(self):
        self.assertEqual(storage.parse_category("  Food  "), "food")
        self.assertEqual(storage.parse_category("Public   Transport"), "public transport")
        with self.assertRaises(ValidationError):
            storage.parse_category("   ")


class TestCrud(unittest.TestCase):
    def setUp(self):
        self.data = sample_data()

    def test_add_assigns_incrementing_ids(self):
        self.assertEqual([t["id"] for t in self.data["transactions"]], [1, 2, 3])
        self.assertEqual(self.data["next_id"], 4)

    def test_add_validates_input(self):
        with self.assertRaises(ValidationError):
            storage.add_transaction(self.data, "expense", -1, "food")
        self.assertEqual(len(self.data["transactions"]), 3)

    def test_get_transaction(self):
        self.assertEqual(storage.get_transaction(self.data, 2)["category"], "food")
        self.assertEqual(storage.get_transaction(self.data, "2")["id"], 2)
        with self.assertRaises(TransactionNotFound):
            storage.get_transaction(self.data, 99)

    def test_update_transaction(self):
        updated = storage.update_transaction(
            self.data, 2, amount="20", category="Groceries", note=None
        )
        self.assertEqual(updated["amount"], 20.0)
        self.assertEqual(updated["category"], "groceries")
        self.assertEqual(updated["note"], "lunch")  # None means "leave unchanged"

    def test_update_rejects_bad_value_without_partial_write(self):
        with self.assertRaises(ValidationError):
            storage.update_transaction(self.data, 2, category="drinks", amount="oops")
        transaction = storage.get_transaction(self.data, 2)
        self.assertEqual(transaction["category"], "food")
        self.assertEqual(transaction["amount"], 12.5)

    def test_update_rejects_unknown_field(self):
        with self.assertRaises(ValidationError):
            storage.update_transaction(self.data, 2, currency="USD")

    def test_delete_transaction(self):
        deleted = storage.delete_transaction(self.data, 1)
        self.assertEqual(deleted["id"], 1)
        self.assertEqual([t["id"] for t in self.data["transactions"]], [2, 3])
        with self.assertRaises(TransactionNotFound):
            storage.delete_transaction(self.data, 1)

    def test_deleted_ids_are_not_reused(self):
        storage.delete_transaction(self.data, 3)
        new = storage.add_transaction(self.data, "expense", 5, "food")
        self.assertEqual(new["id"], 4)


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.data = sample_data()

    def test_filter_by_type_and_category(self):
        found = storage.filter_transactions(self.data, tx_type="expense")
        self.assertEqual([t["id"] for t in found], [2, 3])
        found = storage.filter_transactions(self.data, category="Food")
        self.assertEqual([t["id"] for t in found], [2])

    def test_filter_by_month_and_range(self):
        self.assertEqual(
            [t["id"] for t in storage.filter_transactions(self.data, month="2026-07")],
            [1, 2],
        )
        self.assertEqual(
            [
                t["id"]
                for t in storage.filter_transactions(
                    self.data, date_from="2026-07-02", date_to="2026-08-01"
                )
            ],
            [2],
        )

    def test_filter_by_text(self):
        found = storage.filter_transactions(self.data, text="LUNCH")
        self.assertEqual([t["id"] for t in found], [2])

    def test_filters_combine(self):
        found = storage.filter_transactions(
            self.data, tx_type="expense", month="2026-08"
        )
        self.assertEqual([t["id"] for t in found], [3])

    def test_results_are_sorted_by_date(self):
        storage.add_transaction(self.data, "expense", 1, "food", "2026-06-01")
        found = storage.filter_transactions(self.data)
        self.assertEqual([t["date"] for t in found], sorted(t["date"] for t in found))


class TestBudgets(unittest.TestCase):
    def test_set_and_remove(self):
        data = storage.empty_data()
        storage.set_budget(data, "Food", "300")
        self.assertEqual(data["budgets"], {"food": 300.0})
        storage.remove_budget(data, "food")
        self.assertEqual(data["budgets"], {})
        with self.assertRaises(ValidationError):
            storage.remove_budget(data, "food")


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "nested" / "transactions.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_returns_empty_ledger(self):
        self.assertEqual(storage.load_data(self.path), storage.empty_data())

    def test_save_then_load_round_trip(self):
        data = sample_data()
        storage.set_budget(data, "food", 300)
        storage.save_data(data, self.path)
        self.assertTrue(self.path.exists())
        self.assertEqual(storage.load_data(self.path), data)

    def test_unicode_notes_survive_round_trip(self):
        data = storage.empty_data()
        storage.add_transaction(data, "expense", 5, "food", "2026-08-02", "սուրճ")
        storage.save_data(data, self.path)
        self.assertEqual(storage.load_data(self.path)["transactions"][0]["note"], "սուրճ")

    def test_broken_json_raises_storage_error(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(StorageError):
            storage.load_data(self.path)

    def test_missing_keys_are_filled_in(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                {
                    "transactions": [
                        {
                            "id": 7,
                            "type": "expense",
                            "amount": 10,
                            "category": "food",
                            "date": "2026-08-02",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        data = storage.load_data(self.path)
        self.assertEqual(data["budgets"], {})
        self.assertEqual(data["next_id"], 8)  # recovered from the highest id
        self.assertEqual(data["transactions"][0]["note"], "")

    def test_invalid_transaction_in_file_raises_storage_error(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps({"transactions": [{"id": 1, "type": "expense"}]}),
            encoding="utf-8",
        )
        with self.assertRaises(StorageError):
            storage.load_data(self.path)

    def test_save_leaves_no_temp_files_behind(self):
        storage.save_data(sample_data(), self.path)
        storage.save_data(sample_data(), self.path)
        self.assertEqual([p.name for p in self.path.parent.iterdir()],
                         [self.path.name])


if __name__ == "__main__":
    unittest.main()
