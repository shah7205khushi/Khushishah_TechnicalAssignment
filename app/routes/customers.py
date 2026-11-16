from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.routes.auth import login_required, admin_required, get_current_user
from app.models.customer import Customer
from app.models.order import SalesOrder
from app.extensions import db

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')

@customers_bp.route('/')
@login_required
def list_customers():
    user = get_current_user()
    query = Customer.query

    # Sales Users can only view active customers (PDF Requirement)
    if user.is_sales_user:
        query = query.filter_by(status='active')
    else:
        # Status filter for Admin
        status_filter = request.args.get('status', '').strip().lower()
        if status_filter in ['active', 'inactive']:
            query = query.filter_by(status=status_filter)

    # Search filter: by name, email, or mobile (PDF Requirement)
    search_query = request.args.get('q', '').strip()
    if search_query:
        like_term = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Customer.name.ilike(like_term),
                Customer.email.ilike(like_term),
                Customer.mobile.ilike(like_term)
            )
        )

    customers = query.order_by(Customer.name.asc()).all()
    
    # Pre-calculate order references for safe deletion UI state
    customer_data = []
    for c in customers:
        order_count = SalesOrder.query.filter_by(customer_id=c.id).count()
        customer_data.append({
            'customer': c,
            'order_count': order_count,
            'can_delete': order_count == 0
        })

    return render_template(
        'customers/list.html',
        customer_data=customer_data,
        search_query=search_query,
        current_status=request.args.get('status', '')
    )

@customers_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_customer():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        mobile = request.form.get('mobile', '').strip()
        city = request.form.get('city', '').strip()
        status = request.form.get('status', 'active').strip().lower()

        # Backend Validation
        if not name:
            flash('Customer name is required.', 'danger')
            return render_template('customers/form.html', customer=None, action='Create')

        if status not in ['active', 'inactive']:
            status = 'active'

        new_customer = Customer(
            name=name,
            email=email or None,
            mobile=mobile or None,
            city=city or None,
            status=status
        )
        db.session.add(new_customer)
        db.session.commit()

        flash(f'Customer "{name}" created successfully.', 'success')
        return redirect(url_for('customers.list_customers'))

    return render_template('customers/form.html', customer=None, action='Create')

@customers_bp.route('/<int:customer_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_customer(customer_id):
    customer = db.session.get(Customer, customer_id)
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers.list_customers'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        mobile = request.form.get('mobile', '').strip()
        city = request.form.get('city', '').strip()
        status = request.form.get('status', 'active').strip().lower()

        # Backend Validation
        if not name:
            flash('Customer name is required.', 'danger')
            return render_template('customers/form.html', customer=customer, action='Edit')

        if status not in ['active', 'inactive']:
            status = 'active'

        customer.name = name
        customer.email = email or None
        customer.mobile = mobile or None
        customer.city = city or None
        customer.status = status

        db.session.commit()
        flash(f'Customer "{name}" updated successfully.', 'success')
        return redirect(url_for('customers.list_customers'))

    return render_template('customers/form.html', customer=customer, action='Edit')

@customers_bp.route('/<int:customer_id>/delete', methods=['POST'])
@admin_required
def delete_customer(customer_id):
    customer = db.session.get(Customer, customer_id)
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers.list_customers'))

    # PDF Requirement: "Delete customers only when no order references them. Prevent deletion; allow deactivation instead."
    order_count = SalesOrder.query.filter_by(customer_id=customer.id).count()
    if order_count > 0:
        flash(
            f'Cannot delete customer "{customer.name}" because {order_count} sales order(s) reference them. '
            f'Please deactivate this customer instead.',
            'warning'
        )
        return redirect(url_for('customers.list_customers'))

    customer_name = customer.name
    db.session.delete(customer)
    db.session.commit()
    flash(f'Customer "{customer_name}" was successfully deleted.', 'success')
    return redirect(url_for('customers.list_customers'))

@customers_bp.route('/<int:customer_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_status(customer_id):
    customer = db.session.get(Customer, customer_id)
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers.list_customers'))

    new_status = 'inactive' if customer.status == 'active' else 'active'
    customer.status = new_status
    db.session.commit()
    flash(f'Customer "{customer.name}" status changed to {new_status}.', 'info')
    return redirect(url_for('customers.list_customers'))
