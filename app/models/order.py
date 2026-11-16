from datetime import datetime
from decimal import Decimal
from app.extensions import db

class SalesOrder(db.Model):
    __tablename__ = 'sales_orders'

    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_number = db.Column(db.String(50), nullable=False, unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False, index=True)
    order_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    status = db.Column(
        db.Enum('draft', 'confirmed', 'cancelled', name='order_status_enum'),
        default='draft',
        index=True
    )
    discount_percentage = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    subtotal = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal('0.00'))
    discount_amount = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal('0.00'))
    grand_total = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal('0.00'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items = db.relationship('SalesOrderItem', backref='order', cascade='all, delete-orphan', lazy=True)
    stock_movements = db.relationship('StockMovement', backref='order', lazy=True)

    @property
    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    @property
    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    @property
    def is_cancelled(self):
        return self.status == self.STATUS_CANCELLED

    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'customer_id': self.customer_id,
            'customer_name': self.customer.name if self.customer else None,
            'order_date': self.order_date.strftime('%Y-%m-%d %H:%M:%S') if self.order_date else None,
            'status': self.status,
            'discount_percentage': float(self.discount_percentage) if self.discount_percentage is not None else 0.0,
            'subtotal': float(self.subtotal) if self.subtotal is not None else 0.0,
            'discount_amount': float(self.discount_amount) if self.discount_amount is not None else 0.0,
            'grand_total': float(self.grand_total) if self.grand_total is not None else 0.0,
            'created_by': self.created_by,
            'creator_name': self.creator.name if self.creator else None,
            'items': [item.to_dict() for item in self.items],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

    def __repr__(self):
        return f"<SalesOrder {self.order_number} ({self.status})>"


class SalesOrderItem(db.Model):
    __tablename__ = 'sales_order_items'
    __table_args__ = (
        db.UniqueConstraint('sales_order_id', 'product_id', name='uq_order_product'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    rate = db.Column(db.Numeric(12, 2), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'sales_order_id': self.sales_order_id,
            'product_id': self.product_id,
            'product_code': self.product.product_code if self.product else None,
            'product_name': self.product.name if self.product else None,
            'quantity': self.quantity,
            'rate': float(self.rate) if self.rate is not None else 0.0,
            'amount': float(self.amount) if self.amount is not None else 0.0
        }

    def __repr__(self):
        return f"<SalesOrderItem Order:{self.sales_order_id} Product:{self.product_id} Qty:{self.quantity}>"
