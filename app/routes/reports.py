from flask import Blueprint
from app.routes.auth import login_required, admin_required

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/customer-sales')
@admin_required
def customer_sales():
    return "Customer Sales Report Stub (To be implemented in Step 6)"
