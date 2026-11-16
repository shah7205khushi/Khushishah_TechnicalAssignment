from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.routes.auth import login_required, get_current_user
from app.models.order import SalesOrder
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
