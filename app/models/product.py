from datetime import datetime
from decimal import Decimal
from app.extensions import db

class Product(db.Model):
    __tablename__ = 'products'

    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_code = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    category = db.Column(db.String(100), nullable=True, index=True)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.Enum('active', 'inactive', name='product_status_enum'), default='active', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order_items = db.relationship('SalesOrderItem', backref='product', lazy=True)
    stock_movements = db.relationship('StockMovement', backref='product', lazy=True)

    @property
    def has_references(self):
        return len(self.order_items) > 0 or len(self.stock_movements) > 0

    def to_dict(self):
        return {
            'id': self.id,
            'product_code': self.product_code,
            'name': self.name,
            'category': self.category or '',
            'price': float(self.price) if self.price is not None else 0.0,
            'stock_quantity': self.stock_quantity,
            'status': self.status,
            'has_references': self.has_references,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

    def __repr__(self):
        return f"<Product {self.product_code} - {self.name} (Stock: {self.stock_quantity})>"
