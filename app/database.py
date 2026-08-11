import logging
import os
import pyodbc

logger = logging.getLogger(__name__)

DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_NAME = os.getenv("DB_NAME", "HGT_Assignments")
DB_TRUSTED = os.getenv("DB_TRUSTED_CONNECTION", "yes")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

if DB_USER and DB_PASSWORD:
    CONNECTION_STRING = (
        f"Driver={{ODBC Driver 17 for SQL Server}};"
        f"Server={DB_SERVER};"
        f"Database={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
    )
else:
    CONNECTION_STRING = (
        f"Driver={{ODBC Driver 17 for SQL Server}};"
        f"Server={DB_SERVER};"
        f"Database={DB_NAME};"
        f"Trusted_Connection={DB_TRUSTED};"
    )

def get_db_connection():
    """Returns a new pyodbc connection to the database."""
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        return conn
    except Exception as e:
        logger.error("Database connection error", exc_info=True)
        return None
