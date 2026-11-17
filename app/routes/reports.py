from flask import Blueprint, render_template, request
from app.routes.auth import login_required, admin_required
from app.services.report_service import ReportService
from app.models.stock_movement import StockMovement

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/customer-sales')
@admin_required
def customer_sales():
    """
    Customer Sales Summary Report (PDF Part 9):
    Customer, confirmed order count, total sales after discount.
    Supports date range filtering and includes customers with 0 orders.
    """
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    report = ReportService.get_customer_sales_summary(start_date, end_date)
    return render_template('reports/customer_sales.html', report=report)

@reports_bp.route('/product-sales')
@admin_required
def product_sales():
    """
    Product Sales Summary Report (PDF Part 9):
    Product, quantity sold, gross item value before order discount.
    """
    report = ReportService.get_product_sales_summary()
    return render_template('reports/product_sales.html', report=report)

@reports_bp.route('/low-stock')
@admin_required
def low_stock():
    """
    Low Stock Report (PDF Part 9):
    Products with stock below a user-entered threshold.
    """
    threshold = request.args.get('threshold', 10)
    report = ReportService.get_low_stock_report(threshold)
    return render_template('reports/low_stock.html', report=report)

@reports_bp.route('/stock-movements')
@admin_required
def stock_movements():
    """
    Stock Movement History Report (PDF Part 9):
    Product, movement type, quantity change, order, reason and timestamp.
    """
    movements = (
        StockMovement.query
        .order_by(StockMovement.id.desc())
        .limit(200)
        .all()
    )
    return render_template('reports/stock_movements.html', movements=movements)
