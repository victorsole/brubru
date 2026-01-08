-- Migration 004: Add Notifications Table
-- Part of My EU Bubble - Phase 5: Smart Alerts/Notifications System

-- Create notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Notification type
    notification_type VARCHAR(50) NOT NULL,
    -- Types: new_feed_entry, status_change, deadline, policy_update, amendment_update

    -- Content
    title VARCHAR(500) NOT NULL,
    message TEXT NOT NULL,
    action_url VARCHAR(500),

    -- Metadata
    metadata JSONB,

    -- Related entities
    related_entity_type VARCHAR(50),
    related_entity_id UUID,

    -- Priority and status
    priority VARCHAR(20) DEFAULT 'normal',
    is_read BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    read_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(notification_type);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, is_read) WHERE is_read = FALSE;

-- Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_notifications_user_type_read ON notifications(user_id, notification_type, is_read);

-- Add trigger to update user's last notification time (optional)
CREATE OR REPLACE FUNCTION update_user_last_notification()
RETURNS TRIGGER AS $$
BEGIN
    -- This could update a last_notification_at field in users table if it existed
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_user_notification
    AFTER INSERT ON notifications
    FOR EACH ROW
    EXECUTE FUNCTION update_user_last_notification();

-- Add comments
COMMENT ON TABLE notifications IS 'User notifications and alerts for My EU Bubble';
COMMENT ON COLUMN notifications.notification_type IS 'Type of notification: new_feed_entry, status_change, deadline, policy_update, amendment_update';
COMMENT ON COLUMN notifications.priority IS 'Priority level: low, normal, high, urgent';
COMMENT ON COLUMN notifications.metadata IS 'Additional type-specific data in JSON format';
COMMENT ON COLUMN notifications.related_entity_type IS 'Type of related entity: rss_entry, user_document, procedure, legislation';
