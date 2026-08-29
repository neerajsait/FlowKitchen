"""Add online payment tracking (Razorpay)

Revision ID: c4d8e5f7a9b1
Revises: 1b79288e803e
Create Date: 2026-08-25 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d8e5f7a9b1'
down_revision = '1b79288e803e'
branch_labels = None
depends_on = None


def upgrade():
    # Order payment tracking columns
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('razorpay_order_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('razorpay_payment_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('payment_status', sa.String(length=20), nullable=False,
                                      server_default='unpaid'))
        batch_op.add_column(sa.Column('paid_at', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_orders_razorpay_order_id'), ['razorpay_order_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_payment_status'), ['payment_status'], unique=False)

    # Payment audit trail
    op.create_table(
        'payment_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('provider_order_id', sa.String(length=64), nullable=True),
        sa.Column('provider_payment_id', sa.String(length=64), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('event', sa.String(length=50), nullable=False),
        sa.Column('signature_valid', sa.Boolean(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('raw_payload', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payment_transactions_order_id'), 'payment_transactions', ['order_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_payment_transactions_order_id'), table_name='payment_transactions')
    op.drop_table('payment_transactions')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_orders_payment_status'))
        batch_op.drop_index(batch_op.f('ix_orders_razorpay_order_id'))
        batch_op.drop_column('paid_at')
        batch_op.drop_column('payment_status')
        batch_op.drop_column('razorpay_payment_id')
        batch_op.drop_column('razorpay_order_id')