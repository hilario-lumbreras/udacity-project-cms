# config.py
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

class Config(object):
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Logging / debug (optional)
    DEBUG_FLAG = os.environ.get("DEBUG_FLAG", "false").lower() == "true"

    # Azure Blob Storage
    BLOB_ACCOUNT = os.environ.get("BLOB_ACCOUNT")
    BLOB_STORAGE_KEY = os.environ.get("BLOB_STORAGE_KEY")
    BLOB_CONTAINER = os.environ.get("BLOB_CONTAINER")  # e.g., "images"

    # Azure SQL
    SQL_SERVER = os.environ.get("SQL_SERVER")       # e.g., "yourserver.database.windows.net"
    SQL_DATABASE = os.environ.get("SQL_DATABASE")   # e.g., "yourdb"
    SQL_USER_NAME = os.environ.get("SQL_USER_NAME") # e.g., "sqladmin"
    SQL_PASSWORD = os.environ.get("SQL_PASSWORD")

    # Build a safe ODBC connection string
    odbc_params = urllib.parse.quote_plus(
        "Driver={ODBC Driver 17 for SQL Server};"
        f"Server=tcp:{SQL_SERVER},1433;"
        f"Database={SQL_DATABASE};"
        f"Uid={SQL_USER_NAME};"
        f"Pwd={SQL_PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    SQLALCHEMY_DATABASE_URI = f"mssql+pyodbc:///?odbc_connect={odbc_params}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # MSAL / Entra ID
    CLIENT_ID = os.environ.get("CLIENT_ID")
    CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
    # Use your tenant if single‑tenant; keep /common for multi‑tenant
    AUTHORITY = "https://login.microsoftonline.com/common"
    REDIRECT_PATH = "/getAToken"
    SCOPE = ["User.Read"]

    # Session
    SESSION_TYPE = "filesystem"