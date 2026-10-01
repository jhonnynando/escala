import os
import unittest
from unittest import mock

from web import db


class CleanDatabaseUrlTests(unittest.TestCase):
    def test_removes_whitespace_and_matching_quotes(self):
        self.assertEqual(
            db._clean_database_url('  "postgresql://user:pass@host/db"  '),
            "postgresql://user:pass@host/db",
        )

    def test_empty_value_is_none(self):
        self.assertIsNone(db._clean_database_url("   "))


class ConnectionRetryTests(unittest.TestCase):
    class FakeDatabaseError(Exception):
        pass

    @mock.patch.object(db, "ensure_dirs")
    @mock.patch.object(db.time, "sleep")
    def test_retries_transient_connection_errors(self, sleep, _ensure_dirs):
        connect = mock.Mock(
            side_effect=[
                self.FakeDatabaseError("connection refused"),
                self.FakeDatabaseError("connection reset"),
                "connection",
            ]
        )
        with (
            mock.patch.object(db, "USE_POSTGRES", True),
            mock.patch.object(db, "DBError", self.FakeDatabaseError),
            mock.patch.object(db, "_postgres_connect", connect),
            mock.patch.dict(os.environ, {"JR_ESCALA_DB_CONNECT_ATTEMPTS": "3"}),
        ):
            self.assertEqual(db.get_connection(), "connection")

        self.assertEqual(connect.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @mock.patch.object(db, "ensure_dirs")
    @mock.patch.object(db.time, "sleep")
    def test_does_not_retry_authentication_errors(self, sleep, _ensure_dirs):
        connect = mock.Mock(side_effect=self.FakeDatabaseError("password authentication failed"))
        with (
            mock.patch.object(db, "USE_POSTGRES", True),
            mock.patch.object(db, "DBError", self.FakeDatabaseError),
            mock.patch.object(db, "_postgres_connect", connect),
            mock.patch.dict(os.environ, {"JR_ESCALA_DB_CONNECT_ATTEMPTS": "3"}),
        ):
            with self.assertRaises(self.FakeDatabaseError):
                db.get_connection()

        connect.assert_called_once_with(False)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
