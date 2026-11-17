import uuid
from decimal import Decimal
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import SalesOrder, SalesOrderItem
from app.extensions import db

def login(client, email='admin@savyant.com', password='Admin@123'):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

# =========================================================================
# Order Creation & Calculation Tests (Part 5 & Part 12)
# =========================================================================

def test_order_with_multiple_items_and_discount(client, app):
    """
    Scenario 1 (PDF Page 8 & Page 13):
    Order with multiple items and discount -> Correct subtotal and grand total.
    Example in PDF:
      - 2 Keyboards @ 1,500.00 = 3,000.00
      - 3 Mice @ 500.00 = 1,500.00
      - Subtotal = 4,500.00
      - Discount 10% = 450.00
      - Grand Total = 4,050.00
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    with app.app_context():
        # Setup specific products matching the PDF example
        uid = uuid.uuid4().hex[:4].upper()
        p1 = Product(product_code=f'KB-{uid}', name='Keyboard', price=Decimal('1500.00'), stock_quantity=20, status='active')
        p2 = Product(product_code=f'MS-{uid}', name='Mouse', price=Decimal('500.00'), stock_quantity=50, status='active')
        cust = Customer(name=f'Cust Calc {uid}', status='active')
        db.session.add_all([p1, p2, cust])
        db.session.commit()

        p1_id, p2_id, cust_id = p1.id, p2.id, cust.id

    # Create order via web POST
    response = client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '10.0',
        'product_id[]': [p1_id, p2_id],
        'quantity[]': ['2', '3']
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"created in Draft status" in response.data

    with app.app_context():
        order = SalesOrder.query.filter_by(customer_id=cust_id).first()
        assert order is not None
        assert order.status == 'draft'
        assert order.subtotal == Decimal('4500.00')
        assert order.discount_percentage == Decimal('10.00')
        assert order.discount_amount == Decimal('450.00')
        assert order.grand_total == Decimal('4050.00')
        assert len(order.items) == 2


def test_zero_or_negative_quantity_rejected(client, app):
    """
    Scenario 2 (PDF Page 13):
    Zero or negative quantity -> Rejected.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    with app.app_context():
        cust = Customer.query.filter_by(status='active').first()
        prod = Product.query.filter_by(status='active').first()
        cust_id, prod_id = cust.id, prod.id

    # Test quantity = 0
    resp1 = client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['0']
    }, follow_redirects=True)
    assert resp1.status_code == 200
    assert b"Quantity must be a positive whole number" in resp1.data

    # Test negative quantity
    resp2 = client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['-3']
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert b"Quantity must be a positive whole number" in resp2.data


def test_discount_outside_0_to_20_rejected(client, app):
    """
    Scenario 3 (PDF Page 13):
    Discount outside 0–20% -> Rejected.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    with app.app_context():
        cust = Customer.query.filter_by(status='active').first()
        prod = Product.query.filter_by(status='active').first()
        cust_id, prod_id = cust.id, prod.id

    # Test discount > 20%
    resp1 = client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '25.0',
        'product_id[]': [prod_id],
        'quantity[]': ['1']
    }, follow_redirects=True)
    assert resp1.status_code == 200
    assert b"Discount percentage must be between 0% and 20%" in resp1.data

    # Test negative discount
    resp2 = client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '-5.0',
        'product_id[]': [prod_id],
        'quantity[]': ['1']
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert b"Discount percentage must be between 0% and 20%" in resp2.data


def test_reject_duplicate_products_within_same_order(client, app):
    """
    PDF Part 5 Rule: Reject duplicate products within the same order.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    with app.app_context():
        cust = Customer.query.filter_by(status='active').first()
        prod = Product.query.filter_by(status='active').first()
        cust_id, prod_id = cust.id, prod.id

    response = client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id, prod_id],  # Duplicate
        'quantity[]': ['1', '2']
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Duplicate products are not allowed" in response.data


def test_price_is_snapshotted_on_order_item(client, app):
    """
    PDF Part 5 Rule:
    Store rate on the order so later product price changes do not change existing orders.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        prod = Product(product_code=f'SNP-{uid}', name='Snapshot Prod', price=Decimal('100.00'), stock_quantity=10, status='active')
        cust = Customer(name=f'Cust Snapshot {uid}', status='active')
        db.session.add_all([prod, cust])
        db.session.commit()
        prod_id, cust_id = prod.id, cust.id

    # Create order at price 100
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['2']
    })

    # Now change product price in master data from 100 to 500
    with app.app_context():
        p = db.session.get(Product, prod_id)
        p.price = Decimal('500.00')
        db.session.commit()

        # Existing order must still reflect rate 100 and total 200!
        order = SalesOrder.query.filter_by(customer_id=cust_id).first()
        assert order.subtotal == Decimal('200.00')
        assert order.grand_total == Decimal('200.00')
        assert order.items[0].rate == Decimal('100.00')


def test_sales_user_cannot_access_another_users_order(client, app):
    """
    Scenario 8 (PDF Page 6 & Page 13):
    Sales User accesses another user's order -> Access denied.
    """
    # 1. Admin creates an order
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        cust = Customer.query.filter_by(status='active').first()
        prod = Product.query.filter_by(status='active').first()
        admin_order = SalesOrder(
            order_number=f'SO-ADM-{uid}',
            customer_id=cust.id,
            status='draft',
            created_by=1  # Admin ID
        )
        db.session.add(admin_order)
        db.session.commit()
        admin_order_id = admin_order.id

    # 2. Logout and login as Sales User
    client.get('/logout')
    login(client, 'sales@savyant.com', 'Sales@123')

    # Attempt to view Admin's order
    response = client.get(f'/orders/{admin_order_id}')
    assert response.status_code == 403

    # Attempt to edit Admin's order
    edit_response = client.get(f'/orders/{admin_order_id}/edit')
    assert edit_response.status_code == 403

def test_edit_draft_order_recalculates_totals(client, app):
    """
    Part 5 Rule: Allow quantities to be changed and rows to be removed while the order is Draft.
    Recalculates totals on backend.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        p1 = Product(product_code=f'ED1-{uid}', name='Edit Prod 1', price=Decimal('200.00'), stock_quantity=10, status='active')
        p2 = Product(product_code=f'ED2-{uid}', name='Edit Prod 2', price=Decimal('100.00'), stock_quantity=10, status='active')
        cust = Customer(name=f'Cust Edit {uid}', status='active')
        db.session.add_all([p1, p2, cust])
        db.session.commit()
        p1_id, p2_id, cust_id = p1.id, p2.id, cust.id

    # Create Draft order: 1x p1 (200) + 1x p2 (100) = 300, 0% discount
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [p1_id, p2_id],
        'quantity[]': ['1', '1']
    })

    with app.app_context():
        order = SalesOrder.query.filter_by(customer_id=cust_id).first()
        assert order.grand_total == Decimal('300.00')
        order_id = order.id

    # Edit order: change p1 quantity to 3, remove p2, add 10% discount -> 3 * 200 = 600 - 10% (60) = 540
    edit_resp = client.post(f'/orders/{order_id}/edit', data={
        'customer_id': cust_id,
        'discount_percentage': '10.0',
        'product_id[]': [p1_id],
        'quantity[]': ['3']
    }, follow_redirects=True)
    assert edit_resp.status_code == 200

    with app.app_context():
        updated_order = db.session.get(SalesOrder, order_id)
        assert updated_order.subtotal == Decimal('600.00')
        assert updated_order.discount_amount == Decimal('60.00')
        assert updated_order.grand_total == Decimal('540.00')
        assert len(updated_order.items) == 1


def test_inactive_customer_cannot_place_order(client, app):
    """Orders can only be created for active customers."""
    login(client, 'admin@savyant.com', 'Admin@123')
    with app.app_context():
        inact_cust = Customer.query.filter_by(status='inactive').first()
        prod = Product.query.filter_by(status='active').first()
        cust_id, prod_id = inact_cust.id, prod.id

    response = client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['1']
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Cannot create orders for inactive customers" in response.data
