"""Batch 2 schema improvements

Revision ID: batch_2_schema_improvements
Revises: batch_1_schema_improvements
Create Date: 2026-09-09 10:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision = 'batch_2_schema_improvements'
down_revision = 'batch_1_schema_improvements'
branch_labels = None
depends_on = None

def upgrade():
    # ----------------------------------------------------
    # 1. Create `refunds` table
    # ----------------------------------------------------
    # Drop table if it exists from a previous failed run
    op.execute('DROP TABLE IF EXISTS refunds')
    op.create_table(
        'refunds',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('processed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['processed_by'], ['users.id'], ondelete='SET NULL'),
    )

    # ----------------------------------------------------
    # 2. Add columns to `orders` and `order_items`
    # ----------------------------------------------------
    op.add_column('orders', sa.Column('qr_code_path', sa.String(length=255), nullable=True))
    op.add_column('orders', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('orders', sa.Column('tax_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'))
    op.add_column('orders', sa.Column('discount_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'))
    
    op.add_column('order_items', sa.Column('original_price', sa.Numeric(precision=10, scale=2), nullable=True))

    # ----------------------------------------------------
    # 3. Data Migration: Extract Refunds from Orders
    # ----------------------------------------------------
    connection = op.get_bind()
    
    # Select orders that have a refund_amount > 0 or a refund_reason
    orders_with_refunds = connection.execute(sa.text(
        "SELECT id, refund_amount, refund_reason, refund_status FROM orders WHERE refund_amount > 0 OR refund_reason IS NOT NULL OR refund_status IS NOT NULL"
    )).fetchall()
    
    for row in orders_with_refunds:
        order_id = row[0]
        amount = row[1] if row[1] is not None else 0.00
        reason = row[2]
        status = row[3] if row[3] else 'pending'
        
        connection.execute(
            sa.text(
                "INSERT INTO refunds (order_id, amount, reason, status, created_at, updated_at) "
                "VALUES (:order_id, :amount, :reason, :status, :created_at, :updated_at)"
            ),
            {
                "order_id": order_id, 
                "amount": amount, 
                "reason": reason, 
                "status": status,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        )

    # ----------------------------------------------------
    # 4. Clean up `orders` columns (Drop old fields)
    # ----------------------------------------------------
    op.drop_column('orders', 'qr_code_base64')
    op.drop_column('orders', 'refund_reason')


def downgrade():
    # Re-add columns to orders
    op.add_column('orders', sa.Column('refund_reason', sa.Text(), nullable=True))
    op.add_column('orders', sa.Column('qr_code_base64', sa.Text(), nullable=True))
    
    # Data migration back to orders
    connection = op.get_bind()
    refunds = connection.execute(sa.text("SELECT order_id, amount, reason, status FROM refunds")).fetchall()
    for row in refunds:
        order_id = row[0]
        amount = row[1]
        reason = row[2]
        status = row[3]
        connection.execute(sa.text(
            "UPDATE orders SET refund_amount = :amount, refund_reason = :reason, refund_status = :status WHERE id = :order_id"
        ), {"amount": amount, "reason": reason, "status": status, "order_id": order_id})
    
    # Drop new columns and tables
    op.drop_column('order_items', 'original_price')
    op.drop_column('orders', 'discount_amount')
    op.drop_column('orders', 'tax_amount')
    op.drop_column('orders', 'notes')
    op.drop_column('orders', 'qr_code_path')
    op.drop_table('refunds')
