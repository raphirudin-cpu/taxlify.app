import os
from flask import Flask, redirect, url_for
from flask_login import current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
from app.celery import make_celery, celery
from config import get_config

# Load environment variables from .env (development convenience).
load_dotenv()

# Extensions
db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def _configure_observability(app):
    """Sentry (gated on SENTRY_DSN) + rotating file logging for tracebacks."""
    dsn = app.config.get("SENTRY_DSN")
    if dsn:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=app.config.get("SENTRY_TRACES_SAMPLE_RATE", 0.0),
            environment=app.config.get("SENTRY_ENVIRONMENT", "production"),
            send_default_pii=False,  # never ship client PII to Sentry
        )

    if not app.testing:
        import logging
        from logging.handlers import RotatingFileHandler
        log_dir = app.config.get("LOG_DIR", "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            handler = RotatingFileHandler(
                os.path.join(log_dir, "taxlify.log"), maxBytes=2_000_000, backupCount=5
            )
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            ))
            level = app.config.get("LOG_LEVEL", "INFO")
            handler.setLevel(level)
            app.logger.addHandler(handler)
            app.logger.setLevel(level)
        except OSError:
            app.logger.warning("Could not set up file logging in %s", log_dir)


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object(config_class or get_config())

    _configure_observability(app)

    # === Init Extensions ===
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    make_celery(app)

    # Ensure models are imported so Flask-Migrate can see them.
    from app import models  # noqa: F401

    # German (Swiss) render-time filters: status_de, date_ch, chf, ...
    from app.i18n import register_filters
    register_filters(app)

    @app.context_processor
    def inject_nav():
        """Latest tax year for a client, for the sidebar's year-scoped links."""
        year = None
        try:
            if current_user.is_authenticated and current_user.role == 'user':
                ty = (models.TaxYear.query
                      .filter_by(user_id=current_user.id)
                      .order_by(models.TaxYear.year.desc()).first())
                if ty:
                    year = ty.year
        except Exception:
            year = None
        return {'nav_year': year}

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.dashboard'))
        return redirect(url_for('auth.login'))

    # === Register Blueprints ===
    from app.routes.auth_routes import auth_bp
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.settings_routes import settings_bp
    from app.routes.advisor_routes import advisor_bp
    from app.routes.statistic_routes import statistics_bp
    from app.routes.tips_news_routes import tips_news_bp
    from app.routes.checklist_routes import checklist_bp
    from app.routes.upload_documents_routes import upload_bp
    from app.routes.view_checklist_routes import view_checklist_bp
    from app.routes.generate_pdf_routes import generate_pdf_bp
    from app.routes.view_documents_routes import view_documents_bp
    from app.routes.request_quote_routes import quote_bp
    from app.routes.advisor_details_routes import advisor_details_bp
    from app.routes.advisor_dashboard_routes import advisor_dashboard_bp
    from app.routes.advisor_settings import advisor_settings_bp
    from app.routes.submit_quote_routes import submit_quote_bp
    from app.routes.advisor_tips_news_routes import advisor_tips_news_bp
    from app.routes.advisor_advisors_routes import advisor_advisors_bp
    from app.routes.admin_settings_routes import admin_settings_bp
    from app.routes.reject_quote_routes import reject_quote_bp
    from app.routes.accept_reject_quote_routes import quote_action_bp
    from app.routes.submit_tax_return_routes import submit_tax_return_bp
    from app.routes.accept_reject_draft_tax_return_routes import draft_tax_return_action_bp
    from app.routes.submit_final_tax_return import submit_final_tax_return_bp
    from app.routes.submit_feedback_routes import feedback_bp
    from app.routes.request_more_documents_routes import request_more_documents_bp
    from app.routes.upload_additional_documents_routes import upload_additional_bp
    from app.routes.view_additional_documents_routes import view_additional_bp
    from app.routes.accept_documents_routes import documents_action_bp
    from app.routes.advisor_quotes_routes import advisor_quotes_bp
    from app.routes.advisor_billing_routes import billing_bp
    from app.routes.admin_dashboard_routes import admin_dashboard_bp
    from app.routes.admin_clients_routes import admin_clients_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(advisor_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(tips_news_bp)
    app.register_blueprint(checklist_bp)
    app.register_blueprint(upload_bp, url_prefix='/upload_documents')
    app.register_blueprint(view_checklist_bp)
    app.register_blueprint(generate_pdf_bp)
    app.register_blueprint(view_documents_bp)
    app.register_blueprint(quote_bp)
    app.register_blueprint(advisor_details_bp)
    app.register_blueprint(advisor_dashboard_bp)
    app.register_blueprint(advisor_settings_bp)
    app.register_blueprint(submit_quote_bp)
    app.register_blueprint(advisor_tips_news_bp)
    app.register_blueprint(advisor_advisors_bp)
    app.register_blueprint(admin_settings_bp)
    app.register_blueprint(reject_quote_bp)
    app.register_blueprint(quote_action_bp)
    app.register_blueprint(submit_tax_return_bp)
    app.register_blueprint(draft_tax_return_action_bp)
    app.register_blueprint(submit_final_tax_return_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(request_more_documents_bp)
    app.register_blueprint(upload_additional_bp)
    app.register_blueprint(view_additional_bp)
    app.register_blueprint(documents_action_bp)
    app.register_blueprint(advisor_quotes_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(admin_dashboard_bp)
    app.register_blueprint(admin_clients_bp)

    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.warning("CSRF validation failed: %s", e.description)
        return (
            "Your session or form token expired. Please reload the page and try again.",
            400,
        )

    app.logger.info("App started successfully.")
    return app


# === Register Celery Tasks for Worker Discovery ===
try:
    from app.utils import email_tasks  # Ensures @celery.task decorated functions are registered
except Exception as e:
    print(f"[INIT] Warning: Celery task discovery failed: {e}")
