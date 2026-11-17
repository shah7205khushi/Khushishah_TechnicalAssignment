from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.routes.auth import login_required, admin_required, get_current_user
from app.models.product import Product
from app.models.order import SalesOrderItem
from app.models.stock_movement import StockMovement
from app.extensions import db

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@login_required
def list_products():
    user = get_current_user()
    query = Product.query

    # Sales Users can only view active products (PDF Requirement)
    if user.is_sales_user:
        query = query.filter_by(status='active')
    else:
        status_filter = request.args.get('status', '').strip().lower()
        if status_filter in ['active', 'inactive']:
            query = query.filter_by(status=status_filter)

    # Search filter: by product code or name (PDF Requirement)
    search_query = request.args.get('q', '').strip()
    if search_query:
        like_term = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Product.product_code.ilike(like_term),
                Product.name.ilike(like_term)
            )
        )

    # Category filter (PDF Requirement)
    category_filter = request.args.get('category', '').strip()
    if category_filter:
        query = query.filter_by(category=category_filter)

    products = query.order_by(Product.product_code.asc()).all()

    # Get distinct categories for the filter dropdown
    categories = [
        c[0] for c in db.session.query(Product.category).distinct().order_by(Product.category).all() if c[0]
    ]

    # Pre-calculate reference status for safe deletion check
    product_data = []
    for p in products:
        order_ref_count = SalesOrderItem.query.filter_by(product_id=p.id).count()
        movement_ref_count = StockMovement.query.filter_by(product_id=p.id).count()
        has_refs = (order_ref_count > 0 or movement_ref_count > 0)
        product_data.append({
            'product': p,
            'order_ref_count': order_ref_count,
            'movement_ref_count': movement_ref_count,
            'can_delete': not has_refs
        })

    return render_template(
        'products/list.html',
        product_data=product_data,
        categories=categories,
        search_query=search_query,
        current_status=request.args.get('status', ''),
        current_category=category_filter
    )

@products_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_product():
    user = get_current_user()
    if request.method == 'POST':
        product_code = request.form.get('product_code', '').strip().upper()
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        price_str = request.form.get('price', '').strip()
        stock_str = request.form.get('stock_quantity', '0').strip()
        status = request.form.get('status', 'active').strip().lower()

        # Backend Validations
        if not product_code or not name:
            flash('Product code and name are required.', 'danger')
            return render_template('products/form.html', product=None, action='Create')

        # Validate unique product code
        existing = Product.query.filter(db.func.upper(Product.product_code) == product_code).first()
        if existing:
            flash(f'Product code "{product_code}" already exists. Please use a unique code.', 'danger')
            return render_template('products/form.html', product=None, action='Create')

        # Validate non-negative price
        try:
            price = Decimal(price_str)
            if price < Decimal('0.00'):
                flash('Price cannot be negative.', 'danger')
                return render_template('products/form.html', product=None, action='Create')
        except Exception:
            flash('Please enter a valid numeric price.', 'danger')
            return render_template('products/form.html', product=None, action='Create')

        # Validate non-negative integer stock
        try:
            stock_quantity = int(stock_str)
            if stock_quantity < 0:
                flash('Stock quantity cannot be negative.', 'danger')
                return render_template('products/form.html', product=None, action='Create')
        except ValueError:
            flash('Stock quantity must be a whole number.', 'danger')
            return render_template('products/form.html', product=None, action='Create')

        if status not in ['active', 'inactive']:
            status = 'active'

        # Create Product
        new_product = Product(
            product_code=product_code,
            name=name,
            category=category or None,
            price=price,
            stock_quantity=stock_quantity,
            status=status
        )
        db.session.add(new_product)
        db.session.flush()  # Flush to obtain new_product.id

        # If opening stock > 0, record initial StockMovement
        if stock_quantity > 0:
            movement = StockMovement(
                product_id=new_product.id,
                movement_type='OPENING_STOCK',
                quantity_change=stock_quantity,
                reason='Initial opening stock at product creation',
                created_by=user.id
            )
            db.session.add(movement)

        db.session.commit()
        flash(f'Product "{product_code} - {name}" created successfully.', 'success')
        return redirect(url_for('products.list_products'))

    return render_template('products/form.html', product=None, action='Create')

@products_bp.route('/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products.list_products'))

    if request.method == 'POST':
        product_code = request.form.get('product_code', '').strip().upper()
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        price_str = request.form.get('price', '').strip()
        status = request.form.get('status', 'active').strip().lower()

        # Validation
        if not product_code or not name:
            flash('Product code and name are required.', 'danger')
            return render_template('products/form.html', product=product, action='Edit')

        # Check unique product code excluding self
        existing = Product.query.filter(
            db.func.upper(Product.product_code) == product_code,
            Product.id != product.id
        ).first()
        if existing:
            flash(f'Product code "{product_code}" is already in use by another product.', 'danger')
            return render_template('products/form.html', product=product, action='Edit')

        try:
            price = Decimal(price_str)
            if price < Decimal('0.00'):
                flash('Price cannot be negative.', 'danger')
                return render_template('products/form.html', product=product, action='Edit')
        except Exception:
            flash('Please enter a valid numeric price.', 'danger')
            return render_template('products/form.html', product=product, action='Edit')

        if status not in ['active', 'inactive']:
            status = 'active'

        product.product_code = product_code
        product.name = name
        product.category = category or None
        product.price = price
        product.status = status

        db.session.commit()
        flash(f'Product "{product_code}" updated successfully.', 'success')
        return redirect(url_for('products.list_products'))

    return render_template('products/form.html', product=product, action='Edit')

@products_bp.route('/<int:product_id>/delete', methods=['POST'])
@admin_required
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products.list_products'))

    # PDF Requirement: "Delete products only when no order or stock movement references them. Prevent deletion; allow deactivation instead."
    order_ref_count = SalesOrderItem.query.filter_by(product_id=product.id).count()
    movement_ref_count = StockMovement.query.filter_by(product_id=product.id).count()

    if order_ref_count > 0 or movement_ref_count > 0:
        flash(
            f'Cannot delete product "{product.product_code}" because it is referenced by '
            f'{order_ref_count} order item(s) and {movement_ref_count} inventory movement(s). '
            f'Please deactivate the product instead.',
            'warning'
        )
        return redirect(url_for('products.list_products'))

    code = product.product_code
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{code}" was successfully deleted.', 'success')
    return redirect(url_for('products.list_products'))

@products_bp.route('/<int:product_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_status(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products.list_products'))

    new_status = 'inactive' if product.status == 'active' else 'active'
    product.status = new_status
    db.session.commit()
    flash(f'Product "{product.product_code}" status changed to {new_status}.', 'info')
    return redirect(url_for('products.list_products'))

@products_bp.route('/<int:product_id>/adjust-stock', methods=['GET', 'POST'])
@admin_required
def adjust_stock(product_id):
    """
    Part 6 Requirement:
    Allow Admin users to increase or decrease stock with a mandatory reason.
    Every adjustment must create a stock movement record.
    Reject adjustments that would make stock negative.
    """
    user = get_current_user()
    product = db.session.get(Product, product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products.list_products'))

    if request.method == 'POST':
        adjustment_type = request.form.get('adjustment_type', 'increase')
        qty_str = request.form.get('quantity', '').strip()
        reason = request.form.get('reason', '').strip()

        # Validation: Mandatory reason
        if not reason:
            flash('A mandatory explanation/reason is required for inventory adjustments.', 'danger')
            return render_template('products/adjust_stock.html', product=product)

        # Validation: Quantity
        try:
            qty = int(qty_str)
            if qty <= 0:
                flash('Adjustment quantity must be greater than zero.', 'danger')
                return render_template('products/adjust_stock.html', product=product)
        except ValueError:
            flash('Please enter a valid whole number quantity.', 'danger')
            return render_template('products/adjust_stock.html', product=product)

        # Concurrency safety: Lock row for update
        locked_product = db.session.query(Product).with_for_update().filter_by(id=product.id).one()

        if adjustment_type == 'decrease':
            if locked_product.stock_quantity < qty:
                flash(
                    f'Cannot decrease stock by {qty}. Current available stock is only {locked_product.stock_quantity}.',
                    'danger'
                )
                return render_template('products/adjust_stock.html', product=product)
            quantity_change = -qty
            locked_product.stock_quantity -= qty
        else:
            quantity_change = qty
            locked_product.stock_quantity += qty

        # Create audit record in stock_movements
        movement = StockMovement(
            product_id=locked_product.id,
            movement_type='MANUAL_ADJUSTMENT',
            quantity_change=quantity_change,
            reason=reason,
            created_by=user.id
        )
        db.session.add(movement)
        db.session.commit()

        flash(
            f'Stock for "{locked_product.product_code}" adjusted by {quantity_change:+d}. '
            f'New stock balance: {locked_product.stock_quantity}.',
            'success'
        )
        return redirect(url_for('products.list_products'))

    return render_template('products/adjust_stock.html', product=product)

@products_bp.route('/import-csv')
@admin_required
def import_csv():
    return render_template('products/import_csv.html')

@products_bp.route('/<int:product_id>/info', methods=['GET'])
@login_required
def get_product_info(product_id):
    """JSON helper for dynamic frontend row calculation."""
    product = db.session.get(Product, product_id)
    if not product:
        return {'error': 'Product not found'}, 404
    return {
        'id': product.id,
        'product_code': product.product_code,
        'name': product.name,
        'price': float(product.price),
        'stock_quantity': product.stock_quantity,
        'status': product.status
    }

@products_bp.route('/stock-movements')
@login_required
def stock_movements_history():
    """
    Part 6 & Part 9 Requirement:
    Stock Movement History: Product, movement type, quantity change, order, reason and timestamp.
    """
    movements = (
        StockMovement.query
        .order_by(StockMovement.id.desc())
        .limit(200)
        .all()
    )
    return render_template('products/stock_movements.html', movements=movements)
