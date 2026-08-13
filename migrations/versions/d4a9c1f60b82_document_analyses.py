"""AI document analyses

Revision ID: d4a9c1f60b82
Revises: c8e3f5a17b26
Create Date: 2026-08-13 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4a9c1f60b82'
down_revision = 'c8e3f5a17b26'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'document_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('required_document_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('doc_type', sa.String(length=100), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('fields_json', sa.Text(), nullable=True),
        sa.Column('confidence', sa.String(length=20), nullable=True),
        sa.Column('model', sa.String(length=60), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['required_document_id'], ['required_document.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('document_analyses')
