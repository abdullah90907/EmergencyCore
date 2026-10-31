import unittest
from unittest.mock import MagicMock, patch
from backend.emergencycore.database import PostgresConnection, Record


class PostgresAdapterTests(unittest.TestCase):
    @patch('psycopg.connect')
    def test_parameter_binding_and_literal_preservation(self, connect):
        db = PostgresConnection('postgresql://test')
        db.execute("SELECT '?' AS literal FROM incidents WHERE id=?", ('test',))
        connect.return_value.execute.assert_called_with("SELECT '?' AS literal FROM incidents WHERE id=%s", ('test',))
        db.execute('INSERT INTO incidents(id) VALUES(:id)', {'id': 'test'})
        connect.return_value.execute.assert_called_with('INSERT INTO incidents(id) VALUES(%(id)s)', {'id': 'test'})
        self.assertIsNone(connect.call_args.kwargs['prepare_threshold'])
        self.assertTrue(connect.call_args.kwargs['autocommit'])

    @patch('psycopg.connect')
    def test_transaction_context_handles_exceptions(self, connect):
        db = PostgresConnection('postgresql://test')
        transaction = connect.return_value.transaction.return_value
        with self.assertRaises(RuntimeError):
            with db:
                raise RuntimeError('rollback')
        transaction.__enter__.assert_called_once()
        self.assertEqual(transaction.__exit__.call_args.args[0], RuntimeError)
        self.assertEqual(db.transactions, [])

    def test_mapping_rows_keep_legacy_count_access(self):
        row = Record(count=3)
        self.assertEqual(row[0], 3)
        self.assertEqual(row['count'], 3)
        self.assertEqual(dict(row), {'count': 3})
