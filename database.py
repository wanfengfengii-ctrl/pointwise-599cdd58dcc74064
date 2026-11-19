from contextlib import contextmanager
import sqlite3


def open_database(path):
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.execute('PRAGMA foreign_keys = ON')
    except sqlite3.Error:
        connection.close()
        raise
    return connection


@contextmanager
def write_transaction(connection):
    connection.execute('BEGIN IMMEDIATE')
    try:
        yield
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
