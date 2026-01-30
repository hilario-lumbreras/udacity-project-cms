# views.py
import uuid
import msal
from msal import SerializableTokenCache
from urllib.parse import urlsplit

from flask import (
    render_template, flash, redirect, request, session, url_for
)

from FlaskWebProject import app
from config import Config
from FlaskWebProject.forms import LoginForm, PostForm
from FlaskWebProject.models import User, Post
from flask_login import current_user, login_user, logout_user, login_required

# ---------------------------
# Health
# ---------------------------
@app.route("/healthz")
def healthz():
    app.logger.warning("healthz hit")
    return "OK", 200

# ---------------------------
# Helpers
# ---------------------------
def safe_next(default="home"):
    nxt = request.args.get("next")
    if not nxt or urlsplit(nxt).netloc != "":
        return url_for(default)
    return nxt

def _external_scheme():
    # Honor reverse proxy headers if present; default https in prod
    xf_proto = request.headers.get("X-Forwarded-Proto")
    if xf_proto in ("http", "https"):
        return xf_proto
    return "https" if not app.debug else request.scheme

def redirect_uri():
    uri = url_for("authorized", _external=True, _scheme=_external_scheme())
    app.logger.debug("Redirect URI computed: %s", uri)
    return uri

def load_cache():
    cache = SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache

def save_cache(cache):
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()

def build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        Config.CLIENT_ID,
        authority=Config.AUTHORITY,
        client_credential=Config.CLIENT_SECRET,
        token_cache=cache,
    )

# ---------------------------
# Routes
# ---------------------------
@app.route("/")
@app.route("/home")
@login_required
def home():
    app.logger.warning("HOME route accessed by user=%s", current_user.username)
    posts = Post.query.all()
    return render_template("index.html", posts=posts)

@app.route("/login", methods=["GET", "POST"])
def login():
    app.logger.warning("LOGIN route hit")
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    form = LoginForm()

    # Username/password login
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user or not user.check_password(form.password.data):
            app.logger.warning("Manual login FAILED for user=%s", form.username.data)
            flash("Invalid username or password")
            return redirect(url_for("login"))
        login_user(user)
        app.logger.warning("Manual login SUCCESS for user=%s", user.username)
        return redirect(safe_next())

    # MSAL auth URL
    session["state"] = str(uuid.uuid4())
    auth_url = build_msal_app().get_authorization_request_url(
        scopes=Config.SCOPE,
        state=session["state"],
        redirect_uri=redirect_uri(),
    )

    app.logger.warning("MSAL auth_url startswith: %s", auth_url[:80])
    app.logger.warning("Expected redirect_uri: %s", redirect_uri())

    return render_template("login.html", form=form, auth_url=auth_url)

@app.route(Config.REDIRECT_PATH)
def authorized():
    app.logger.warning("AUTHORIZED callback hit args=%s", dict(request.args))

    if request.args.get("state") != session.get("state"):
        app.logger.error("STATE MISMATCH expected=%s got=%s",
                         session.get("state"), request.args.get("state"))
        flash("Login session expired. Please sign in again.")
        return redirect(url_for("login"))

    if "error" in request.args:
        app.logger.error("MSAL authorization error: %s", request.args)
        return render_template("auth_error.html", result=request.args), 401

    code = request.args.get("code")
    if not code:
        app.logger.error("NO authorization code returned by MSAL.")
        flash("Login failed.")
        return redirect(url_for("login"))

    cache = load_cache()
    msal_app = build_msal_app(cache)
    result = msal_app.acquire_token_by_authorization_code(
        code, scopes=Config.SCOPE, redirect_uri=redirect_uri()
    )

    if not result or "error" in result:
        app.logger.error("TOKEN ERROR: %s", result)
        return render_template("auth_error.html", result=result), 401

    save_cache(cache)

    claims = result.get("id_token_claims", {})
    username = (
        claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("email")
        or claims.get("name")
        or "msal_user"
    )

    user = User.query.filter_by(username=username).first()
    if not user:
        from FlaskWebProject import db
        user = User(username=username)
        user.set_password(uuid.uuid4().hex)
        db.session.add(user)
        db.session.commit()

    login_user(user)
    app.logger.warning("MSAL login SUCCESS for=%s", user.username)
    return redirect(url_for("home"))

@app.route("/new_post", methods=["GET", "POST"])
@login_required
def new_post():
    app.logger.warning("NEW_POST route hit")
    form = PostForm()
    if form.validate_on_submit():
        post = Post()
        post.save_changes(form, request.files.get("image_path"), current_user.id, new=True)
        app.logger.warning("New post created successfully")
        return redirect(url_for("home"))
    return render_template(
        "post.html",
        title="Create Post",
        form=form,
        imageSource=f"https://{app.config['BLOB_ACCOUNT']}.blob.core.windows.net/{app.config['BLOB_CONTAINER']}/",
    )

@app.route("/post/<int:id>", methods=["GET", "POST"])  # fixed brackets
@login_required
def post(id):
    app.logger.warning("EDIT POST route hit id=%s", id)
    post_obj = Post.query.get_or_404(id)
    form = PostForm(obj=post_obj)

    if form.validate_on_submit():
        post_obj.save_changes(form, request.files.get("image_path"), current_user.id)
        app.logger.warning("Post %s updated successfully", id)
        return redirect(url_for("home"))

    return render_template(
        "post.html",
        title="Edit Post",
        form=form,
        imageSource=f"https://{app.config['BLOB_ACCOUNT']}.blob.core.windows.net/{app.config['BLOB_CONTAINER']}/",
    )

@app.route("/logout")
def logout():
    logout_user()
    session.clear()
    app.logger.warning("User logged out")
    return redirect(url_for("login"))