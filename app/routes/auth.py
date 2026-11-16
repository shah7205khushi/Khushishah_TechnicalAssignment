from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, g
from app.models.user import User
from app.extensions import db

auth_bp = Blueprint('auth', __name__, url_prefix='')

def get_current_user():
    if not hasattr(g, 'current_user'):
        user_id = session.get('user_id')
        if user_id:
            g.current_user = db.session.get(User, user_id)
        else:
            g.current_user = None
    return g.current_user

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required. Please log in.'}), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required.'}), 401
            return redirect(url_for('auth.login', next=request.path))
        if not user.is_admin:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Forbidden: Administrator privileges required.'}), 403
            flash('Access denied: Administrator privileges required.', 'danger')
            return redirect(url_for('orders.list_orders'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if get_current_user():
        return redirect(url_for('orders.list_orders'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('auth/login.html', email=email)

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'danger')
            return render_template('auth/login.html', email=email)

        # Establish session
        session.clear()
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['user_email'] = user.email
        session['role'] = user.role

        flash(f'Welcome back, {user.name}!', 'success')
        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('orders.list_orders'))

    return render_template('auth/login.html')

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('You have been safely logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/')
def index():
    if get_current_user():
        return redirect(url_for('orders.list_orders'))
    return redirect(url_for('auth.login'))
