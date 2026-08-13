"""subscription unique per (user, tax_year), not per user

The subscriptions table had a UNIQUE constraint on user_id alone, which
capped each advisor at a single subscription — so they could buy slots for
only ONE tax year. Slots are sold per tax year, so the constraint must be
composite (user_id, tax_year).

Revision ID: f2b3c4d5e6a7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-13 12:30:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f2b3c4d5e6a7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the old single-column unique (Postgres auto-named it
    # subscriptions_user_id_key when the column was declared unique).
    op.drop_constraint('subscriptions_user_id_key', 'subscriptions', type_='unique')
    op.create_unique_constraint(
        'uq_subscription_user_year', 'subscriptions', ['user_id', 'tax_year'])


def downgrade():
    op.drop_constraint('uq_subscription_user_year', 'subscriptions', type_='unique')
    op.create_unique_constraint(
        'subscriptions_user_id_key', 'subscriptions', ['user_id'])
