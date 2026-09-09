"""Batch 4 schema tightening

Revision ID: batch_4_schema_tightening
Revises: batch_3_status_normalization
Create Date: 2026-09-09 10:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'batch_4_schema_tightening'
down_revision = 'batch_3_status_normalization'
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()

    # ----------------------------------------------------
    # 1. Update VARCHAR lengths for User table
    # ----------------------------------------------------
    op.alter_column('users', 'emergency_contact',
               existing_type=mysql.VARCHAR(length=255),
               type_=mysql.VARCHAR(length=100),
               existing_nullable=True)

    op.alter_column('users', 'rfid_tag',
               existing_type=mysql.VARCHAR(length=100),
               type_=mysql.VARCHAR(length=50),
               existing_nullable=True)

    op.alter_column('users', 'pin_hash',
               existing_type=mysql.VARCHAR(length=255),
               type_=mysql.VARCHAR(length=100),
               existing_nullable=True)

    # ----------------------------------------------------
    # 2. Migrate AdminAuditLog data to AuditLog
    # ----------------------------------------------------
    # Read existing admin_audit_logs and insert into audit_logs
    has_admin_audit_logs = connection.execute(sa.text("SHOW TABLES LIKE 'admin_audit_logs'")).fetchone()
    if has_admin_audit_logs:
        res = connection.execute(sa.text("SELECT * FROM admin_audit_logs"))
        if hasattr(res, 'mappings'):
            admin_logs = res.mappings().fetchall()
        else:
            # Fallback for older SQLAlchemy
            keys = res.keys()
            admin_logs = [dict(zip(keys, row)) for row in res]
            
        for log in admin_logs:
            connection.execute(
                sa.text("""
                    INSERT INTO audit_logs (actor_id, actor_role, action, resource_type, resource_id, new_value, timestamp)
                    VALUES (:actor_id, 'admin', :action, :resource_type, :resource_id, :new_value, :timestamp)
                """),
                {
                    "actor_id": log['admin_id'],
                    "action": log['action'],
                    "resource_type": log['target_entity'],
                    "resource_id": log['target_id'],
                    "new_value": log['details'],
                    "timestamp": log['created_at']
                }
            )

        # Drop admin_audit_logs
        op.drop_table('admin_audit_logs')

    # ----------------------------------------------------
    # 3. Rename production_batches to kitchen_production_batches
    # ----------------------------------------------------
    connection.execute(sa.text("DROP TABLE IF EXISTS kitchen_production_batches"))
    op.rename_table('production_batches', 'kitchen_production_batches')


def downgrade():
    # Reverse table rename
    op.rename_table('kitchen_production_batches', 'production_batches')

    # Recreate admin_audit_logs
    op.create_table('admin_audit_logs',
        sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('admin_id', mysql.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('action', mysql.VARCHAR(length=255), nullable=False),
        sa.Column('target_entity', mysql.VARCHAR(length=100), nullable=True),
        sa.Column('target_id', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('details', mysql.TEXT(), nullable=True),
        sa.Column('created_at', mysql.DATETIME(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], name='admin_audit_logs_ibfk_1', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_default_charset='utf8mb4',
        mysql_engine='InnoDB'
    )

    # Reverse VARCHAR lengths
    op.alter_column('users', 'pin_hash',
               existing_type=mysql.VARCHAR(length=100),
               type_=mysql.VARCHAR(length=255),
               existing_nullable=True)

    op.alter_column('users', 'rfid_tag',
               existing_type=mysql.VARCHAR(length=50),
               type_=mysql.VARCHAR(length=100),
               existing_nullable=True)

    op.alter_column('users', 'emergency_contact',
               existing_type=mysql.VARCHAR(length=100),
               type_=mysql.VARCHAR(length=255),
               existing_nullable=True)
