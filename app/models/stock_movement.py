from datetime import datetime
from app.extensions import db

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'

    TYPE_OPENING = 'OPENING_STOCK'
    TYPE_CONFIRM = 'ORDER_CONFIRM'
    TYPE_CANCEL = 'ORDER_CANCEL'
    TYPE_ADJUSTMENT = 'MANUAL_ADJUSTMENT'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False, index=True)
    movement_type = db.Column(
        db.Enum('OPENING_STOCK', 'ORDER_CONFIRM', 'ORDER_CANCEL', 'MANUAL_ADJUSTMENT', name='stock_movement_type_enum'),
        nullable=False,
        index=True
    )
    quantity_change = db.Column(db.Integer, nullable=False)
    related_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=True, index=True)
    reason = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_code': self.product.product_code if self.product else None,
            'product_name': self.product.name if self.product else None,
            'movement_type': self.movement_type,
            'quantity_change': self.quantity_change,
            'related_order_id': self.related_order_id,
            'order_number': self.order.order_number if self.order else None,
            'reason': self.reason or '',
            'created_by': self.created_by,
            'creator_name': self.creator.name if self.creator else None,
            'timestamp': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f"<StockMovement Product:{self.product_id} Type:{self.movement_type} Change:{self.quantity_change}>"
