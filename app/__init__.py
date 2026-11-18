"""
Application Factory for Urban Microclimate & Heat-Risk Intelligence System.
"""
import logging
from flask import Flask
from config import settings
from app.utils.response import api_error


def create_app(test_config=None) -> Flask:
    """Creates and configures an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s"
    )

    if test_config:
        app.config.update(test_config)

    # Register blueprints
    from app.routes.api import api_bp
    app.register_blueprint(api_bp)

    # Global HTTP error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return api_error(str(e.description if hasattr(e, "description") else e), error_code="BAD_REQUEST", status_code=400)

    @app.errorhandler(404)
    def not_found(e):
        return api_error("The requested URL or resource was not found on this server.", error_code="NOT_FOUND", status_code=404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return api_error("The HTTP method is not allowed for the requested URL.", error_code="METHOD_NOT_ALLOWED", status_code=405)

    @app.errorhandler(500)
    def internal_server_error(e):
        return api_error("An unexpected internal server error occurred.", error_code="INTERNAL_SERVER_ERROR", status_code=500)

    # Root informational route with content negotiation
    @app.route("/", methods=["GET"])
    def index():
        from flask import request, render_template, jsonify
        accept_header = request.headers.get("Accept", "")
        # If accessed by a web browser expecting HTML, render the dashboard
        if "text/html" in accept_header and accept_header.strip() != "*/*":
            return render_template("index.html")

        # In programmatic test client or API consumers, return service metadata JSON
        return jsonify({
            "service": "Urban Microclimate & Heat-Risk Intelligence System API",
            "version": "1.0.0",
            "documentation": "/api/v1/health",
            "database": "Apache HBase 2.6.7 (REST)",
            "dashboard": "/dashboard"
        })

    # Dedicated frontend dashboard route
    @app.route("/dashboard", methods=["GET"])
    def dashboard():
        from flask import render_template
        return render_template("index.html")

    return app
