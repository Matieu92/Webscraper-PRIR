from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os

print("Loading auth.py")  # Debug: Sprawdzenie, czy moduł się ładuje

# Definicja blueprintów
bpUser = Blueprint('auth', __name__, url_prefix='/auth')
bpAdmin = Blueprint('admin', __name__, url_prefix='/admin')

def get_db():
    if 'db' not in g:
        db_path = os.path.join('/app/frontend', 'users.db')
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        print(f"Connected to database at {db_path}")  # Debug
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
        print("Database connection closed")  # Debug

# Widoki dla bpUser
@bpUser.route('/register', methods=('GET', 'POST'))
def register():
    print("Accessing register view")  # Debug
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif db.execute('SELECT id FROM user WHERE username = ?', (username,)).fetchone() is not None:
            error = 'User {} is already registered.'.format(username)

        if error is None:
            db.execute(
                'INSERT INTO user (username, password) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )
            db.commit()
            print(f"Registered user: {username}")  # Debug
            return redirect(url_for('auth.login'))
        flash(error)

    return render_template('auth/register.html')

@bpUser.route('/login', methods=('GET', 'POST'))
def login():
    print("Accessing login view")  # Debug
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            g.user = user
            print(f"Logged in user: {username}")  # Debug
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')

@bpUser.route('/logout')
def logout():
    print("Logging out")  # Debug
    g.user = None
    return redirect(url_for('index'))

@bpUser.before_app_request
def load_logged_in_user():
    g.user = None
    if 'user' in g:
        g.user = g.pop('user')
        print(f"Loaded user: {g.user['username'] if g.user else None}")  # Debug

def login_required(view):
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view

# Widoki dla bpAdmin z unikalnymi endpointami
@bpAdmin.route('/', methods=['GET'], endpoint='admin_index')
@login_required
def index():
    print("Accessing admin index")  # Debug
    db = get_db()
    users = db.execute('SELECT * FROM user').fetchall()
    return render_template('auth/admin/index.html', users=users)

@bpAdmin.route('/add', methods=['GET', 'POST'], endpoint='admin_add')
@login_required
def add_user():
    print("Accessing add_user view")  # Debug
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif db.execute('SELECT id FROM user WHERE username = ?', (username,)).fetchone() is not None:
            error = 'User {} is already registered.'.format(username)

        if error is None:
            db.execute(
                'INSERT INTO user (username, password) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )
            db.commit()
            print(f"Added user: {username}")  # Debug
            return redirect(url_for('admin.admin_index'))
        flash(error)

    return render_template('auth/admin/add_user.html')

@bpAdmin.route('/edit/<username>', methods=['GET', 'POST'], endpoint='admin_edit')
@login_required
def edit_user(username):
    print(f"Accessing edit_user view for {username}")  # Debug
    db = get_db()
    user = db.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()
    if request.method == 'POST':
        password = request.form['password']
        error = None

        if not password:
            error = 'Password is required.'

        if error is None:
            db.execute(
                'UPDATE user SET password = ? WHERE username = ?',
                (generate_password_hash(password), username)
            )
            db.commit()
            print(f"Edited user: {username}")  # Debug
            return redirect(url_for('admin.admin_index'))
        flash(error)

    return render_template('auth/admin/edit_user.html', user=user)