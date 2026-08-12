# app/routes/billing.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Subscription, Plan, Invoice, TaxYear, Quote, Advisor
from app.security import current_advisor
from app.helpers import commit_or_rollback
from decimal import Decimal

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

def _ensure_admin():
    if current_user.role != 'admin':
        flash("Zugriff verweigert.", "danger")
        return False
    return True

@billing_bp.route('/', methods=['GET'])
@login_required
def billing_index():
    if not _ensure_admin():
        return redirect(url_for('dashboard.dashboard'))

    # look up your advisor_id (if any)
    adv = current_advisor()
    advisor_id = adv.id if adv else None

    # Existing slot‐purchases by tax year
    purchases = (
        Subscription.query
          .filter_by(user_id=current_user.id)
          .order_by(Subscription.tax_year.desc())
          .all()
    )

    purchase_data = []
    for sub in purchases:
        plan = Plan.query.get(sub.plan_id)
        total_slots = plan.base_slots + sub.slots

        used = TaxYear.query.filter_by(
            advisor_id=advisor_id,
            year=sub.tax_year
        ).count() if advisor_id else 0

        # only count Pending or In Review quotes as reserved
        reserved = 0
        if advisor_id:
            reserved = Quote.query \
                .filter_by(advisor_id=advisor_id, tax_year=sub.tax_year) \
                .filter(Quote.quote_status.in_(['Pending', 'In Review'])) \
                .count()

        occupied = used + reserved
        remaining = total_slots - occupied

        purchase_data.append({
            'tax_year':       sub.tax_year,
            'plan_name':      plan.name,
            'base_slots':     plan.base_slots,
            'extra_slots':    sub.slots,
            'total_slots':    total_slots,
            'used_slots':     used,
            'reserved_slots': reserved,
            'occupied_slots': occupied,
            'remaining_slots': remaining,
        })

    # Available slot-packages
    plans = Plan.query.order_by(Plan.tier_level).all()

    # Invoice history
    invoices = (
        Invoice.query
               .filter_by(user_id=current_user.id)
               .order_by(Invoice.date.desc(), Invoice.id.desc())
               .all()
    )

    return render_template(
        'advisor_billing.html',
        purchases=purchase_data,
        plans=plans,
        invoices=invoices
    )

@billing_bp.route('/update', methods=['POST'])
@login_required
def billing_update():
    if not _ensure_admin():
        return redirect(url_for('dashboard.dashboard'))

    tax_year    = request.form.get('tax_year', type=int)
    new_plan_id = request.form.get('plan_id',  type=int)
    extra_slots = request.form.get('extra_slots', type=int, default=0)

    if not tax_year:
        flash("Bitte wähle ein Steuerjahr.", "warning")
        return redirect(url_for('billing.billing_index'))

    purchase = Subscription.query.filter_by(
        user_id=current_user.id,
        tax_year=tax_year
    ).first()

    # CASE 1: new purchase for that year
    if purchase is None:
        if not new_plan_id:
            flash("Bitte wähle einen Plan für dieses Jahr.", "warning")
            return redirect(url_for('billing.billing_index'))
        plan = Plan.query.get(new_plan_id)
        if not plan:
            flash("Plan nicht gefunden.", "danger")
            return redirect(url_for('billing.billing_index'))

        purchase = Subscription(
            user_id=current_user.id,
            plan_id=new_plan_id,
            tax_year=tax_year,
            slots=0
        )
        db.session.add(purchase)

        amount = plan.monthly_price
        desc   = f"{plan.base_slots}-slot package for {tax_year}"
        flash(f"{plan.name} für {tax_year} gekauft: {amount:.2f}", "success")

    # CASE 2: adding extra slots to existing year
    else:
        if extra_slots <= 0:
            flash("Bitte gib eine positive Anzahl zusätzlicher Slots ein.", "warning")
            return redirect(url_for('billing.billing_index'))

        # tiered per-slot pricing
        price_tiers = [
            (10,  Decimal('40')),
            (25,  Decimal('38')),
            (50,  Decimal('36')),
            (100, Decimal('34')),
            (200, Decimal('32')),
            (500, Decimal('30')),
        ]
        for threshold, price in price_tiers:
            if extra_slots <= threshold:
                slot_rate = price
                break
        else:
            slot_rate = price_tiers[-1][1]

        amount = slot_rate * extra_slots
        purchase.slots += extra_slots

        desc = f"{extra_slots} extra slot(s) for {tax_year}"
        flash(f"{extra_slots} Slots zu {tax_year} hinzugefügt @ {slot_rate:.2f} je: {amount:.2f}", "success")

    # Record a one-time invoice
    invoice = Invoice(
        user_id=current_user.id,
        amount=amount,
        description=desc
    )
    db.session.add(invoice)
    if not commit_or_rollback():
        flash("Fehler beim Erfassen der Rechnung.", "danger")

    return redirect(url_for('billing.billing_index'))
