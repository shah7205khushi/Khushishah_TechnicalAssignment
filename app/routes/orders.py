import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from app.routes.auth import login_required, get_current_user
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import SalesOrder, SalesOrderItem
from app.services.order_service import OrderService
from app.extensions import db

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

@orders_bp.route('/')
@login_required
def list_orders():
    user = get_current_user()
    
    # PDF Requirement: Admin manages all orders; Sales Users manage their own orders
    query = SalesOrder.query
    if user.is_sales_user:
        query = query.filter_by(created_by=user.id)
        
    status_filter = request.args.get('status', '').strip().lower()
    if status_filter in ['draft', 'confirmed', 'cancelled']:
        query = query.filter_by(status=status_filter)
        
    orders = query.order_by(SalesOrder.id.desc()).all()
    
    # Calculate quick dashboard stats
    if user.is_admin:
        all_user_orders = SalesOrder.query.all()
    else:
        all_user_orders = SalesOrder.query.filter_by(created_by=user.id).all()
        
    stats = {
        'total': len(all_user_orders),
        'draft': sum(1 for o in all_user_orders if o.status == 'draft'),
        'confirmed': sum(1 for o in all_user_orders if o.status == 'confirmed'),
        'cancelled': sum(1 for o in all_user_orders if o.status == 'cancelled'),
    }

    return render_template('orders/list.html', orders=orders, stats=stats, current_status=status_filter)

@orders_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_order():
    user = get_current_user()

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        discount_percentage = request.form.get('discount_percentage', '0.00')

        # Parse dynamic item rows submitted from the form
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')

        items_data = []
        for pid, qty in zip(product_ids, quantities):
            if pid and pid.strip():
                items_data.append({
                    'product_id': int(pid.strip()),
                    'quantity': qty.strip()
                })

        try:
            if not customer_id:
                raise ValueError("Please select a customer.")

            order = OrderService.create_draft_order(
                customer_id=int(customer_id),
                items_data=items_data,
                discount_percentage=discount_percentage,
                user_id=user.id
            )
            flash(f'Sales Order "{order.order_number}" created in Draft status.', 'success')
            return redirect(url_for('orders.view_order', order_id=order.id))

        except Exception as e:
            flash(str(e), 'danger')

    # Fetch active customers and active products for the dropdowns
    customers = Customer.query.filter_by(status='active').order_by(Customer.name.asc()).all()
    products = Product.query.filter_by(status='active').order_by(Product.name.asc()).all()

    # Pre-encode product info into JSON for instant client-side lookup
    products_json = {
        p.id: {
            'product_code': p.product_code,
            'name': p.name,
            'price': float(p.price),
            'stock_quantity': p.stock_quantity
        }
        for p in products
    }

    return render_template(
        'orders/create.html',
        customers=customers,
        products=products,
        products_json=json.dumps(products_json)
    )

@orders_bp.route('/<int:order_id>')
@login_required
def view_order(order_id):
    user = get_current_user()
    order = db.session.get(SalesOrder, order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('orders.list_orders'))

    # PDF Security Requirement: Sales Users must not access another user's orders by changing a URL or order ID
    if user.is_sales_user and order.created_by != user.id:
        abort(403)

    return render_template('orders/detail.html', order=order)

@orders_bp.route('/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
    user = get_current_user()
    order = db.session.get(SalesOrder, order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('orders.list_orders'))

    # Security Check
    if user.is_sales_user and order.created_by != user.id:
        abort(403)

    # PDF Rule: "Allow quantities to be changed and rows to be removed while the order is Draft."
    if not order.is_draft:
        flash('Only Draft orders can be edited.', 'warning')
        return redirect(url_for('orders.view_order', order_id=order.id))

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        discount_percentage = request.form.get('discount_percentage', '0.00')

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')

        items_data = []
        for pid, qty in zip(product_ids, quantities):
            if pid and pid.strip():
                items_data.append({
                    'product_id': int(pid.strip()),
                    'quantity': qty.strip()
                })

        try:
            if not customer_id:
                raise ValueError("Please select a customer.")

            OrderService.update_draft_order(
                order_id=order.id,
                customer_id=int(customer_id),
                items_data=items_data,
                discount_percentage=discount_percentage,
                user=user
            )
            flash(f'Sales Order "{order.order_number}" updated successfully.', 'success')
            return redirect(url_for('orders.view_order', order_id=order.id))

        except Exception as e:
            flash(str(e), 'danger')

    customers = Customer.query.filter_by(status='active').order_by(Customer.name.asc()).all()
    products = Product.query.filter_by(status='active').order_by(Product.name.asc()).all()

    products_json = {
        p.id: {
            'product_code': p.product_code,
            'name': p.name,
            'price': float(p.price),
            'stock_quantity': p.stock_quantity
        }
        for p in products
    }

    return render_template(
        'orders/edit.html',
        order=order,
        customers=customers,
        products=products,
        products_json=json.dumps(products_json)
    )

@orders_bp.route('/<int:order_id>/confirm', methods=['POST'])
@login_required
def confirm_order(order_id):
    """Stub for Order Confirmation (will be fully implemented in Step 4)."""
    flash('Order confirmation will be finalized in Step 4 (Order Lifecycle & Concurrency).', 'info')
    return redirect(url_for('orders.view_order', order_id=order_id))

@orders_bp.route('/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    """Stub for Order Cancellation (will be fully implemented in Step 4)."""
    flash('Order cancellation will be finalized in Step 4 (Order Lifecycle & Concurrency).', 'info')
    return redirect(url_for('orders.view_order', order_id=order_id))
