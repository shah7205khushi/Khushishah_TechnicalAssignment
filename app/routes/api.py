import math
from flask import Blueprint, request, jsonify, session
from app.routes.auth import login_required, get_current_user
from app.models.product import Product
from app.models.order import SalesOrder
from app.models.user import User
from app.services.order_service import OrderService
from app.extensions import db

api_bp = Blueprint('api', __name__, url_prefix='/api')

# =========================================================================
# Authentication Helpers for API Clients (cURL / Postman)
# =========================================================================

@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """Authenticate an API client and establish a session."""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password.'}), 401

    session.clear()
    session['user_id'] = user.id
    session['user_name'] = user.name
    session['user_email'] = user.email
    session['role'] = user.role

    return jsonify({
        'message': 'Logged in successfully.',
        'user': user.to_dict()
    }), 200

@api_bp.route('/auth/logout', methods=['POST'])
def api_logout():
    """Clear session for API client."""
    session.clear()
    return jsonify({'message': 'Logged out successfully.'}), 200


# =========================================================================
# 1. GET /api/products - List active products with search & pagination
# =========================================================================

@api_bp.route('/products', methods=['GET'])
@login_required
def get_products():
    """
    List active products with search and pagination.
    Query parameters:
      - q: search term matching product code or name
      - category: filter by category
      - page: page number (default: 1)
      - per_page: items per page (default: 10, max: 100)
    """
    user = get_current_user()
    query = Product.query

    # Sales Users only see active products
    if user.is_sales_user:
        query = query.filter_by(status='active')
    else:
        status_param = request.args.get('status', 'active').strip().lower()
        if status_param in ['active', 'inactive']:
            query = query.filter_by(status=status_param)

    # Search filter
    q = request.args.get('q', '').strip()
    if q:
        like_term = f"%{q}%"
        query = query.filter(
            db.or_(
                Product.product_code.ilike(like_term),
                Product.name.ilike(like_term)
            )
        )

    # Category filter
    category = request.args.get('category', '').strip()
    if category:
        query = query.filter_by(category=category)

    # Pagination
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 10))))
    except (ValueError, TypeError):
        page = 1
        per_page = 10

    total = query.count()
    products = (
        query.order_by(Product.product_code.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify({
        'products': [p.to_dict() for p in products],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': math.ceil(total / per_page) if per_page else 1
    }), 200


# =========================================================================
# 2. POST /api/orders - Create a Draft order
# =========================================================================

@api_bp.route('/orders', methods=['POST'])
@login_required
def create_order():
    """
    Create a new sales order in Draft status.
    Payload:
      {
        "customer_id": 1,
        "discount_percentage": 10.0,
        "items": [
          {"product_id": 1, "quantity": 2},
          {"product_id": 2, "quantity": 3}
        ]
      }
    """
    user = get_current_user()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Malformed or missing JSON body in request.'}), 400

    customer_id = data.get('customer_id')
    if not customer_id:
        return jsonify({'error': 'customer_id is required.'}), 400

    items = data.get('items')
    if not items or not isinstance(items, list):
        return jsonify({'error': 'items list is required and must contain at least one item.'}), 400

    discount_percentage = data.get('discount_percentage', 0.0)

    try:
        order = OrderService.create_draft_order(
            customer_id=int(customer_id),
            items_data=items,
            discount_percentage=discount_percentage,
            user_id=user.id
        )
        return jsonify({
            'message': 'Sales order created successfully in Draft status.',
            'order': order.to_dict()
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f"Failed to create order: {str(e)}"}), 500


# =========================================================================
# 3. GET /api/orders/{id} - Retrieve an accessible order and its items
# =========================================================================

@api_bp.route('/orders/<int:order_id>', methods=['GET'])
@login_required
def get_order(order_id):
    """
    Retrieve an accessible order and its line items.
    Sales Users can only access their own orders (IDOR protected).
    """
    user = get_current_user()
    order = db.session.get(SalesOrder, order_id)
    if not order:
        return jsonify({'error': f"Sales order with ID {order_id} not found."}), 404

    # Permission check (IDOR protection)
    if user.is_sales_user and order.created_by != user.id:
        return jsonify({'error': 'Forbidden: You do not have permission to access this order.'}), 403

    return jsonify({
        'order': order.to_dict()
    }), 200


# =========================================================================
# 4. POST /api/orders/{id}/confirm - Confirm an order and deduct stock
# =========================================================================

@api_bp.route('/orders/<int:order_id>/confirm', methods=['POST'])
@login_required
def confirm_order(order_id):
    """
    Confirm a Draft order and deduct inventory atomically.
    """
    user = get_current_user()
    order = db.session.get(SalesOrder, order_id)
    if not order:
        return jsonify({'error': f"Sales order with ID {order_id} not found."}), 404

    try:
        confirmed_order = OrderService.confirm_order(order_id, user)
        return jsonify({
            'message': f"Order {confirmed_order.order_number} confirmed and inventory deducted successfully.",
            'order': confirmed_order.to_dict()
        }), 200

    except PermissionError:
        return jsonify({'error': 'Forbidden: You do not have permission to confirm this order.'}), 403
    except ValueError as e:
        # Business logic errors (insufficient stock, already confirmed, not draft)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f"Order confirmation failed: {str(e)}"}), 500


# =========================================================================
# 5. POST /api/orders/{id}/cancel - Cancel an order and restore stock
# =========================================================================

@api_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    """
    Cancel an order (restores stock if the order was Confirmed).
    """
    user = get_current_user()
    order = db.session.get(SalesOrder, order_id)
    if not order:
        return jsonify({'error': f"Sales order with ID {order_id} not found."}), 404

    try:
        cancelled_order = OrderService.cancel_order(order_id, user)
        return jsonify({
            'message': f"Order {cancelled_order.order_number} cancelled successfully.",
            'order': cancelled_order.to_dict()
        }), 200

    except PermissionError:
        return jsonify({'error': 'Forbidden: You do not have permission to cancel this order.'}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f"Order cancellation failed: {str(e)}"}), 500
