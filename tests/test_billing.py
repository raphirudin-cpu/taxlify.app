"""Billing: an advisor can hold slots for multiple tax years."""
from decimal import Decimal

from app import db as _db
from app.models import Plan, Subscription


def test_advisor_can_subscribe_for_multiple_years(app, make_user):
    """Regression: subscriptions were UNIQUE on user_id alone, capping an
    advisor at a single tax year. Two years for one user must both persist."""
    advisor = make_user(role="advisor")
    with app.app_context():
        plan = Plan(name="Team", tier_level=2, monthly_price=Decimal("149.00"),
                    base_slots=25, slot_price=Decimal("7.00"))
        _db.session.add(plan)
        _db.session.commit()
        for yr in (2024, 2025):
            _db.session.add(Subscription(user_id=advisor, plan_id=plan.id, slots=0, tax_year=yr))
        _db.session.commit()  # must not raise a UNIQUE violation
        years = sorted(s.tax_year for s in Subscription.query.filter_by(user_id=advisor).all())
        assert years == [2024, 2025]
