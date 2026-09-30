import unittest
import os
import sqlite3
import time
from core import app_db, auth
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
        app_db.ensure_dipendente_exists("Mario Rossi")
        df_dip = ferie_db.get_dipendenti()
        self.assertFalse(df_dip.empty)

        df_storico = ferie_db.get_ferie_storico()
        riepilogo = ferie_db.calcola_riepilogo_ferie_annuale(df_storico, "Mario Rossi", 26)
        self.assertIn(2026, riepilogo)

    def test_totp_verification(self):
        totp_info = auth.generate_totp_details_for_user("admin", "admin@ecom.it")
        secret = totp_info["totp_secret"]

        # Test invalid codes
        self.assertFalse(auth.verify_totp_secret_code(secret, "000000"))
        self.assertFalse(auth.verify_totp_secret_code(secret, "123456"))
        self.assertFalse(auth.verify_totp_secret_code(secret, "abcdef"))
        self.assertFalse(auth.verify_totp_secret_code(secret, ""))

        # Generate a valid code using internal RFC6238 logic
        import hmac, hashlib, struct
        import base64
        secret_padded = secret + '=' * ((8 - len(secret) % 8) % 8)
        key_bytes = base64.b32decode(secret_padded, casefold=True)
        time_counter = int(time.time()) // 30
        time_bytes = struct.pack(">Q", time_counter)
        hmac_digest = hmac.new(key_bytes, time_bytes, hashlib.sha1).digest()
        offset = hmac_digest[-1] & 0x0F
        binary_code = (
            ((hmac_digest[offset] & 0x7F) << 24) |
            ((hmac_digest[offset + 1] & 0xFF) << 16) |
            ((hmac_digest[offset + 2] & 0xFF) << 8) |
            (hmac_digest[offset + 3] & 0xFF)
        )
        valid_otp = f"{binary_code % 1000000:06d}"

        self.assertTrue(auth.verify_totp_secret_code(secret, valid_otp))

if __name__ == "__main__":
    unittest.main()
