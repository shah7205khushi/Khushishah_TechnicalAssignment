from flask import Blueprint, render_template
from app.routes.auth import login_required

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')

@customers_bp.route('/')
@login_required
def list_customers():
    return "Customers List Stub (To be implemented in Step 2)"
