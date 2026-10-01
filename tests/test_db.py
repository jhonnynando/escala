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


class PooledConnectionWrapperTests(unittest.TestCase):
    def test_context_exit_returns_connection_to_pool(self):
        connection = mock.MagicMock()
        pool_context = mock.MagicMock()
        wrapper = db._PsycopgConnWrapper(connection, False, pool_context)

        with wrapper:
            pass

        connection.__enter__.assert_not_called()
        connection.__exit__.assert_not_called()
        pool_context.__exit__.assert_called_once_with(None, None, None)


class ConnectionScopeTests(unittest.TestCase):
    @mock.patch.object(db, "ensure_dirs")
    def test_scope_lazily_reuses_one_connection(self, _ensure_dirs):
        raw_connection = mock.MagicMock()
        pool_context = mock.MagicMock()
        owner = db._PsycopgConnWrapper(raw_connection, False, pool_context)

        with (
            mock.patch.object(db, "USE_POSTGRES", True),
            mock.patch.object(db, "psycopg", object()),
            mock.patch.object(db, "_new_postgres_connection", return_value=owner) as connect,
        ):
            with db.database_connection_scope():
                connect.assert_not_called()
                first = db.get_connection()
                second = db.get_connection(dict_rows=True)
                self.assertIs(first._conn, raw_connection)
                self.assertIs(second._conn, raw_connection)
                first.close()
                second.close()

        connect.assert_called_once_with(False)
        pool_context.__exit__.assert_called_once_with(None, None, None)


class SchemaCheckTests(unittest.TestCase):
    def test_schema_check_uses_single_query(self):
        cursor = mock.Mock()
        cursor.fetchone.return_value = (True,)

        self.assertTrue(db._postgres_schema_is_current(cursor))
        cursor.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
