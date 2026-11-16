import os
import sys
from app import create_app
from app.extensions import db
from app.models import User, Customer, Product, SalesOrder, SalesOrderItem, StockMovement

app = create_app()

@app.cli.command('init-db')
def init_db():
    """Create database tables if they do not exist."""
    with app.app_context():
        db.create_all()
        print("Database tables verified/created successfully.")

@app.cli.command('seed')
def seed():
    """Seed initial sample users, customers, and products."""
    from werkzeug.security import generate_password_hash
    with app.app_context():
        # Users
        admin = User.query.filter_by(email='admin@savyant.com').first()
        if not admin:
            admin = User(
                name='System Administrator',
                email='admin@savyant.com',
                password_hash=generate_password_hash('Admin@123'),
                role='admin'
            )
            db.session.add(admin)

        sales = User.query.filter_by(email='sales@savyant.com').first()
        if not sales:
            sales = User(
                name='Sarah Sales',
                email='sales@savyant.com',
                password_hash=generate_password_hash('Sales@123'),
                role='sales_user'
            )
            db.session.add(sales)

        db.session.commit()
        print("Sample users seeded successfully.")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=True)
