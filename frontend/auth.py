import functools
import os
import sqlite3

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

print("Loading auth.py")  # Debug: Sprawdzenie, czy moduł się ładuje

# Definicja blueprintów
bpUser = Blueprint('auth', __name__, url_prefix='/auth')
bpAdmin = Blueprint('admin', __name__, url_prefix='/auth/admin')

def get_db():
    if 'db' not in g:
        db_path = os.path.join('/app/frontend', 'users.db')
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        print(f"Connected to database at {db_path}")  # Debug
        query = "SELECT name FROM sqlite_master WHERE type='table'"
        print(f"Tables: {g.db.execute(query).fetchall()}")  # Debug: Lista tabel
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
        print("Database connection closed")  # Debug

def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please log in to access this page.", "warning")  # Opcjonalny flash
            return redirect(url_for("auth.login"))

        user_id = g.user["id"]
        
        db = get_db()
        user = db.execute("SELECT is_admin FROM user WHERE id = ?", (user_id,)).fetchone()

        if user is None or not user["is_admin"]:
            return redirect(url_for("auth.login"))
        
        return view(**kwargs)
    return wrapped_view

@bpAdmin.route("/")
@admin_required
def index():
    db = get_db()
    users = db.execute("SELECT id, username, is_admin FROM user").fetchall()
    posts = db.execute("SELECT id, title, created, author_id FROM post").fetchall()
    return render_template("auth/admin/index.html", users=users, posts=posts)

@bpAdmin.route("/delete_post/<int:id>", methods=["POST"])
@admin_required
def delete_post(id):
    db = get_db()
    db.execute("DELETE FROM post WHERE id = ?", (id,))
    db.commit()
    flash("Post deleted successfully.")
    return redirect(url_for("admin.index"))

@bpAdmin.route("/edit_user/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_user(id):
    db = get_db()
    user = db.execute("SELECT * FROM user WHERE id = ?", (id,)).fetchone()

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        is_admin = 'is_admin' in request.form

        if password:
            password = generate_password_hash(password, method="pbkdf2:sha256")
            db.execute(
                "UPDATE user SET username = ?, password = ?, is_admin = ? WHERE id = ?",
                (username, password, is_admin, id),
            )
        else:
            db.execute(
                "UPDATE user SET username = ?, is_admin = ? WHERE id = ?",
                (username, is_admin, id),
            )
        db.commit()
        flash("User updated successfully.")
        return redirect(url_for("admin.index"))

    return render_template("auth/admin/edit_user.html", user=user)

@bpAdmin.route("/add_user", methods=["GET", "POST"])
@admin_required
def add_user():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        is_admin = 'is_admin' in request.form

        db = get_db()
        db.execute(
            "INSERT INTO user (username, password, is_admin) VALUES (?, ?, ?)",
            (username, generate_password_hash(password, method="pbkdf2:sha256"), is_admin)
        )
        db.commit()
        flash("User added successfully.")
        return redirect(url_for("admin.index"))
    return render_template("auth/admin/add_user.html")

@bpAdmin.route("/delete_user/<int:id>", methods=["POST"])
@admin_required
def delete_user(id):
    db = get_db()
    db.execute("DELETE FROM user WHERE id = ?", (id,))
    db.commit()
    flash("User deleted successfully.")
    return redirect(url_for("admin.index"))

@bpUser.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (username, password, is_admin) VALUES (?, ?, ?)",
                    (username, generate_password_hash(password, method="pbkdf2:sha256"), 0),
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                return redirect(url_for("auth.login"))

        flash(error)
    return render_template('auth/register.html')

@bpUser.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM user WHERE username = ?', (username,)
        ).fetchone()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')

@bpUser.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM user WHERE id = ?', (user_id,)
        ).fetchone()

@bpUser.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view