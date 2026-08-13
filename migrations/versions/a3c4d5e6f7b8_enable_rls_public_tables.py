"""enable Row Level Security on all public tables

Supabase auto-exposes public-schema tables through its PostgREST Data API
(reachable with the public 'anon' key). With RLS disabled that API can
read/write every row, bypassing the app. This app never uses the Data API —
it connects directly to Postgres as the 'postgres' owner role (which has
BYPASSRLS) — so enabling RLS with no policies denies the anon/authenticated
API roles while leaving the app's direct access unaffected.

New tables added in later migrations must enable RLS too (Postgres has no
"default RLS on"): add `ALTER TABLE public.<t> ENABLE ROW LEVEL SECURITY;`
to those migrations, or re-run an enable sweep.

Revision ID: a3c4d5e6f7b8
Revises: f2b3c4d5e6a7
Create Date: 2026-08-13 13:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a3c4d5e6f7b8'
down_revision = 'f2b3c4d5e6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
                EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
            END LOOP;
        END $$;
    """)


def downgrade():
    op.execute("""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
                EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', r.tablename);
            END LOOP;
        END $$;
    """)
