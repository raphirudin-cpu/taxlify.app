"""time tracking + client billing

Revision ID: c8e3f5a17b26
Revises: b7f2a1c9d3e4
Create Date: 2026-08-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8e3f5a17b26'
down_revision = 'b7f2a1c9d3e4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('advisor',
                  sa.Column('default_hourly_rate', sa.Numeric(10, 2), nullable=True))

    op.create_table(
        'client_invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('advisor_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('minutes_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='offen'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['advisor_id'], ['advisor.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'time_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('advisor_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('spent_on', sa.Date(), nullable=False),
        sa.Column('minutes', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('rate_chf', sa.Numeric(10, 2), nullable=False),
        sa.Column('billed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['advisor_id'], ['advisor.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['author_id'], ['user.id']),
        sa.ForeignKeyConstraint(['invoice_id'], ['client_invoices.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('time_entries')
    op.drop_table('client_invoices')
    op.drop_column('advisor', 'default_hourly_rate')
