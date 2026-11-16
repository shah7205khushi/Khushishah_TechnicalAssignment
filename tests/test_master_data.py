import uuid
from decimal import Decimal
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import SalesOrder, SalesOrderItem
from app.models.stock_movement import StockMovement
from app.extensions import db

def login(client, email='admin@savyant.com', password='Admin@123'):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

# =========================================================================
# Customer Master Tests
# =========================================================================

def test_admin_create_customer(client, app):
    """Admin can create a customer with valid data."""
    unique_name = f"Test Cust {uuid.uuid4().hex[:6]}"
    login(client, 'admin@savyant.com', 'Admin@123')
    response = client.post('/customers/create', data={
        'name': unique_name,
        'email': f'{unique_name.replace(" ", "")}@test.com',
        'mobile': '9898989898',
        'city': 'Mumbai',
        'status': 'active'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"created successfully" in response.data

    with app.app_context():
        c = Customer.query.filter_by(name=unique_name).first()
        assert c is not None
        assert c.status == 'active'


def test_customer_creation_validation(client):
    """Customer creation requires a non-empty name."""
    login(client, 'admin@savyant.com', 'Admin@123')
    response = client.post('/customers/create', data={
        'name': '   ',
        'email': 'bad@test.com'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Customer name is required" in response.data


def test_customer_search_and_filter(client):
    """Search by name/email/mobile and filter by status."""
    login(client, 'admin@savyant.com', 'Admin@123')
    # Search by email (seeded)
    response = client.get('/customers/?q=techcore')
    assert response.status_code == 200
    assert b"TechCore Enterprises" in response.data

    # Filter inactive (seeded)
    response = client.get('/customers/?status=inactive')
    assert response.status_code == 200
    assert b"Dormant Enterprise" in response.data


def test_customer_safe_deletion(client, app):
    """
    PDF Requirement: Delete customers only when no order references them.
    Prevent deletion of customers referenced by orders; allow deactivation instead.
    """
    uid = uuid.uuid4().hex[:6]
    login(client, 'admin@savyant.com', 'Admin@123')
    with app.app_context():
        cust = Customer(name=f'Ref Cust {uid}', email=f'ref_{uid}@cust.com', status='active')
        db.session.add(cust)
        db.session.flush()

        order = SalesOrder(
            order_number=f'SO-TEST-{uid.upper()}',
            customer_id=cust.id,
            status='draft',
            created_by=1
        )
        db.session.add(order)
        db.session.commit()
        cust_id = cust.id

    # Attempt to delete referenced customer
    response = client.post(f'/customers/{cust_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    assert b"Cannot delete customer" in response.data
    assert b"deactivate this customer instead" in response.data

    # Verify customer still exists in DB
    with app.app_context():
        assert db.session.get(Customer, cust_id) is not None

    # Now create an unreferenced customer and verify deletion succeeds
    with app.app_context():
        unref_cust = Customer(name=f'Unref Cust {uid}', email=f'unref_{uid}@cust.com', status='active')
        db.session.add(unref_cust)
        db.session.commit()
        unref_id = unref_cust.id

    response = client.post(f'/customers/{unref_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    assert b"was successfully deleted" in response.data

    with app.app_context():
        assert db.session.get(Customer, unref_id) is None


# =========================================================================
# Product Master Tests
# =========================================================================

def test_admin_create_product(client, app):
    """Admin can create a product with valid code, name, price and stock."""
    code = f"PRD-{uuid.uuid4().hex[:5].upper()}"
    login(client, 'admin@savyant.com', 'Admin@123')
    response = client.post('/products/create', data={
        'product_code': code,
        'name': f'Switch {code}',
        'category': 'Hardware',
        'price': '750.50',
        'stock_quantity': '10',
        'status': 'active'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"created successfully" in response.data

    with app.app_context():
        p = Product.query.filter_by(product_code=code).first()
        assert p is not None
        assert p.price == Decimal('750.50')
        assert p.stock_quantity == 10
        # Check that opening stock was logged
        movement = StockMovement.query.filter_by(product_id=p.id, movement_type='OPENING_STOCK').first()
        assert movement is not None
        assert movement.quantity_change == 10


def test_product_unique_code_validation(client):
    """Reject duplicate product codes."""
    login(client, 'admin@savyant.com', 'Admin@123')
    # PRD-001 already seeded
    response = client.post('/products/create', data={
        'product_code': 'PRD-001',
        'name': 'Duplicate Code Product',
        'price': '100.00',
        'stock_quantity': '5'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"already exists" in response.data


def test_product_negative_values_rejected(client):
    """Prevent negative price and stock quantities."""
    uid = uuid.uuid4().hex[:4].upper()
    login(client, 'admin@savyant.com', 'Admin@123')
    # Negative price
    response = client.post('/products/create', data={
        'product_code': f'PRD-N1-{uid}',
        'name': 'Negative Price',
        'price': '-50.00',
        'stock_quantity': '10'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Price cannot be negative" in response.data

    # Negative stock
    response = client.post('/products/create', data={
        'product_code': f'PRD-N2-{uid}',
        'name': 'Negative Stock',
        'price': '50.00',
        'stock_quantity': '-5'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Stock quantity cannot be negative" in response.data


def test_product_safe_deletion(client, app):
    """
    PDF Requirement: Delete products only when no order or stock movement references them.
    """
    uid = uuid.uuid4().hex[:5].upper()
    login(client, 'admin@savyant.com', 'Admin@123')
    with app.app_context():
        p = Product(product_code=f'PRD-R-{uid}', name='Referenced Product', price=100, stock_quantity=0)
        db.session.add(p)
        db.session.flush()

        movement = StockMovement(
            product_id=p.id,
            movement_type='OPENING_STOCK',
            quantity_change=5,
            created_by=1
        )
        db.session.add(movement)
        db.session.commit()
        pid = p.id

    # Attempt to delete product referenced by stock movement
    response = client.post(f'/products/{pid}/delete', follow_redirects=True)
    assert response.status_code == 200
    assert b"Cannot delete product" in response.data
    assert b"deactivate the product instead" in response.data

    with app.app_context():
        assert db.session.get(Product, pid) is not None


def test_stock_adjustment(client, app):
    """
    Part 6 Requirement:
    Allow Admin to increase or decrease stock with mandatory reason.
    Every adjustment must create a stock movement record.
    Reject adjustments that would make stock negative.
    """
    uid = uuid.uuid4().hex[:5].upper()
    login(client, 'admin@savyant.com', 'Admin@123')
    with app.app_context():
        prod = Product(product_code=f'PRD-A-{uid}', name='Stock Adj Test', price=200, stock_quantity=20)
        db.session.add(prod)
        db.session.commit()
        prod_id = prod.id

    # 1. Increase stock by 10
    response = client.post(f'/products/{prod_id}/adjust-stock', data={
        'adjustment_type': 'increase',
        'quantity': '10',
        'reason': 'Received inventory shipment'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"New stock balance: 30" in response.data

    # 2. Reject missing reason
    response = client.post(f'/products/{prod_id}/adjust-stock', data={
        'adjustment_type': 'decrease',
        'quantity': '5',
        'reason': '   '
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"mandatory explanation/reason is required" in response.data

    # 3. Reject adjustment that would make stock negative
    response = client.post(f'/products/{prod_id}/adjust-stock', data={
        'adjustment_type': 'decrease',
        'quantity': '50',  # Current stock is 30
        'reason': 'Excessive deduction'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Cannot decrease stock" in response.data


def test_sales_user_cannot_modify_master_data(client):
    """
    Access Rule: Only Admin users may modify master data.
    Sales users view active customers and products.
    """
    login(client, 'sales@savyant.com', 'Sales@123')

    # Cannot access customer create
    response = client.post('/customers/create', data={'name': 'Illegal Customer'}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Administrator privileges required" in response.data

    # Cannot access product create
    response = client.post('/products/create', data={'product_code': 'ILL-01', 'name': 'Illegal'}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Administrator privileges required" in response.data

    # Sales user customer list hides inactive customers
    response = client.get('/customers/')
    assert response.status_code == 200
    assert b"Acme Retail Solutions" in response.data  # active
    assert b"Dormant Enterprise" not in response.data  # inactive
