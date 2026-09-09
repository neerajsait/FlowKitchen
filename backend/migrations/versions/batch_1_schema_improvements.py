"""Batch 1 schema improvements

Revision ID: batch_1_schema_improvements
Revises: db73f3f54427
Create Date: 2026-09-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision = 'batch_1_schema_improvements'
down_revision = 'c4d8e5f7a9b1'  # Fixed to correct head
branch_labels = None
depends_on = None

def upgrade():
    # ----------------------------------------------------
    # 1. Clean up Duplicate Favorites
    # ----------------------------------------------------
    # Keep the most recent favorite, delete older duplicates
    connection = op.get_bind()
    connection.execute(sa.text("""
        DELETE f1 FROM favorites f1
        INNER JOIN favorites f2 
        WHERE f1.id < f2.id 
          AND f1.customer_id = f2.customer_id 
          AND f1.menu_item_id = f2.menu_item_id;
    """))

    # ----------------------------------------------------
    # 2. Add constraints to favorites and coupons
    # ----------------------------------------------------
    op.create_unique_constraint('uix_customer_menu_item', 'favorites', ['customer_id', 'menu_item_id'])
    
    # Check constraints might not be strictly enforced in older MySQL versions, but it's good practice.
    op.create_check_constraint('chk_coupon_discount', 'coupons', 'discount_pct IS NOT NULL OR discount_amount IS NOT NULL')

    # ----------------------------------------------------
    # 3. Add order_number to orders safely
    # ----------------------------------------------------
    # Add column as nullable first
    op.add_column('orders', sa.Column('order_number', sa.String(length=30), nullable=True))
    
    # Generate unique order numbers for existing data
    orders = connection.execute(sa.text("SELECT id, created_at FROM orders WHERE order_number IS NULL")).fetchall()
    for order in orders:
        order_id = order[0]
        # order[1] is created_at
        created_at = order[1] if order[1] else datetime.now(timezone.utc)
        
        if isinstance(created_at, str):
            # parse string if needed, or just use current time for generation format
            date_str = created_at[:10].replace("-", "") if len(created_at) >= 10 else datetime.now(timezone.utc).strftime('%Y%m%d')
        else:
            date_str = created_at.strftime('%Y%m%d')
            
        unique_suffix = uuid.uuid4().hex[:6].upper()
        order_number = f"ORD-{date_str}-{unique_suffix}"
        
        connection.execute(
            sa.text("UPDATE orders SET order_number = :order_number WHERE id = :id"),
            {"order_number": order_number, "id": order_id}
        )

    # Now alter column to be NOT NULL
    op.alter_column('orders', 'order_number',
               existing_type=sa.String(length=30),
               nullable=False)
               
    # Add unique constraint for order_number
    op.create_unique_constraint('uq_orders_order_number', 'orders', ['order_number'])

    # ----------------------------------------------------
    # 4. Add new indexes to orders
    # ----------------------------------------------------
    op.create_index('ix_order_status_payment', 'orders', ['status', 'payment_status'], unique=False)
    op.create_index('ix_order_outlet_created', 'orders', ['outlet_id', 'created_at'], unique=False)
    op.create_index('ix_orders_created_at', 'orders', ['created_at'], unique=False)
    op.create_index('ix_orders_customer_id', 'orders', ['customer_id'], unique=False)

    # ----------------------------------------------------
    # 5. Clear QR codes
    # ----------------------------------------------------
    connection.execute(sa.text("UPDATE orders SET qr_code_base64 = NULL"))


def downgrade():
    # ----------------------------------------------------
    # 1. Downgrade QR codes 
    # ----------------------------------------------------
    # Cannot recover deleted QR codes easily, leaving as NULL
    
    # ----------------------------------------------------
    # 2. Drop new indexes from orders
    # ----------------------------------------------------
    op.drop_index('ix_orders_customer_id', table_name='orders')
    op.drop_index('ix_orders_created_at', table_name='orders')
    op.drop_index('ix_order_outlet_created', table_name='orders')
    op.drop_index('ix_order_status_payment', table_name='orders')

    # ----------------------------------------------------
    # 3. Drop order_number from orders
    # ----------------------------------------------------
    op.drop_constraint('uq_orders_order_number', 'orders', type_='unique')
    op.drop_column('orders', 'order_number')

    # ----------------------------------------------------
    # 4. Drop constraints from favorites and coupons
    # ----------------------------------------------------
    op.drop_constraint('chk_coupon_discount', 'coupons', type_='check')
    op.drop_constraint('uix_customer_menu_item', 'favorites', type_='unique')
