import enum

class OrderStatus(str, enum.Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    READY = 'ready'
    SHIPPED = 'shipped'
    OUT_FOR_DELIVERY = 'out_for_delivery'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'

class PaymentStatus(str, enum.Enum):
    UNPAID = 'unpaid'
    PAID = 'paid'
    FAILED = 'failed'
    REFUNDED = 'refunded'

class RefundStatus(str, enum.Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    COMPLETED = 'completed'

class TransactionStatus(str, enum.Enum):
    CREATED = 'created'
    CAPTURED = 'captured'
    FAILED = 'failed'
    REFUNDED = 'refunded'

class StaffShiftStatus(str, enum.Enum):
    ACTIVE = 'active'
    CLOSED = 'closed'

class ProductionBatchStatus(str, enum.Enum):
    PRODUCED = 'produced'
    DISPATCHED = 'dispatched'

class BroadcastMessageStatus(str, enum.Enum):
    SENT = 'sent'
    PENDING = 'pending'
    FAILED = 'failed'

class SupportTicketStatus(str, enum.Enum):
    OPEN = 'open'
    RESOLVED = 'resolved'
    CLOSED = 'closed'

class StockRequestStatus(str, enum.Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    FULFILLED = 'fulfilled'
    REJECTED = 'rejected'
