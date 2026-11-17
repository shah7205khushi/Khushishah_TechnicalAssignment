import os
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import SalesOrder, SalesOrderItem
from app.services.order_service import OrderService
from app.services.report_service import ReportService
from app.extensions import db

def login(client, email='admin@savyant.com', password='Admin@123'):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

# =========================================================================
# Reports & Analytics Automated Tests (Part 9)
# =========================================================================

def test_customer_sales_summary_logic(app):
    """
    PDF Part 9 Requirement:
    - Customer, confirmed order count, total sales after discount.
    - Support order-date range.
    - Include customers with no Confirmed orders in that range, showing zero totals.
    - Avoid counting one order multiple times because it has multiple item rows.
    """
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        # Setup 2 customers: one with confirmed orders, one with ZERO orders
        c1 = Customer(name=f'Report Cust Active {uid}', status='active')
        c2 = Customer(name=f'Report Cust Zero {uid}', status='active')
        p1 = Product(product_code=f'RP1-{uid}', name='R Prod 1', price=Decimal('100.00'), stock_quantity=50, status='active')
        p2 = Product(product_code=f'RP2-{uid}', name='R Prod 2', price=Decimal('200.00'), stock_quantity=50, status='active')
        db.session.add_all([c1, c2, p1, p2])
        db.session.commit()

        # Create order for c1 with MULTIPLE item rows (2x p1 + 1x p2 = 400.00, 10% discount = 360.00)
        from app.models.user import User
        admin = User.query.filter_by(role='admin').first()
        order = OrderService.create_draft_order(
            customer_id=c1.id,
            items_data=[{'product_id': p1.id, 'quantity': 2}, {'product_id': p2.id, 'quantity': 1}],
            discount_percentage=10.0,
            user_id=admin.id
        )
        # Confirm order
        OrderService.confirm_order(order.id, admin)

        # Generate report
        report = ReportService.get_customer_sales_summary()
        results = {r.customer_name: r for r in report['data']}

        # 1. c1 must have confirmed_order_count = 1 (NOT 2, even though it has 2 item rows!)
        assert results[c1.name].confirmed_order_count == 1
        assert results[c1.name].total_sales_after_discount == Decimal('360.00')

        # 2. c2 must be present in the report with count = 0 and total = 0.00
        assert results[c2.name].confirmed_order_count == 0
        assert results[c2.name].total_sales_after_discount == Decimal('0.00')


def test_product_sales_summary_logic(app):
    """
    PDF Part 9 Requirement:
    - Product, quantity sold, gross item value before order discount.
    - Confirmed orders only.
    """
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        cust = Customer(name=f'Prod Summary Cust {uid}', status='active')
        prod = Product(product_code=f'PSP-{uid}', name='Summary Item', price=Decimal('150.00'), stock_quantity=50, status='active')
        db.session.add_all([cust, prod])
        db.session.commit()

        from app.models.user import User
        admin = User.query.filter_by(role='admin').first()

        # 1. Create and confirm order with 3 units (Gross value = 3 * 150 = 450)
        order1 = OrderService.create_draft_order(
            customer_id=cust.id,
            items_data=[{'product_id': prod.id, 'quantity': 3}],
            discount_percentage=10.0,  # 10% discount applied to order
            user_id=admin.id
        )
        OrderService.confirm_order(order1.id, admin)

        # 2. Create another order with 2 units that remains in DRAFT (should NOT be counted!)
        OrderService.create_draft_order(
            customer_id=cust.id,
            items_data=[{'product_id': prod.id, 'quantity': 2}],
            discount_percentage=0.0,
            user_id=admin.id
        )

        report = ReportService.get_product_sales_summary()
        prod_map = {r.product_code: r for r in report['data']}

        # Must count only the confirmed order: 3 units sold, gross value 450.00 (before order discount)
        assert prod_map[prod.product_code].total_quantity_sold == 3
        assert prod_map[prod.product_code].gross_sales_value == Decimal('450.00')


def test_low_stock_report_logic(app):
    """
    PDF Part 9 Requirement:
    - Products with stock below a user-entered threshold.
    """
    uid = uuid.uuid4().hex[:4].upper()
    with app.app_context():
        p_low = Product(product_code=f'LOW-{uid}', name='Low Stock Item', price=Decimal('50.00'), stock_quantity=3, status='active')
        p_high = Product(product_code=f'HIGH-{uid}', name='High Stock Item', price=Decimal('50.00'), stock_quantity=25, status='active')
        db.session.add_all([p_low, p_high])
        db.session.commit()

        # Query threshold = 5
        report = ReportService.get_low_stock_report(threshold=5)
        codes = [p.product_code for p in report['products']]

        assert p_low.product_code in codes
        assert p_high.product_code not in codes


def test_sales_user_cannot_view_reports(client):
    """
    Access Rule (PDF Part 2):
    Admin manages all orders and views reports. Sales Users cannot view reports.
    """
    login(client, 'sales@savyant.com', 'Sales@123')

    # Cannot view customer sales report
    r1 = client.get('/reports/customer-sales', follow_redirects=True)
    assert r1.status_code == 200
    assert b"Administrator privileges required" in r1.data

    # Cannot view product sales report
    r2 = client.get('/reports/product-sales', follow_redirects=True)
    assert r2.status_code == 200
    assert b"Administrator privileges required" in r2.data


def test_sql_queries_file_exists():
    """Verify sql/queries.sql exists and contains all 5 required queries."""
    filepath = os.path.join('sql', 'queries.sql')
    assert os.path.exists(filepath), "sql/queries.sql file is missing!"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    assert "QUERY 1: Top three customers" in content
    assert "QUERY 2: Top three products" in content
    assert "QUERY 3: Customers who have never placed any order" in content
    assert "QUERY 4: Month-wise Confirmed sales totals" in content
    assert "QUERY 5: Products below a supplied stock threshold" in content
