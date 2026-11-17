import base64
import uuid
from decimal import Decimal
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import SalesOrder
from app.extensions import db

def basic_auth_header(email, password):
    token = base64.b64encode(f"{email}:{password}".encode('utf-8')).decode('utf-8')
    return {'Authorization': f'Basic {token}'}

# =========================================================================
# REST API Automated Tests (Part 8 & Part 12)
# =========================================================================

def test_unauthenticated_api_request_returns_401(client):
    """Unauthenticated requests to /api/products must return HTTP 401 with JSON error."""
    response = client.get('/api/products')
    assert response.status_code == 401
    data = response.get_json()
    assert 'error' in data
    assert 'Authentication required' in data['error']


def test_api_login_and_logout(client):
    """API clients can log in via POST /api/auth/login."""
    # Invalid login
    bad_resp = client.post('/api/auth/login', json={'email': 'admin@savyant.com', 'password': 'WrongPassword'})
    assert bad_resp.status_code == 401
    assert 'Invalid email or password' in bad_resp.get_json()['error']

    # Valid login
    good_resp = client.post('/api/auth/login', json={'email': 'admin@savyant.com', 'password': 'Admin@123'})
    assert good_resp.status_code == 200
    data = good_resp.get_json()
    assert data['user']['email'] == 'admin@savyant.com'
    assert data['user']['role'] == 'admin'

    # Can now access protected endpoint
    prod_resp = client.get('/api/products')
    assert prod_resp.status_code == 200

    # Logout
    logout_resp = client.post('/api/auth/logout')
    assert logout_resp.status_code == 200


def test_get_products_with_search_and_pagination(client):
    """GET /api/products returns paginated active products with search support."""
    headers = basic_auth_header('admin@savyant.com', 'Admin@123')

    # 1. Basic listing
    response = client.get('/api/products?page=1&per_page=5', headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert 'products' in data
    assert 'total' in data
    assert 'page' in data
    assert data['page'] == 1
    assert len(data['products']) <= 5

    # 2. Search by query
    search_resp = client.get('/api/products?q=Keyboard', headers=headers)
    assert search_resp.status_code == 200
    s_data = search_resp.get_json()
    assert any('Keyboard' in p['name'] for p in s_data['products'])


def test_post_orders_create_draft(client, app):
    """POST /api/orders creates a new order in Draft status."""
    headers = basic_auth_header('admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        p1 = Product(product_code=f'API1-{uid}', name='API Product 1', price=Decimal('200.00'), stock_quantity=10, status='active')
        p2 = Product(product_code=f'API2-{uid}', name='API Product 2', price=Decimal('100.00'), stock_quantity=10, status='active')
        cust = Customer(name=f'API Customer {uid}', status='active')
        db.session.add_all([p1, p2, cust])
        db.session.commit()
        p1_id, p2_id, cust_id = p1.id, p2.id, cust.id

    payload = {
        'customer_id': cust_id,
        'discount_percentage': 10.0,
        'items': [
            {'product_id': p1_id, 'quantity': 2},
            {'product_id': p2_id, 'quantity': 1}
        ]
    }
    # 2x 200 + 1x 100 = 500, 10% discount = 50, grand total = 450
    response = client.post('/api/orders', json=payload, headers=headers)
    assert response.status_code == 201
    data = response.get_json()
    assert 'order' in data
    order = data['order']
    assert order['status'] == 'draft'
    assert order['subtotal'] == 500.0
    assert order['discount_amount'] == 50.0
    assert order['grand_total'] == 450.0
    assert len(order['items']) == 2


def test_post_orders_validation_errors(client, app):
    """POST /api/orders returns HTTP 400 for invalid inputs."""
    headers = basic_auth_header('admin@savyant.com', 'Admin@123')
    with app.app_context():
        cust = Customer.query.filter_by(status='active').first()
        prod = Product.query.filter_by(status='active').first()
        cust_id, prod_id = cust.id, prod.id

    # 1. Missing customer_id
    r1 = client.post('/api/orders', json={'items': [{'product_id': prod_id, 'quantity': 1}]}, headers=headers)
    assert r1.status_code == 400
    assert 'customer_id is required' in r1.get_json()['error']

    # 2. Empty items
    r2 = client.post('/api/orders', json={'customer_id': cust_id, 'items': []}, headers=headers)
    assert r2.status_code == 400

    # 3. Duplicate products in same order
    r3 = client.post('/api/orders', json={
        'customer_id': cust_id,
        'items': [
            {'product_id': prod_id, 'quantity': 1},
            {'product_id': prod_id, 'quantity': 2}
        ]
    }, headers=headers)
    assert r3.status_code == 400
    assert 'Duplicate products' in r3.get_json()['error']

    # 4. Discount > 20%
    r4 = client.post('/api/orders', json={
        'customer_id': cust_id,
        'discount_percentage': 25.0,
        'items': [{'product_id': prod_id, 'quantity': 1}]
    }, headers=headers)
    assert r4.status_code == 400
    assert 'between 0% and 20%' in r4.get_json()['error']


def test_get_order_by_id_and_idor_protection(client, app):
    """GET /api/orders/{id} returns order details and enforces IDOR permissions."""
    admin_headers = basic_auth_header('admin@savyant.com', 'Admin@123')
    sales_headers = basic_auth_header('sales@savyant.com', 'Sales@123')

    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        cust = Customer.query.filter_by(status='active').first()
        admin_order = SalesOrder(
            order_number=f'SO-API-ADM-{uid}',
            customer_id=cust.id,
            status='draft',
            created_by=1  # Admin
        )
        db.session.add(admin_order)
        db.session.commit()
        admin_order_id = admin_order.id

    # 1. Admin can access order
    resp1 = client.get(f'/api/orders/{admin_order_id}', headers=admin_headers)
    assert resp1.status_code == 200
    assert resp1.get_json()['order']['id'] == admin_order_id

    # 2. Sales User accessing Admin's order returns HTTP 403 Forbidden!
    resp2 = client.get(f'/api/orders/{admin_order_id}', headers=sales_headers)
    assert resp2.status_code == 403
    assert 'Forbidden' in resp2.get_json()['error']

    # 3. Non-existent order returns HTTP 404 Not Found
    resp3 = client.get('/api/orders/999999', headers=admin_headers)
    assert resp3.status_code == 404


def test_api_confirm_and_cancel_order(client, app):
    """POST /api/orders/{id}/confirm and POST /api/orders/{id}/cancel."""
    headers = basic_auth_header('admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        prod = Product(product_code=f'API-CF-{uid}', name='API Confirm Item', price=Decimal('150.00'), stock_quantity=10, status='active')
        cust = Customer(name=f'Cust API CF {uid}', status='active')
        db.session.add_all([prod, cust])
        db.session.commit()
        prod_id, cust_id = prod.id, cust.id

    # Create order via API
    create_resp = client.post('/api/orders', json={
        'customer_id': cust_id,
        'discount_percentage': 0,
        'items': [{'product_id': prod_id, 'quantity': 3}]
    }, headers=headers)
    assert create_resp.status_code == 201
    order_id = create_resp.get_json()['order']['id']

    # 1. Confirm order via API -> status 200, stock deducted from 10 to 7
    confirm_resp = client.post(f'/api/orders/{order_id}/confirm', headers=headers)
    assert confirm_resp.status_code == 200
    assert confirm_resp.get_json()['order']['status'] == 'confirmed'

    with app.app_context():
        assert db.session.get(Product, prod_id).stock_quantity == 7

    # 2. Cancel order via API -> status 200, stock restored from 7 to 10
    cancel_resp = client.post(f'/api/orders/{order_id}/cancel', headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.get_json()['order']['status'] == 'cancelled'

    with app.app_context():
        assert db.session.get(Product, prod_id).stock_quantity == 10
