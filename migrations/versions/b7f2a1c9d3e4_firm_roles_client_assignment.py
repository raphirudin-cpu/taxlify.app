"""firm roles + per-client assignment

Revision ID: b7f2a1c9d3e4
Revises: 8c4bf7543916
Create Date: 2026-08-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f2a1c9d3e4'
down_revision = '8c4bf7543916'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('team_members',
                  sa.Column('role', sa.String(length=20), nullable=False,
                            server_default='staff'))
    op.add_column('tax_years',
                  sa.Column('assignee_id', sa.Integer(), nullable=True))
    op.create_foreign_key('tax_years_assignee_id_fkey', 'tax_years', 'user',
                          ['assignee_id'], ['id'])


def downgrade():
    op.drop_constraint('tax_years_assignee_id_fkey', 'tax_years', type_='foreignkey')
    op.drop_column('tax_years', 'assignee_id')
    op.drop_column('team_members', 'role')
