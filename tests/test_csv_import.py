import io
import os
import uuid
from decimal import Decimal
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.services.csv_service import CsvService
from app.extensions import db

def login(client, email='admin@savyant.com', password='Admin@123'):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

# =========================================================================
# CSV Import Automated Tests (Part 10 & Part 12 Scenario 9)
# =========================================================================

def test_valid_csv_import_creates_products_and_opening_movements(client, app):
    """
    Valid CSV import creates all products and logs OPENING_STOCK for products with initial stock.
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    code1 = f'CSV-V1-{uid}'
    code2 = f'CSV-V2-{uid}'

    csv_content = f"""product_code,product_name,category,price,stock_quantity,status
{code1},Batch Webcam,Video,1500.00,20,Active
{code2},Batch Mic,Audio,800.00,0,Inactive
"""
    response = client.post('/products/import-csv', data={
        'csv_file': (io.BytesIO(csv_content.encode('utf-8')), 'test_valid.csv')
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Successfully imported 2 product(s)" in response.data

    with app.app_context():
        p1 = Product.query.filter_by(product_code=code1).first()
        assert p1 is not None
        assert p1.stock_quantity == 20
        assert p1.price == Decimal('1500.00')

        # p1 had stock 20 -> must have OPENING_STOCK movement
        m1 = StockMovement.query.filter_by(product_id=p1.id, movement_type='OPENING_STOCK').first()
        assert m1 is not None
        assert m1.quantity_change == 20

        p2 = Product.query.filter_by(product_code=code2).first()
        assert p2 is not None
        assert p2.stock_quantity == 0
        assert p2.status == 'inactive'


def test_csv_containing_invalid_row_imports_nothing(client, app):
    """
    Scenario 9 (PDF Page 13):
    CSV containing an invalid row -> No products imported (all-or-nothing rollback).
    """
    login(client, 'admin@savyant.com', 'Admin@123')
    uid = uuid.uuid4().hex[:4].upper()
    valid_code = f'CSV-GOOD-{uid}'
    bad_code = f'CSV-BAD-{uid}'

    # Row 2 is valid, Row 3 has a negative price (-50.00)
    csv_content = f"""product_code,product_name,category,price,stock_quantity,status
{valid_code},Good Product,Hardware,100.00,10,Active
{bad_code},Bad Product,Hardware,-50.00,5,Active
"""
    response = client.post('/products/import-csv', data={
        'csv_file': (io.BytesIO(csv_content.encode('utf-8')), 'test_invalid.csv')
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Import failed with 1 error(s)" in response.data
    assert b"Price cannot be negative" in response.data
    assert b"Row 3" in response.data

    # Verify that NEITHER product was imported into the database!
    with app.app_context():
        assert Product.query.filter_by(product_code=valid_code).first() is None
        assert Product.query.filter_by(product_code=bad_code).first() is None


def test_csv_rejects_duplicate_codes_in_file(app):
    """CSV rejects duplicate product codes within the same file."""
    uid = uuid.uuid4().hex[:4].upper()
    dup_code = f'DUP-{uid}'

    csv_content = f"""product_code,product_name,category,price,stock_quantity,status
{dup_code},First Item,Cat,100,5,Active
{dup_code},Second Item,Cat,200,10,Active
"""
    from app.models.user import User
    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        result = CsvService.parse_and_validate_csv(csv_content, admin)

        assert result['success'] is False
        assert any("Duplicate product code" in err['reason'] for err in result['errors'])
        assert any(err['row'] == 3 for err in result['errors'])


def test_csv_rejects_duplicate_codes_already_in_db(app):
    """CSV rejects codes that already exist in the database."""
    from app.models.user import User
    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        # PRD-001 already exists in seed data
        csv_content = """product_code,product_name,category,price,stock_quantity,status
PRD-001,Colliding Item,Accessories,999,5,Active
"""
        result = CsvService.parse_and_validate_csv(csv_content, admin)
        assert result['success'] is False
        assert any("already exists in the database" in err['reason'] for err in result['errors'])


def test_csv_rejects_invalid_numeric_and_status(app):
    """CSV rejects invalid price, negative stock, and invalid status."""
    from app.models.user import User
    uid = uuid.uuid4().hex[:4].upper()
    csv_content = f"""product_code,product_name,category,price,stock_quantity,status
INV1-{uid},Bad Price,Cat,NOT_A_NUMBER,5,Active
INV2-{uid},Negative Stock,Cat,100,-10,Active
INV3-{uid},Bad Status,Cat,100,5,Draft
"""
    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        result = CsvService.parse_and_validate_csv(csv_content, admin)

        assert result['success'] is False
        assert len(result['errors']) == 3
        assert any("Price must be a valid numeric" in e['reason'] for e in result['errors'])
        assert any("Stock quantity cannot be negative" in e['reason'] for e in result['errors'])
        assert any("Invalid status" in e['reason'] for e in result['errors'])


def test_sales_user_cannot_access_csv_import(client):
    """Only Admin users can access and run CSV import."""
    login(client, 'sales@savyant.com', 'Sales@123')

    # GET
    r1 = client.get('/products/import-csv', follow_redirects=True)
    assert r1.status_code == 200
    assert b"Administrator privileges required" in r1.data

    # POST
    r2 = client.post('/products/import-csv', data={}, follow_redirects=True)
    assert r2.status_code == 200
    assert b"Administrator privileges required" in r2.data
