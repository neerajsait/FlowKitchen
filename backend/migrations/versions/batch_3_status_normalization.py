"""Batch 3 status normalization

Revision ID: batch_3_status_normalization
Revises: batch_2_schema_improvements
Create Date: 2026-09-09 10:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from constants import (
    OrderStatus, PaymentStatus, RefundStatus, TransactionStatus, 
    StaffShiftStatus, ProductionBatchStatus, BroadcastMessageStatus, 
    SupportTicketStatus, StockRequestStatus
)

# revision identifiers, used by Alembic.
revision = 'batch_3_status_normalization'
down_revision = 'batch_2_schema_improvements'
branch_labels = None
depends_on = None

def upgrade():
    # ----------------------------------------------------
    # 1. Normalize existing data (Data Migration)
    # ----------------------------------------------------
    connection = op.get_bind()
    
    # Support Tickets
    connection.execute(sa.text("UPDATE support_tickets SET status = 'open' WHERE status = 'Open'"))
    connection.execute(sa.text("UPDATE support_tickets SET status = 'resolved' WHERE status = 'Resolved'"))
    connection.execute(sa.text("UPDATE support_tickets SET status = 'closed' WHERE status = 'Closed'"))

    # Stock Requests
    connection.execute(sa.text("UPDATE stock_requests SET status = 'pending' WHERE status = 'Pending'"))
    connection.execute(sa.text("UPDATE stock_requests SET status = 'approved' WHERE status = 'Approved'"))
    connection.execute(sa.text("UPDATE stock_requests SET status = 'fulfilled' WHERE status = 'Fulfilled'"))
    connection.execute(sa.text("UPDATE stock_requests SET status = 'rejected' WHERE status = 'Rejected'"))
    
    # Broadcast Messages
    connection.execute(sa.text("UPDATE broadcast_messages SET status = 'sent' WHERE status = 'Sent'"))
    connection.execute(sa.text("UPDATE broadcast_messages SET status = 'pending' WHERE status = 'Pending'"))
    connection.execute(sa.text("UPDATE broadcast_messages SET status = 'failed' WHERE status = 'Failed'"))

    # ----------------------------------------------------
    # 2. Alter Columns to Enum Type
    # ----------------------------------------------------
    # orders.status
    op.alter_column('orders', 'status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum(OrderStatus),
               existing_nullable=False,
               existing_server_default='pending')

    # orders.refund_status
    op.alter_column('orders', 'refund_status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum(RefundStatus),
               existing_nullable=True)

    # orders.payment_status
    op.alter_column('orders', 'payment_status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum(PaymentStatus),
               existing_nullable=False,
               existing_server_default='unpaid')

    # payment_transactions.status
    op.alter_column('payment_transactions', 'status',
               existing_type=mysql.VARCHAR(length=30),
               type_=sa.Enum(TransactionStatus),
               existing_nullable=False)

    # refunds.status
    op.alter_column('refunds', 'status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum(RefundStatus),
               existing_nullable=False,
               existing_server_default='pending')

    # staff_shifts.status
    op.alter_column('staff_shifts', 'status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum(StaffShiftStatus),
               existing_nullable=False,
               existing_server_default='active')

    # production_batches.status
    op.alter_column('production_batches', 'status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum(ProductionBatchStatus),
               existing_nullable=True,
               existing_server_default='produced')

    # broadcast_messages.status
    op.alter_column('broadcast_messages', 'status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum(BroadcastMessageStatus),
               existing_nullable=True,
               existing_server_default='sent')

    # support_tickets.status
    op.alter_column('support_tickets', 'status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum(SupportTicketStatus),
               existing_nullable=True,
               existing_server_default='open')

    # stock_requests.status
    op.alter_column('stock_requests', 'status',
               existing_type=mysql.VARCHAR(length=20),
               type_=sa.Enum(StockRequestStatus),
               existing_nullable=True,
               existing_server_default='pending')


def downgrade():
    op.alter_column('stock_requests', 'status',
               existing_type=sa.Enum(StockRequestStatus),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=True,
               existing_server_default='Pending')
    
    op.alter_column('support_tickets', 'status',
               existing_type=sa.Enum(SupportTicketStatus),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=True,
               existing_server_default='Open')

    op.alter_column('broadcast_messages', 'status',
               existing_type=sa.Enum(BroadcastMessageStatus),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=True,
               existing_server_default='sent')

    op.alter_column('production_batches', 'status',
               existing_type=sa.Enum(ProductionBatchStatus),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=True,
               existing_server_default='produced')

    op.alter_column('staff_shifts', 'status',
               existing_type=sa.Enum(StaffShiftStatus),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=False,
               existing_server_default='active')

    op.alter_column('refunds', 'status',
               existing_type=sa.Enum(RefundStatus),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=False,
               existing_server_default='pending')

    op.alter_column('payment_transactions', 'status',
               existing_type=sa.Enum(TransactionStatus),
               type_=mysql.VARCHAR(length=30),
               existing_nullable=False)

    op.alter_column('orders', 'payment_status',
               existing_type=sa.Enum(PaymentStatus),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=False,
               existing_server_default='unpaid')

    op.alter_column('orders', 'refund_status',
               existing_type=sa.Enum(RefundStatus),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=True)

    op.alter_column('orders', 'status',
               existing_type=sa.Enum(OrderStatus),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=False,
               existing_server_default='pending')
