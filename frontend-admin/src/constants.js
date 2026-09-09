export const ORDER_STATUS = {
    PENDING: 'pending',
    PROCESSING: 'processing',
    READY: 'ready',
    OUT_FOR_DELIVERY: 'out_for_delivery',
    DELIVERED: 'delivered',
    CANCELLED: 'cancelled'
};

export const PAYMENT_STATUS = {
    UNPAID: 'unpaid',
    PAID: 'paid',
    FAILED: 'failed',
    REFUNDED: 'refunded'
};

export const REFUND_STATUS = {
    PENDING: 'pending',
    APPROVED: 'approved',
    REJECTED: 'rejected',
    COMPLETED: 'completed'
};

export const TICKET_STATUS = {
    OPEN: 'open',
    RESOLVED: 'resolved',
    CLOSED: 'closed'
};

export const STOCK_REQUEST_STATUS = {
    PENDING: 'pending',
    APPROVED: 'approved',
    FULFILLED: 'fulfilled',
    REJECTED: 'rejected'
};
