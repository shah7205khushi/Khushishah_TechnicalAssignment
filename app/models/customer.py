from datetime import datetime
from app.extensions import db

class Customer(db.Model):
    __tablename__ = 'customers'

    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(150), nullable=True, index=True)
    mobile = db.Column(db.String(20), nullable=True, index=True)
    city = db.Column(db.String(100), nullable=True)
    status = db.Column(db.Enum('active', 'inactive', name='customer_status_enum'), default='active', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = db.relationship('SalesOrder', backref='customer', lazy=True)

    @property
    def has_orders(self):
        return len(self.orders) > 0

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email or '',
            'mobile': self.mobile or '',
            'city': self.city or '',
            'status': self.status,
            'order_count': len(self.orders),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

    def __repr__(self):
        return f"<Customer {self.name} ({self.status})>"
