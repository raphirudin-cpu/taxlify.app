"""seed default billing plans

Reference/catalog data: the billing page needs at least one Plan to sell
slots. Seeds a default catalog only when the table is empty, so it never
clobbers plans an operator has customized.

Revision ID: e1f2a3b4c5d6
Revises: d4a9c1f60b82
Create Date: 2026-08-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'd4a9c1f60b82'
branch_labels = None
depends_on = None


_PLANS = (
    # name,       tier, monthly_price, base_slots, slot_price
    ("Starter",   1,  49.00,   5,  9.00),
    ("Team",      2, 149.00,  25,  7.00),
    ("Kanzlei",   3, 449.00, 100,  5.00),
)


def upgrade():
    plans = sa.table(
        "plans",
        sa.column("name", sa.String),
        sa.column("tier_level", sa.Integer),
        sa.column("monthly_price", sa.Numeric),
        sa.column("base_slots", sa.Integer),
        sa.column("slot_price", sa.Numeric),
    )
    bind = op.get_bind()
    existing = bind.execute(sa.text("SELECT COUNT(*) FROM plans")).scalar()
    if existing:
        return  # don't touch an operator-customized catalog
    op.bulk_insert(plans, [
        {"name": n, "tier_level": t, "monthly_price": mp,
         "base_slots": bs, "slot_price": sp}
        for (n, t, mp, bs, sp) in _PLANS
    ])


def downgrade():
    # Only remove the exact seeded rows.
    names = ", ".join(f"'{n}'" for (n, *_rest) in _PLANS)
    op.execute(f"DELETE FROM plans WHERE name IN ({names})")
