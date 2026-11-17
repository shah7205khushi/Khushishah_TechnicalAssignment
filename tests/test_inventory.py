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
# Order Lifecycle & Inventory Logic Tests (Part 6 & Part 12)
# =========================================================================

def test_draft_order_does_not_deduct_stock(client, app):
    """
    Part 6 Requirement: Draft orders must not reserve or deduct stock.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        prod = Product(product_code=f'DF-{uid}', name='Draft Prod', price=Decimal('100.00'), stock_quantity=20, status='active')
        cust = Customer(name=f'Cust Draft {uid}', status='active')
        db.session.add_all([prod, cust])
        db.session.commit()
        prod_id, cust_id = prod.id, cust.id

    # Create draft order with qty 5
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['5']
    })

    # Stock must remain unchanged at 20!
    with app.app_context():
        p = db.session.get(Product, prod_id)
        assert p.stock_quantity == 20


def test_confirmation_with_sufficient_stock(client, app):
    """
    Scenario 4 (PDF Page 13):
    Confirmation with sufficient stock -> Order confirmed and stock deducted.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        prod = Product(product_code=f'CF1-{uid}', name='Confirm Prod', price=Decimal('500.00'), stock_quantity=25, status='active')
        cust = Customer(name=f'Cust Confirm {uid}', status='active')
        db.session.add_all([prod, cust])
        db.session.commit()
        prod_id, cust_id = prod.id, cust.id

    # Create draft order with qty 7
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['7']
    })

    with app.app_context():
        order = SalesOrder.query.filter_by(customer_id=cust_id).first()
        order_id = order.id

    # Confirm order
    response = client.post(f'/orders/{order_id}/confirm', follow_redirects=True)
    assert response.status_code == 200
    assert b"successfully CONFIRMED" in response.data

    # Verify stock deducted: 25 - 7 = 18
    with app.app_context():
        p = db.session.get(Product, prod_id)
        assert p.stock_quantity == 18

        o = db.session.get(SalesOrder, order_id)
        assert o.status == 'confirmed'

        movement = StockMovement.query.filter_by(
            product_id=prod_id,
            related_order_id=order_id,
            movement_type='ORDER_CONFIRM'
        ).first()
        assert movement is not None
        assert movement.quantity_change == -7


def test_confirmation_with_one_insufficient_stock_item(client, app):
    """
    Scenario 5 (PDF Page 13):
    Confirmation with one insufficient-stock item -> No stock or status changes (all-or-nothing rollback).
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        # Product 1 has plenty of stock (10)
        p1 = Product(product_code=f'OK-{uid}', name='Sufficient Prod', price=Decimal('100.00'), stock_quantity=10, status='active')
        # Product 2 has insufficient stock (only 2 in stock, but order will ask for 5)
        p2 = Product(product_code=f'SHORT-{uid}', name='Short Prod', price=Decimal('200.00'), stock_quantity=2, status='active')
        cust = Customer(name=f'Cust Short {uid}', status='active')
        db.session.add_all([p1, p2, cust])
        db.session.commit()
        p1_id, p2_id, cust_id = p1.id, p2.id, cust.id

    # Create draft order: 2x p1 + 5x p2
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [p1_id, p2_id],
        'quantity[]': ['2', '5']
    })

    with app.app_context():
        order = SalesOrder.query.filter_by(customer_id=cust_id).first()
        order_id = order.id

    # Attempt to confirm order
    response = client.post(f'/orders/{order_id}/confirm', follow_redirects=True)
    assert response.status_code == 200
    assert b"Insufficient stock" in response.data

    # Verify ALL-OR-NOTHING: order remains draft, NO stock deducted from either product
    with app.app_context():
        o = db.session.get(SalesOrder, order_id)
        assert o.status == 'draft'

        prod1 = db.session.get(Product, p1_id)
        assert prod1.stock_quantity == 10  # Untouched

        prod2 = db.session.get(Product, p2_id)
        assert prod2.stock_quantity == 2   # Untouched

        # No confirm movement logged
        movements = StockMovement.query.filter_by(related_order_id=order_id).all()
        assert len(movements) == 0


def test_repeated_confirmation_does_not_deduct_stock_again(client, app):
    """
    Scenario 6 (PDF Page 13):
    Repeated confirmation -> No additional deduction.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        prod = Product(product_code=f'REP-{uid}', name='Repeat Prod', price=Decimal('300.00'), stock_quantity=20, status='active')
        cust = Customer(name=f'Cust Rep {uid}', status='active')
        db.session.add_all([prod, cust])
        db.session.commit()
        prod_id, cust_id = prod.id, cust.id

    # Create order: qty 4
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['4']
    })

    with app.app_context():
        order = SalesOrder.query.filter_by(customer_id=cust_id).first()
        order_id = order.id

    # First confirmation: Deducts 4 -> stock becomes 16
    resp1 = client.post(f'/orders/{order_id}/confirm', follow_redirects=True)
    assert resp1.status_code == 200
    assert b"successfully CONFIRMED" in resp1.data

    with app.app_context():
        assert db.session.get(Product, prod_id).stock_quantity == 16

    # Repeated confirmation: Must fail and NOT deduct stock again!
    resp2 = client.post(f'/orders/{order_id}/confirm', follow_redirects=True)
    assert resp2.status_code == 200
    assert b"already confirmed" in resp2.data

    with app.app_context():
        # Stock remains exactly 16
        assert db.session.get(Product, prod_id).stock_quantity == 16


def test_cancellation_of_confirmed_order_restores_stock_once(client, app):
    """
    Scenario 7 (PDF Page 13):
    Cancellation of Confirmed order -> Stock restored once.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        prod = Product(product_code=f'CAN-{uid}', name='Cancel Prod', price=Decimal('400.00'), stock_quantity=15, status='active')
        cust = Customer(name=f'Cust Cancel {uid}', status='active')
        db.session.add_all([prod, cust])
        db.session.commit()
        prod_id, cust_id = prod.id, cust.id

    # Create order: qty 5
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['5']
    })

    with app.app_context():
        order = SalesOrder.query.filter_by(customer_id=cust_id).first()
        order_id = order.id

    # Confirm order -> stock decreases from 15 to 10
    client.post(f'/orders/{order_id}/confirm')
    with app.app_context():
        assert db.session.get(Product, prod_id).stock_quantity == 10

    # Cancel confirmed order -> stock restored from 10 back to 15!
    cancel_resp = client.post(f'/orders/{order_id}/cancel', follow_redirects=True)
    assert cancel_resp.status_code == 200
    assert b"has been CANCELLED" in cancel_resp.data

    with app.app_context():
        # Stock restored
        assert db.session.get(Product, prod_id).stock_quantity == 15
        assert db.session.get(SalesOrder, order_id).status == 'cancelled'

        # Check ORDER_CANCEL movement
        cancel_mvt = StockMovement.query.filter_by(
            product_id=prod_id,
            related_order_id=order_id,
            movement_type='ORDER_CANCEL'
        ).first()
        assert cancel_mvt is not None
        assert cancel_mvt.quantity_change == 5

    # Repeated cancellation attempt -> Stock is NOT restored twice
    repeat_cancel = client.post(f'/orders/{order_id}/cancel', follow_redirects=True)
    assert repeat_cancel.status_code == 200
    assert b"already cancelled" in repeat_cancel.data

    with app.app_context():
        assert db.session.get(Product, prod_id).stock_quantity == 15


def test_cancellation_of_draft_order_does_not_change_stock(client, app):
    """
    Part 6 Rule: Draft -> Cancel -> Cancelled (No stock effect).
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        prod = Product(product_code=f'CD-{uid}', name='Cancel Draft Prod', price=Decimal('100.00'), stock_quantity=30, status='active')
        cust = Customer(name=f'Cust CD {uid}', status='active')
        db.session.add_all([prod, cust])
        db.session.commit()
        prod_id, cust_id = prod.id, cust.id

    # Create draft order
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['6']
    })

    with app.app_context():
        order = SalesOrder.query.filter_by(customer_id=cust_id).first()
        order_id = order.id

    # Cancel directly from draft
    client.post(f'/orders/{order_id}/cancel')

    with app.app_context():
        assert db.session.get(Product, prod_id).stock_quantity == 30  # No change
        assert db.session.get(SalesOrder, order_id).status == 'cancelled'
        # No stock movements created
        mvts = StockMovement.query.filter_by(related_order_id=order_id).all()
        assert len(mvts) == 0


def test_confirmed_order_is_read_only(client, app):
    """
    Part 6 Rule: Confirmed and Cancelled orders must be read-only (cannot edit items/quantities).
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        prod = Product(product_code=f'RO-{uid}', name='ReadOnly Prod', price=Decimal('100.00'), stock_quantity=10, status='active')
        cust = Customer(name=f'Cust RO {uid}', status='active')
        db.session.add_all([prod, cust])
        db.session.commit()
        prod_id, cust_id = prod.id, cust.id

    # Create and confirm order
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['1']
    })
    with app.app_context():
        order_id = SalesOrder.query.filter_by(customer_id=cust_id).first().id

    client.post(f'/orders/{order_id}/confirm')

    # Attempt to edit confirmed order
    edit_resp = client.post(f'/orders/{order_id}/edit', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['5']
    }, follow_redirects=True)
    assert edit_resp.status_code == 200
    assert b"Only Draft orders can be edited" in edit_resp.data

def test_concurrent_order_confirmation_prevents_negative_stock(client, app):
    """
    Part 6 Requirement:
    Handle two users attempting to confirm orders for the same limited stock without allowing negative stock.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        # Product has only 5 units in total
        prod = Product(product_code=f'LMT-{uid}', name='Limited Stock Item', price=Decimal('100.00'), stock_quantity=5, status='active')
        cust = Customer(name=f'Cust LMT {uid}', status='active')
        db.session.add_all([prod, cust])
        db.session.commit()
        prod_id, cust_id = prod.id, cust.id

    # User A creates order requesting 4 units
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['4']
    })
    with app.app_context():
        order1 = SalesOrder.query.filter_by(customer_id=cust_id).order_by(SalesOrder.id.desc()).first()
        order1_id = order1.id

    # User B creates order requesting 4 units (both are valid Draft orders!)
    client.post('/orders/create', data={
        'customer_id': cust_id,
        'discount_percentage': '0',
        'product_id[]': [prod_id],
        'quantity[]': ['4']
    })
    with app.app_context():
        order2 = SalesOrder.query.filter_by(customer_id=cust_id).order_by(SalesOrder.id.desc()).first()
        order2_id = order2.id

    assert order1_id != order2_id

    # Confirm Order 1 -> succeeds! Stock reduces from 5 to 1
    resp1 = client.post(f'/orders/{order1_id}/confirm', follow_redirects=True)
    assert resp1.status_code == 200
    assert b"successfully CONFIRMED" in resp1.data

    with app.app_context():
        assert db.session.get(Product, prod_id).stock_quantity == 1

    # Confirm Order 2 -> MUST be rejected because 4 > 1 remaining stock!
    resp2 = client.post(f'/orders/{order2_id}/confirm', follow_redirects=True)
    assert resp2.status_code == 200
    assert b"Insufficient stock" in resp2.data

    with app.app_context():
        # Stock remains at 1, never goes negative!
        p = db.session.get(Product, prod_id)
        assert p.stock_quantity == 1
        assert p.stock_quantity >= 0

        # Order 2 remains in draft
        o2 = db.session.get(SalesOrder, order2_id)
        assert o2.status == 'draft'
