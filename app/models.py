from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db  # Import db from app/__init__.py

class User(db.Model, UserMixin):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    email_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    password = db.Column(db.String(255), nullable=False)
    firstname = db.Column(db.String(100))
    lastname = db.Column(db.String(100))
    role = db.Column(db.Enum('user', 'advisor', 'admin', name='user_roles'), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    street = db.Column(db.String(200))
    city = db.Column(db.String(100))
    zipcode = db.Column(db.String(20))
    country = db.Column(db.String(100))
    retail = db.Column(db.Boolean, nullable=False, default=False)
    institutional = db.Column(db.Boolean, nullable=False, default=False)
    birthday = db.Column(db.Date)
    phone = db.Column(db.String(20))
    contact_option = db.Column(db.String(50))
    notify_status_changes = db.Column(db.Boolean, default=False)
    notify_new_requests = db.Column(db.Boolean, default=False)
    notify_deadline = db.Column(db.Boolean, default=False)
    first_login = db.Column(db.Boolean, nullable=False, default=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class TaxYear(db.Model):
    __tablename__ = 'tax_years'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(255), nullable=False)
    deadline = db.Column(db.Date, nullable=False)
    checklist_completed = db.Column(db.Boolean, default=False)
    uploaded_documents = db.Column(db.Boolean, default=False)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # advisor User responsible for this engagement
    assigned_on = db.Column(db.DateTime, nullable=True)  # when the client accepted the advisor's quote
    draft_rejection_comment = db.Column(db.Text, nullable=True)  # client's reason for rejecting a draft
    last_reminded_at = db.Column(db.DateTime, nullable=True)  # advisor's last nudge to the client
    final_submitted = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    draft_tax_return_submitted = db.Column(db.Boolean, nullable=False, default=False)
    draft_tax_return_approved = db.Column(db.Boolean, nullable=False, default=False)
    # Boolean flag (0/1 assignments from routes are coerced by SQLAlchemy).
    final_tax_return_submitted = db.Column(db.Boolean, nullable=False, default=False)
    draft_file_path = db.Column(db.String(255))
    final_file_path = db.Column(db.String(255))
    additional_documents_request = db.Column(db.Boolean, default=False)
    additional_documents_uploaded = db.Column(db.Boolean, default=False)
    documents_approved = db.Column(db.Boolean, default=False)

class Quote(db.Model):
    __tablename__ = 'quotes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tax_year = db.Column(db.Integer, nullable=False)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=False)
    quote_status = db.Column(
        db.Enum('Pending', 'In Review', 'Accepted', 'Rejected', 'Draft Tax Return in Review', 'Tax Return Approved', name='quote_status'),
        default='Pending'
    )
    quote_amount = db.Column(db.Numeric(10, 2), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)  # client's reason for declining the offer
    file_path = db.Column(db.String(255), nullable=True)
    final_submitted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_on = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.Date)
    accepted_on = db.Column(db.DateTime, default=datetime.utcnow)

class Feedback(db.Model):
    __tablename__ = 'feedback'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tax_year = db.Column(db.Integer, nullable=False)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # Between 1 and 5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Removed relationship logic

class TaxReturn(db.Model):
    __tablename__ = 'tax_returns'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tax_year = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default="Pending")
    file_path = db.Column(db.String(255), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Removed relationship logic

class Advisor(db.Model):
    __tablename__ = 'advisor'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    logo = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    website = db.Column(db.String(255), nullable=True)
    rating = db.Column(db.Numeric(3,2), default=0.0)
    default_hourly_rate = db.Column(db.Numeric(10,2), nullable=True)  # CHF/h prefilled on new time entries
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Removed relationship logic

class UserStatistics(db.Model):
    __tablename__ = 'user_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    taxable_income = db.Column(db.Numeric(15,2), nullable=False)
    taxable_assets = db.Column(db.Numeric(15,2), nullable=False)
    paid_taxes = db.Column(db.Numeric(15,2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Removed relationship logic

class ChecklistAnswer(db.Model):
    __tablename__ = 'checklist_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey('tax_years.id'), nullable=False)
    step = db.Column(db.Integer, nullable=False)
    answers = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    document_required = db.Column(db.Boolean, default=False)
    # Removed relationship logic

class RequiredDocument(db.Model):
    __tablename__ = 'required_document'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tax_year_id = db.Column(db.Integer, db.ForeignKey('tax_years.id'), nullable=False)
    document_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(255))
    uploaded_on = db.Column(db.DateTime, default=datetime.utcnow)
    downloaded_on = db.Column(db.DateTime, nullable=True)
    # Removed relationship logic

class TeamMember(db.Model):
    __tablename__ = 'team_members'
    
    id = db.Column(db.Integer, primary_key=True)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='staff')  # 'manager' | 'staff'

    def __repr__(self):
        return f'<TeamMember {self.email}>'

class DocumentRequest(db.Model):
    __tablename__ = 'additional_document_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tax_year_id = db.Column(db.Integer, db.ForeignKey('tax_years.id'), nullable=False)
    request_text = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255))
    uploaded_on = db.Column(db.DateTime)
    downloaded_on = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TaxYearExtension(db.Model):
    """A recorded deadline extension (Fristverlängerung) for a tax year."""
    __tablename__ = 'tax_year_extensions'

    id = db.Column(db.Integer, primary_key=True)
    tax_year_id = db.Column(db.Integer, db.ForeignKey('tax_years.id'), nullable=False)
    previous_deadline = db.Column(db.Date, nullable=True)
    new_deadline = db.Column(db.Date, nullable=False)
    note = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ClientInvoice(db.Model):
    """An invoice a firm issues to one of its clients for a tax year, generated
    from the billable time logged against that engagement."""
    __tablename__ = 'client_invoices'

    id = db.Column(db.Integer, primary_key=True)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # client billed
    tax_year = db.Column(db.Integer, nullable=False)
    minutes_total = db.Column(db.Integer, nullable=False, default=0)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default='offen')  # offen | bezahlt | storniert
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class TimeEntry(db.Model):
    """A unit of billable work logged against a client's tax year."""
    __tablename__ = 'time_entries'

    id = db.Column(db.Integer, primary_key=True)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=False)  # the firm
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)         # the client
    tax_year = db.Column(db.Integer, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)        # who logged it
    spent_on = db.Column(db.Date, nullable=False)
    minutes = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    rate_chf = db.Column(db.Numeric(10, 2), nullable=False)                           # snapshot hourly rate
    billed = db.Column(db.Boolean, nullable=False, default=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('client_invoices.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def amount(self):
        """Billable amount in CHF for this entry (minutes / 60 * rate)."""
        from decimal import Decimal, ROUND_HALF_UP
        return (Decimal(self.minutes) / Decimal(60) * Decimal(self.rate_chf)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)


class DocumentAnalysis(db.Model):
    """AI classification + field extraction for one uploaded document.
    One row per RequiredDocument (re-analysis replaces the previous row)."""
    __tablename__ = 'document_analyses'

    id = db.Column(db.Integer, primary_key=True)
    required_document_id = db.Column(db.Integer, db.ForeignKey('required_document.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tax_year = db.Column(db.Integer, nullable=False)
    doc_type = db.Column(db.String(100), nullable=True)      # e.g. 'Lohnausweis'
    summary = db.Column(db.Text, nullable=True)              # one-line German summary
    fields_json = db.Column(db.Text, nullable=True)          # JSON: [{label, value}, ...]
    confidence = db.Column(db.String(20), nullable=True)     # 'hoch' | 'mittel' | 'niedrig'
    model = db.Column(db.String(60), nullable=True)          # model id used
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def fields(self):
        import json
        try:
            return json.loads(self.fields_json) if self.fields_json else []
        except (ValueError, TypeError):
            return []


class AuditLog(db.Model):
    """Activity trail of user actions (who did what, when). Best-effort — writing
    an entry never blocks the underlying request (see app.audit.log_action)."""
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(80), nullable=False)          # e.g. 'quote.accept'
    target_type = db.Column(db.String(40), nullable=True)       # e.g. 'tax_year'
    target_id = db.Column(db.Integer, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    detail = db.Column(db.Text, nullable=True)                  # short human/JSON note
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    tier_level = db.Column(db.Integer, nullable=False)
    monthly_price = db.Column(db.Numeric(10,2), nullable=False)
    base_slots = db.Column(db.Integer, nullable=False)
    slot_price = db.Column(db.Numeric(10,2), nullable=False)

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    slots = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    tax_year = db.Column(db.Integer, nullable=False)

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Numeric(10,2), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.Date, nullable=False, server_default=db.func.current_date())
    status = db.Column(db.String(20), nullable=False, default='pending')
    invoice_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
