from datetime import datetime, date, time
from decimal import Decimal
from sqlalchemy import func, case
from app.extensions import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import SalesOrder, SalesOrderItem
from app.models.stock_movement import StockMovement

class ReportService:
    @staticmethod
    def get_customer_sales_summary(start_date_str=None, end_date_str=None):
        """
        Customer Sales Summary Report (PDF Part 9):
          - Customer, confirmed order count, total sales after discount.
          - Supports an order-date range.
          - Includes customers with no Confirmed orders in that range, showing zero totals.
          - Avoids counting one order multiple times because it has multiple item rows.
        """
        # Parse date range if provided
        start_dt = None
        end_dt = None
        if start_date_str:
            try:
                d = datetime.strptime(start_date_str.strip(), '%Y-%m-%d').date()
                start_dt = datetime.combine(d, time.min)
            except ValueError:
                pass

        if end_date_str:
            try:
                d = datetime.strptime(end_date_str.strip(), '%Y-%m-%d').date()
                end_dt = datetime.combine(d, time.max)
            except ValueError:
                pass

        # Build join condition on SalesOrder directly (not items, to prevent multiplication)
        join_conditions = [
            SalesOrder.customer_id == Customer.id,
            SalesOrder.status == SalesOrder.STATUS_CONFIRMED
        ]
        if start_dt:
            join_conditions.append(SalesOrder.order_date >= start_dt)
        if end_dt:
            join_conditions.append(SalesOrder.order_date <= end_dt)

        query = (
            db.session.query(
                Customer.id.label('customer_id'),
                Customer.name.label('customer_name'),
                Customer.email.label('customer_email'),
                Customer.city.label('customer_city'),
                func.count(SalesOrder.id).label('confirmed_order_count'),
                func.coalesce(func.sum(SalesOrder.grand_total), Decimal('0.00')).label('total_sales_after_discount')
            )
            .outerjoin(SalesOrder, db.and_(*join_conditions))
            .group_by(Customer.id, Customer.name, Customer.email, Customer.city)
            .order_by(func.coalesce(func.sum(SalesOrder.grand_total), Decimal('0.00')).desc(), Customer.name.asc())
        )

        results = query.all()

        total_orders_sum = sum(r.confirmed_order_count for r in results)
        total_revenue_sum = sum(r.total_sales_after_discount for r in results)

        return {
            'data': results,
            'total_orders': total_orders_sum,
            'total_revenue': total_revenue_sum,
            'start_date': start_date_str or '',
            'end_date': end_date_str or ''
        }

    @staticmethod
    def get_product_sales_summary():
        """
        Product Sales Summary Report (PDF Part 9):
          - Product, quantity sold, gross item value before order discount.
          - Includes Confirmed orders only.
        """
        query = (
            db.session.query(
                Product.id.label('product_id'),
                Product.product_code.label('product_code'),
                Product.name.label('product_name'),
                Product.category.label('category'),
                func.coalesce(
                    func.sum(
                        case(
                            (SalesOrder.status == SalesOrder.STATUS_CONFIRMED, SalesOrderItem.quantity),
                            else_=0
                        )
                    ), 0
                ).label('total_quantity_sold'),
                func.coalesce(
                    func.sum(
                        case(
                            (SalesOrder.status == SalesOrder.STATUS_CONFIRMED, SalesOrderItem.amount),
                            else_=Decimal('0.00')
                        )
                    ), Decimal('0.00')
                ).label('gross_sales_value')
            )
            .outerjoin(
                SalesOrderItem,
                Product.id == SalesOrderItem.product_id
            )
            .outerjoin(
                SalesOrder,
                db.and_(
                    SalesOrderItem.sales_order_id == SalesOrder.id,
                    SalesOrder.status == SalesOrder.STATUS_CONFIRMED
                )
            )
            .group_by(Product.id, Product.product_code, Product.name, Product.category)
            .order_by(func.coalesce(func.sum(SalesOrderItem.quantity), 0).desc(), func.coalesce(func.sum(SalesOrderItem.amount), Decimal('0.00')).desc())
        )

        results = query.all()
        total_units_sold = sum(r.total_quantity_sold for r in results)
        total_gross_value = sum(r.gross_sales_value for r in results)

        return {
            'data': results,
            'total_units_sold': total_units_sold,
            'total_gross_value': total_gross_value
        }

    @staticmethod
    def get_low_stock_report(threshold=10):
        """
        Low Stock Report (PDF Part 9):
          - Products with stock below a user-entered threshold.
        """
        try:
            threshold_int = max(0, int(threshold))
        except (ValueError, TypeError):
            threshold_int = 10

        products = (
            Product.query
            .filter(Product.stock_quantity <= threshold_int)
            .order_by(Product.stock_quantity.asc(), Product.name.asc())
            .all()
        )

        return {
            'products': products,
            'threshold': threshold_int,
            'count': len(products)
        }
