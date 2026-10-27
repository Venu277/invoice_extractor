"""add_reset_token_in_workspace_and_collections

Revision ID: fca048943767
Revises: ff6dc3a24383
Create Date: 2026-10-28 00:49:13.545430

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fca048943767'
down_revision: Union[str, Sequence[str], None] = 'ff6dc3a24383'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema idempotently across SQLite and PostgreSQL."""
    if context.is_offline_mode():
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('reset_token', sa.String(length=255), nullable=True))
            batch_op.add_column(sa.Column('reset_token_expires', sa.DateTime(), nullable=True))

        with op.batch_alter_table('invoices', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('in_workspace', sa.Boolean(), nullable=False, server_default=sa.true())
            )

        op.create_table(
            'invoice_collections',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('business_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('name_normalized', sa.String(length=100), nullable=False),
            sa.Column('month', sa.Integer(), nullable=False),
            sa.Column('year', sa.Integer(), nullable=False),
            sa.Column('invoice_ids', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('invoice_collections', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_invoice_collections_business_id'), ['business_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_invoice_collections_name_normalized'), ['name_normalized'], unique=False)
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Update 'users' table: add reset_token and reset_token_expires if not present
    if 'users' in existing_tables:
        user_cols = {col['name'] for col in inspector.get_columns('users')}
        with op.batch_alter_table('users', schema=None) as batch_op:
            if 'reset_token' not in user_cols:
                batch_op.add_column(sa.Column('reset_token', sa.String(length=255), nullable=True))
            if 'reset_token_expires' not in user_cols:
                batch_op.add_column(sa.Column('reset_token_expires', sa.DateTime(), nullable=True))

    # 2. Update 'invoices' table: add in_workspace if not present
    if 'invoices' in existing_tables:
        inv_cols = {col['name'] for col in inspector.get_columns('invoices')}
        if 'in_workspace' not in inv_cols:
            with op.batch_alter_table('invoices', schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column('in_workspace', sa.Boolean(), nullable=False, server_default=sa.true())
                )

    # 3. Create 'invoice_collections' table if not present
    if 'invoice_collections' not in existing_tables:
        op.create_table(
            'invoice_collections',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('business_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('name_normalized', sa.String(length=100), nullable=False),
            sa.Column('month', sa.Integer(), nullable=False),
            sa.Column('year', sa.Integer(), nullable=False),
            sa.Column('invoice_ids', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('invoice_collections', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_invoice_collections_business_id'), ['business_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_invoice_collections_name_normalized'), ['name_normalized'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    if context.is_offline_mode():
        with op.batch_alter_table('invoice_collections', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_invoice_collections_name_normalized'))
            batch_op.drop_index(batch_op.f('ix_invoice_collections_business_id'))
        op.drop_table('invoice_collections')

        with op.batch_alter_table('invoices', schema=None) as batch_op:
            batch_op.drop_column('in_workspace')

        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('reset_token_expires')
            batch_op.drop_column('reset_token')
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'invoice_collections' in existing_tables:
        with op.batch_alter_table('invoice_collections', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_invoice_collections_name_normalized'))
            batch_op.drop_index(batch_op.f('ix_invoice_collections_business_id'))
        op.drop_table('invoice_collections')

    if 'invoices' in existing_tables:
        inv_cols = {col['name'] for col in inspector.get_columns('invoices')}
        if 'in_workspace' in inv_cols:
            with op.batch_alter_table('invoices', schema=None) as batch_op:
                batch_op.drop_column('in_workspace')

    if 'users' in existing_tables:
        user_cols = {col['name'] for col in inspector.get_columns('users')}
        with op.batch_alter_table('users', schema=None) as batch_op:
            if 'reset_token_expires' in user_cols:
                batch_op.drop_column('reset_token_expires')
            if 'reset_token' in user_cols:
                batch_op.drop_column('reset_token')

