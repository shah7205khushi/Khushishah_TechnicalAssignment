from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from app.extensions import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import SalesOrder, SalesOrderItem
from app.models.stock_movement import StockMovement

def quantize_money(amount):
    """Round monetary values to two decimal places using standard ROUND_HALF_UP."""
    if amount is None:
        return Decimal('0.00')
    return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def generate_order_number():
    """Generate a unique order number formatted as SO-YYYYMMDD-XXXX."""
    today_str = datetime.now().strftime('%Y%m%d')
    prefix = f"SO-{today_str}-"
    # Find the latest order with today's prefix
    last_order = (
        SalesOrder.query
        .filter(SalesOrder.order_number.like(f"{prefix}%"))
        .order_by(SalesOrder.id.desc())
        .first()
    )
    if last_order:
        try:
            last_seq = int(last_order.order_number.split('-')[-1])
            new_seq = last_seq + 1
        except ValueError:
            new_seq = 1
    else:
        new_seq = 1
    return f"{prefix}{new_seq:04d}"

class OrderService:
    @staticmethod
    def calculate_order_values(items_data, discount_percentage):
        """
        Calculates and validates financial values strictly on the backend.
        Calculation Rules (PDF Part 5):
          - Item Amount = Quantity * Rate
          - Subtotal = Sum of Item Amounts
          - Discount Amount = Subtotal * Discount Percentage / 100
          - Grand Total = Subtotal - Discount Amount
          - Round monetary amounts to two decimal places consistently.
        """
        # Validate discount percentage between 0 and 20
        try:
            discount_pct = Decimal(str(discount_percentage or '0.00'))
            if discount_pct < Decimal('0.00') or discount_pct > Decimal('20.00'):
                raise ValueError("Discount percentage must be between 0% and 20%.")
            discount_pct = quantize_money(discount_pct)
        except Exception as e:
            raise ValueError(f"Invalid discount percentage: {e}")

        if not items_data or len(items_data) == 0:
            raise ValueError("Sales order requires at least one item.")

        processed_items = []
        seen_products = set()
        subtotal = Decimal('0.00')

        for item in items_data:
            product_id = item.get('product_id')
            if not product_id:
                raise ValueError("Product selection is required for every row.")

            # Validate duplicate products
            if product_id in seen_products:
                raise ValueError("Duplicate products are not allowed within the same order.")
            seen_products.add(product_id)

            # Validate quantity
            try:
                qty = int(item.get('quantity', 0))
            except (ValueError, TypeError):
                raise ValueError("Item quantity must be a valid integer.")
            if qty <= 0:
                raise ValueError("Quantity must be a positive whole number greater than 0.")

            # Fetch product from database to get official rate (never trust client rate!)
            product = db.session.get(Product, product_id)
            if not product:
                raise ValueError(f"Product with ID {product_id} not found.")
            if product.status != 'active':
                raise ValueError(f"Product '{product.name}' is inactive and cannot be ordered.")

            rate = quantize_money(product.price)
            item_amount = quantize_money(Decimal(qty) * rate)
            subtotal += item_amount

            processed_items.append({
                'product': product,
                'product_id': product.id,
                'quantity': qty,
                'rate': rate,
                'amount': item_amount
            })

        subtotal = quantize_money(subtotal)
        discount_amount = quantize_money(subtotal * (discount_pct / Decimal('100')))
        grand_total = quantize_money(subtotal - discount_amount)

        return {
            'items': processed_items,
            'subtotal': subtotal,
            'discount_percentage': discount_pct,
            'discount_amount': discount_amount,
            'grand_total': grand_total
        }

    @staticmethod
    def create_draft_order(customer_id, items_data, discount_percentage, user_id):
        """Create a new sales order in Draft status."""
        customer = db.session.get(Customer, customer_id)
        if not customer:
            raise ValueError("Customer not found.")
        if customer.status != 'active':
            raise ValueError("Cannot create orders for inactive customers.")

        # Calculate values
        calc = OrderService.calculate_order_values(items_data, discount_percentage)

        order_number = generate_order_number()

        # Create Order
        order = SalesOrder(
            order_number=order_number,
            customer_id=customer.id,
            status=SalesOrder.STATUS_DRAFT,
            discount_percentage=calc['discount_percentage'],
            subtotal=calc['subtotal'],
            discount_amount=calc['discount_amount'],
            grand_total=calc['grand_total'],
            created_by=user_id,
            order_date=datetime.now()
        )
        db.session.add(order)
        db.session.flush()

        # Create Order Items (snapshotting current rate)
        for item in calc['items']:
            order_item = SalesOrderItem(
                sales_order_id=order.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                rate=item['rate'],
                amount=item['amount']
            )
            db.session.add(order_item)

        db.session.commit()
        return order

    @staticmethod
    def update_draft_order(order_id, customer_id, items_data, discount_percentage, user):
        """Update an existing order while it is in Draft status."""
        order = db.session.get(SalesOrder, order_id)
        if not order:
            raise ValueError("Order not found.")

        # Check permissions
        if user.is_sales_user and order.created_by != user.id:
            raise PermissionError("Access denied: You cannot edit another user's order.")

        # Draft check
        if not order.is_draft:
            raise ValueError("Only orders in 'Draft' status can be modified.")

        customer = db.session.get(Customer, customer_id)
        if not customer or customer.status != 'active':
            raise ValueError("Selected customer is not active.")

        calc = OrderService.calculate_order_values(items_data, discount_percentage)

        order.customer_id = customer.id
        order.discount_percentage = calc['discount_percentage']
        order.subtotal = calc['subtotal']
        order.discount_amount = calc['discount_amount']
        order.grand_total = calc['grand_total']

        # Replace items
        SalesOrderItem.query.filter_by(sales_order_id=order.id).delete()

        for item in calc['items']:
            order_item = SalesOrderItem(
                sales_order_id=order.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                rate=item['rate'],
                amount=item['amount']
            )
            db.session.add(order_item)

        db.session.commit()
        return order

    @staticmethod
    def confirm_order(order_id, user):
        """
        Confirms a Draft sales order and deducts inventory atomically.
        Requirements (PDF Part 6):
          - Check stock availability when confirming an order.
          - If ANY product has insufficient stock, reject the ENTIRE confirmation (all-or-nothing).
          - Concurrency Safety: Lock product rows with SELECT ... FOR UPDATE in sorted order.
          - Save order status, stock changes, and stock movement records in one atomic transaction.
          - Repeated confirmation requests must not deduct stock again.
          - Confirmed orders become read-only.
        """
        order = db.session.get(SalesOrder, order_id)
        if not order:
            raise ValueError("Order not found.")

        # Permission check: Sales User can only confirm their own orders
        if user.is_sales_user and order.created_by != user.id:
            raise PermissionError("Access denied: You cannot confirm another user's order.")

        # Status checks & Repeated confirmation prevention
        if order.status == SalesOrder.STATUS_CONFIRMED:
            raise ValueError("Order is already confirmed. Repeated confirmation is not permitted.")
        if order.status != SalesOrder.STATUS_DRAFT:
            raise ValueError(f"Cannot confirm order with status '{order.status}'. Only Draft orders can be confirmed.")

        if not order.items or len(order.items) == 0:
            raise ValueError("Cannot confirm an order with no items.")

        try:
            # 1. Collect and sort product IDs to prevent database deadlocks under concurrency
            product_ids = sorted(list(set(item.product_id for item in order.items)))

            # 2. Acquire exclusive row-level locks on products using SELECT ... FOR UPDATE
            locked_products = {
                p.id: p
                for p in (
                    db.session.query(Product)
                    .filter(Product.id.in_(product_ids))
                    .order_by(Product.id.asc())
                    .with_for_update()
                    .all()
                )
            }

            # 3. Check stock availability for EVERY item (all-or-nothing check)
            for item in order.items:
                product = locked_products.get(item.product_id)
                if not product:
                    raise ValueError(f"Product (ID: {item.product_id}) not found.")

                if product.stock_quantity < item.quantity:
                    raise ValueError(
                        f"Insufficient stock for product '{product.name}' ({product.product_code}). "
                        f"Requested: {item.quantity}, Available in stock: {product.stock_quantity}."
                    )

            # 4. If all products have sufficient stock, deduct quantities and create movements
            for item in order.items:
                product = locked_products[item.product_id]
                product.stock_quantity -= item.quantity

                movement = StockMovement(
                    product_id=product.id,
                    movement_type=StockMovement.TYPE_CONFIRM,
                    quantity_change=-item.quantity,
                    related_order_id=order.id,
                    reason=f"Order {order.order_number} confirmed",
                    created_by=user.id
                )
                db.session.add(movement)

            # 5. Transition order status to Confirmed
            order.status = SalesOrder.STATUS_CONFIRMED
            order.updated_at = datetime.now()

            # 6. Commit atomic transaction
            db.session.commit()
            return order

        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def cancel_order(order_id, user):
        """
        Cancels a Draft or Confirmed sales order.
        Requirements (PDF Part 6):
          - Draft -> Cancel: No stock change.
          - Confirmed -> Cancel: Restore deducted stock and log ORDER_CANCEL movements.
          - Repeated cancellation requests must not restore stock again.
          - Cancelled orders are terminal and read-only.
        """
        order = db.session.get(SalesOrder, order_id)
        if not order:
            raise ValueError("Order not found.")

        # Permission check
        if user.is_sales_user and order.created_by != user.id:
            raise PermissionError("Access denied: You cannot cancel another user's order.")

        # Status check
        if order.status == SalesOrder.STATUS_CANCELLED:
            raise ValueError("Order is already cancelled. Repeated cancellation is not permitted.")
        if order.status not in [SalesOrder.STATUS_DRAFT, SalesOrder.STATUS_CONFIRMED]:
            raise ValueError(f"Cannot cancel order with status '{order.status}'.")

        previous_status = order.status

        try:
            # Case 1: Cancelling a Confirmed order -> Restore stock
            if previous_status == SalesOrder.STATUS_CONFIRMED:
                product_ids = sorted(list(set(item.product_id for item in order.items)))

                # Lock product rows for update
                locked_products = {
                    p.id: p
                    for p in (
                        db.session.query(Product)
                        .filter(Product.id.in_(product_ids))
                        .order_by(Product.id.asc())
                        .with_for_update()
                        .all()
                    )
                }

                for item in order.items:
                    product = locked_products.get(item.product_id)
                    if product:
                        product.stock_quantity += item.quantity

                        movement = StockMovement(
                            product_id=product.id,
                            movement_type=StockMovement.TYPE_CANCEL,
                            quantity_change=item.quantity,
                            related_order_id=order.id,
                            reason=f"Order {order.order_number} cancelled - stock restored",
                            created_by=user.id
                        )
                        db.session.add(movement)

            # Transition status
            order.status = SalesOrder.STATUS_CANCELLED
            order.updated_at = datetime.now()

            db.session.commit()
            return order

        except Exception:
            db.session.rollback()
            raise
