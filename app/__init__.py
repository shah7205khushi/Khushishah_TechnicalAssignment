from datetime import datetime
from flask import Flask
from app.config import Config
from app.extensions import db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    # Context processors
    from app.routes.auth import get_current_user
    @app.context_processor
    def inject_context():
        return {
            'current_user': get_current_user(),
            'current_year': datetime.now().year
        }

    # Register Blueprints
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.customers import customers_bp
    app.register_blueprint(customers_bp)

    from app.routes.products import products_bp
    app.register_blueprint(products_bp)

    from app.routes.orders import orders_bp
    app.register_blueprint(orders_bp)

    from app.routes.reports import reports_bp
    app.register_blueprint(reports_bp)

    from app.routes.api import api_bp
    app.register_blueprint(api_bp)

    # Error handlers
    from flask import render_template, jsonify, request
    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden: You do not have permission to access this resource.'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Resource not found.'}), 404
        return render_template('base.html'), 404

    return app
