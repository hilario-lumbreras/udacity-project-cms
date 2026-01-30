
"""
Flask application bootstrap with aggressive diagnostics.
"""

# __init__.py

import os
import logging
from logging.config import dictConfig
from flask import Flask, request
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_session import Session

# ---------------------------
# Logging configuration
# ---------------------------
DEBUG_FLAG = os.getenv("DEBUG_FLAG", "true").lower() == "true"
LOG_LEVEL = "DEBUG" if DEBUG_FLAG else "INFO"

dictConfig({
    "version": 1,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default"
        }
    },
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["console"]
    }
})

# Reduce noise unless debugging
logging.getLogger("msal").setLevel(logging.DEBUG if DEBUG_FLAG else logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ---------------------------
# Flask app creation
# ---------------------------
app = Flask(__name__)
app.config.from_object(Config)

app.logger.warning("=== Flask app starting ===")
app.logger.warning("DEBUG_FLAG=%s LOG_LEVEL=%s", DEBUG_FLAG, LOG_LEVEL)

# ---------------------------
# Extensions
# ---------------------------
Session(app)
db = SQLAlchemy(app)

login = LoginManager(app)
login.login_view = "login"

# ---------------------------
# Request / response tracing
# ---------------------------
@app.before_request
def log_request():
    app.logger.debug(
        "REQUEST %s %s secure=%s",
        request.method,
        request.path,
        request.is_secure,
    )

@app.after_request
def log_response(response):
    app.logger.debug(
        "RESPONSE %s %s -> %s",
        request.method,
        request.path,
        response.status,
    )
    return response

@app.errorhandler(Exception)
def log_exception(e):
    app.logger.exception("UNHANDLED EXCEPTION")
    raise e

# ---------------------------
# Import routes LAST
# ---------------------------
try:
    import FlaskWebProject.views  # noqa: F401
    app.logger.warning("views.py imported successfully ✅")
except Exception:
    app.logger.exception("FAILED importing views.py ❌")

# ---------------------------
# Dump registered routes
# ---------------------------
app.logger.warning("=== REGISTERED ROUTES ===")
for rule in app.url_map.iter_rules():
    app.logger.warning("Route: %-30s -> %s", rule.rule, rule.endpoint)
app.logger.warning("=== END ROUTES ===")


import uuid
from flask import g, request

@app.before_request
def add_request_id():
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    app.logger.debug("RID=%s REQUEST %s %s secure=%s host=%s",
                     g.request_id, request.method, request.path,
                     request.is_secure, request.host)
    if DEBUG_FLAG:
        app.logger.debug("RID=%s QS=%s", g.request_id, request.query_string.decode("utf-8", "ignore"))

@app.after_request
def add_request_id_to_response(response):
    rid = getattr(g, "request_id", None)
    if rid:
        response.headers["X-Request-ID"] = rid
    app.logger.debug("RID=%s RESPONSE %s %s -> %s",
                     rid, request.method, request.path, response.status)
    return response

@app.errorhandler(404)
def not_found(e):
    # This will tell you exactly what Flask thinks exists
    app.logger.error("404 NOT FOUND path=%s host=%s method=%s", request.path, request.host, request.method)
    app.logger.error("Known routes: %s", [str(r) for r in app.url_map.iter_rules()])
    return "404 - Not Found (see server logs for route dump)", 404
