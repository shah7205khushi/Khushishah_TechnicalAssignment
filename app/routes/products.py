from flask import Blueprint
from app.routes.auth import login_required, admin_required

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@login_required
def list_products():
    return "Products List Stub (To be implemented in Step 2)"

@products_bp.route('/import-csv')
@admin_required
def import_csv():
    return "CSV Import Stub (To be implemented in Step 7)"
