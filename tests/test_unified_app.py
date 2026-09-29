import unittest
import os
import sqlite3
from core import app_db
from functions import ferie_db

class TestUnifiedApp(unittest.TestCase):
    def setUp(self):
        self.test_db_path = "data/test_app_data.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        app_db.init_app_db(self.test_db_path)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_db_initialization(self):
        conn = app_db.get_connection(self.test_db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()

        self.assertIn("dipendenti", tables)
        self.assertIn("ferie_storico", tables)
        self.assertIn("giacenze", tables)
        self.assertIn("foto_skus", tables)
        self.assertIn("user_dashboard_widgets", tables)

    def test_dashboard_widgets_persistence(self):
        username = "test_user"
        widgets = ["widget_ferie", "widget_ecom_bi"]
        app_db.save_user_dashboard_widgets(username, widgets)

        retrieved = app_db.get_user_dashboard_widgets(username)
        self.assertEqual(retrieved, widgets)

    def test_ferie_operations(self):
        df_dip = ferie_db.get_dipendenti()
        self.assertFalse(df_dip.empty)

        df_storico = ferie_db.get_ferie_storico()
        riepilogo = ferie_db.calcola_riepilogo_ferie_annuale(df_storico, "Mario Rossi", 26)
        self.assertIn(2026, riepilogo)

if __name__ == "__main__":
    unittest.main()
