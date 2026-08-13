"""Time-tracking and client billing for advisor firms.

Any firm member may log and view billable time against the firm's client
engagements; only owners/managers may generate and settle client invoices.
"""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.models import db, TaxYear, User, TimeEntry, ClientInvoice
from app.security import (
    require_role, parse_int, advisor_is_bound, can_manage_firm,
    current_advisor_ids, firm_advisor,
)
from app.helpers import commit_or_rollback
from app.audit import log_action

time_bp = Blueprint('time_tracking', __name__, url_prefix='/advisor/time')

DEFAULT_RATE = Decimal('150.00')


def _firm_ids_or_403():
    ids = current_advisor_ids()
    if not ids:
        abort(403)
    return ids


def _parse_rate(raw):
    try:
        r = Decimal(str(raw).replace(',', '.'))
    except (InvalidOperation, TypeError):
        return None
    return r if r >= 0 else None


@time_bp.route('/', methods=['GET'])
@login_required
@require_role('advisor', 'admin')
def index():
    ids = _firm_ids_or_403()
    is_manager = can_manage_firm()
    adv = firm_advisor()
    default_rate = (adv.default_hourly_rate if adv and adv.default_hourly_rate is not None
                    else DEFAULT_RATE)

    # Engagements (client-year) for the add-form dropdown.
    rows = (db.session.query(TaxYear, User)
            .join(User, TaxYear.user_id == User.id)
            .filter(TaxYear.advisor_id.in_(ids))
            .order_by(TaxYear.year.desc()).all())
    engagements = [{
        'user_id': ty.user_id, 'year': ty.year,
        'label': f"{user.firstname or ''} {user.lastname or ''}".strip() or user.email,
    } for ty, user in rows]

    # All time entries for the firm, newest first, with client + author labels.
    entries = (TimeEntry.query
               .filter(TimeEntry.advisor_id.in_(ids))
               .order_by(TimeEntry.spent_on.desc(), TimeEntry.id.desc()).all())
    user_ids = {e.user_id for e in entries} | {e.author_id for e in entries if e.author_id}
    names = {}
    if user_ids:
        for u in User.query.filter(User.id.in_(user_ids)).all():
            names[u.id] = f"{u.firstname or ''} {u.lastname or ''}".strip() or u.email

    entry_rows = []
    unbilled = {}  # (user_id, year) -> {'minutes':, 'amount':, 'label':}
    for e in entries:
        entry_rows.append({
            'id': e.id, 'client': names.get(e.user_id, '—'), 'year': e.tax_year,
            'author': names.get(e.author_id, '—'), 'spent_on': e.spent_on,
            'minutes': e.minutes, 'description': e.description,
            'rate': e.rate_chf, 'amount': e.amount, 'billed': e.billed,
        })
        if not e.billed:
            key = (e.user_id, e.tax_year)
            agg = unbilled.setdefault(key, {'minutes': 0, 'amount': Decimal('0.00'),
                                            'label': names.get(e.user_id, '—')})
            agg['minutes'] += e.minutes
            agg['amount'] += e.amount

    unbilled_groups = [{
        'user_id': k[0], 'year': k[1], 'label': v['label'],
        'minutes': v['minutes'], 'amount': v['amount'],
    } for k, v in sorted(unbilled.items(), key=lambda kv: (kv[1]['label'], kv[0][1]))]

    invoices = (ClientInvoice.query
                .filter(ClientInvoice.advisor_id.in_(ids))
                .order_by(ClientInvoice.created_at.desc()).all())
    inv_user_ids = {i.user_id for i in invoices}
    if inv_user_ids:
        for u in User.query.filter(User.id.in_(inv_user_ids)).all():
            names[u.id] = f"{u.firstname or ''} {u.lastname or ''}".strip() or u.email
    invoice_rows = [{
        'id': i.id, 'client': names.get(i.user_id, '—'), 'year': i.tax_year,
        'minutes': i.minutes_total, 'amount': i.amount, 'status': i.status,
        'created_at': i.created_at,
    } for i in invoices]

    return render_template(
        'time_tracking.html',
        engagements=engagements, entries=entry_rows, unbilled_groups=unbilled_groups,
        invoices=invoice_rows, default_rate=default_rate, is_manager=is_manager,
        today=date.today(),
    )


@time_bp.route('/add', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def add_entry():
    _firm_ids_or_403()
    engagement = request.form.get('engagement', '')  # "user_id:year"
    try:
        uid_str, year_str = engagement.split(':', 1)
        user_id, year = int(uid_str), int(year_str)
    except (ValueError, AttributeError):
        flash("Bitte ein Mandat auswählen.", "error")
        return redirect(url_for('time_tracking.index'))

    minutes = parse_int(request.form.get('minutes'))
    description = (request.form.get('description') or '').strip()
    rate = _parse_rate(request.form.get('rate'))
    spent_on_str = request.form.get('spent_on')

    if not advisor_is_bound(user_id, year):
        abort(403)
    if not minutes or minutes <= 0 or not description or rate is None:
        flash("Bitte Dauer, Beschreibung und Ansatz korrekt ausfüllen.", "error")
        return redirect(url_for('time_tracking.index'))
    try:
        spent_on = datetime.strptime(spent_on_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        spent_on = date.today()

    ty = TaxYear.query.filter_by(user_id=user_id, year=year).first()
    db.session.add(TimeEntry(
        advisor_id=ty.advisor_id, user_id=user_id, tax_year=year,
        author_id=current_user.id, spent_on=spent_on, minutes=minutes,
        description=description[:255], rate_chf=rate,
    ))
    if commit_or_rollback():
        log_action('time.add', target_type='tax_year', target_id=year,
                   detail=f"{minutes}min")
        flash("Zeit erfasst.", "success")
    else:
        flash("Zeit konnte nicht erfasst werden.", "error")
    return redirect(url_for('time_tracking.index'))


@time_bp.route('/<int:entry_id>/delete', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def delete_entry(entry_id):
    ids = _firm_ids_or_403()
    e = TimeEntry.query.get(entry_id)
    if not e or e.advisor_id not in ids:
        abort(403)
    if e.billed:
        flash("Bereits abgerechnete Einträge können nicht gelöscht werden.", "error")
        return redirect(url_for('time_tracking.index'))
    db.session.delete(e)
    if commit_or_rollback():
        log_action('time.delete', target_type='tax_year', target_id=e.tax_year)
        flash("Eintrag gelöscht.", "success")
    else:
        flash("Löschen fehlgeschlagen.", "error")
    return redirect(url_for('time_tracking.index'))


@time_bp.route('/invoice', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def create_invoice():
    ids = _firm_ids_or_403()
    if not can_manage_firm():
        abort(403)
    user_id = parse_int(request.form.get('user_id'))
    year = parse_int(request.form.get('tax_year'))
    if user_id is None or year is None:
        flash("Fehlende Angaben.", "error")
        return redirect(url_for('time_tracking.index'))
    if not advisor_is_bound(user_id, year):
        abort(403)

    entries = (TimeEntry.query
               .filter(TimeEntry.advisor_id.in_(ids), TimeEntry.user_id == user_id,
                       TimeEntry.tax_year == year, TimeEntry.billed.is_(False)).all())
    if not entries:
        flash("Keine offenen Zeiteinträge für dieses Mandat.", "error")
        return redirect(url_for('time_tracking.index'))

    total_minutes = sum(e.minutes for e in entries)
    total_amount = sum((e.amount for e in entries), Decimal('0.00'))
    inv = ClientInvoice(
        advisor_id=entries[0].advisor_id, user_id=user_id, tax_year=year,
        minutes_total=total_minutes, amount=total_amount, status='offen',
        created_by=current_user.id,
    )
    db.session.add(inv)
    db.session.flush()
    for e in entries:
        e.billed = True
        e.invoice_id = inv.id
    if commit_or_rollback():
        log_action('invoice.create', target_type='tax_year', target_id=year,
                   detail=f"CHF {total_amount}")
        flash(f"Rechnung über CHF {total_amount} erstellt.", "success")
    else:
        flash("Rechnung konnte nicht erstellt werden.", "error")
    return redirect(url_for('time_tracking.index'))


@time_bp.route('/invoice/<int:invoice_id>/status', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def set_invoice_status(invoice_id):
    ids = _firm_ids_or_403()
    if not can_manage_firm():
        abort(403)
    status = request.form.get('status')
    if status not in ('offen', 'bezahlt', 'storniert'):
        flash("Ungültiger Status.", "error")
        return redirect(url_for('time_tracking.index'))
    inv = ClientInvoice.query.get(invoice_id)
    if not inv or inv.advisor_id not in ids:
        abort(403)

    inv.status = status
    # Cancelling releases the time entries so they can be re-billed.
    if status == 'storniert':
        for e in TimeEntry.query.filter_by(invoice_id=inv.id).all():
            e.billed = False
            e.invoice_id = None
    if commit_or_rollback():
        log_action('invoice.status', target_type='tax_year', target_id=inv.tax_year,
                   detail=status)
        flash("Rechnungsstatus aktualisiert.", "success")
    else:
        flash("Aktualisierung fehlgeschlagen.", "error")
    return redirect(url_for('time_tracking.index'))
