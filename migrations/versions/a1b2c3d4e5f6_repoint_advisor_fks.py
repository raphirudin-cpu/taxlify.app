"""repoint advisor_id foreign keys from user.id to advisor.id

These columns store an Advisor.id (app convention) but the original FK pointed
at user.id, which Postgres enforces — breaking quote/feedback/team writes.

Revision ID: a1b2c3d4e5f6
Revises: 27245029ea06
Create Date: 2026-08-12
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '27245029ea06'
branch_labels = None
depends_on = None

_TABLES = ['tax_years', 'quotes', 'feedback', 'team_members']


def upgrade():
    for tbl in _TABLES:
        op.drop_constraint(f'{tbl}_advisor_id_fkey', tbl, type_='foreignkey')
        op.create_foreign_key(f'{tbl}_advisor_id_fkey', tbl, 'advisor', ['advisor_id'], ['id'])


def downgrade():
    for tbl in _TABLES:
        op.drop_constraint(f'{tbl}_advisor_id_fkey', tbl, type_='foreignkey')
        op.create_foreign_key(f'{tbl}_advisor_id_fkey', tbl, 'user', ['advisor_id'], ['id'])
