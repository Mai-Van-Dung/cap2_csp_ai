"""
Database connection and configuration module for MySQL
"""
import os
import logging
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(__file__)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "cap2_csp_db"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "use_pure": True,
    "autocommit": True,
}

logger = logging.getLogger(__name__)


def get_connection():
    """Create and return a new database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        logger.info("Database connection successful")
        return connection
    except Error as e:
        logger.error(f"Database connection error: {e}")
        raise


@contextmanager
def get_db_cursor(dictionary=False):
    """
    Context manager for database cursor
    Usage:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM zones")
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=dictionary)
        yield cursor
        connection.commit()
    except Error as e:
        logger.error(f"Database error: {e}")
        if connection:
            connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def execute_query(query, params=None):
    """Execute a query without returning results"""
    with get_db_cursor() as cursor:
        cursor.execute(query, params or ())


def fetch_one(query, params=None):
    """Fetch a single row"""
    with get_db_cursor(dictionary=True) as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchone()


def fetch_all(query, params=None):
    """Fetch all rows"""
    with get_db_cursor(dictionary=True) as cursor:
        cursor.execute(query, params or ())
        return cursor.fetchall()
