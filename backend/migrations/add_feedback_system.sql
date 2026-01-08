-- Feedback System Tables
-- Allows users to submit feedback, bug reports, and feature requests
-- Includes admin panel support for feedback management

-- Feedback submissions table
CREATE TABLE IF NOT EXISTS feedback_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    feedback_type VARCHAR(50) NOT NULL CHECK (feedback_type IN ('bug', 'feature_request', 'general', 'other')),
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(50) DEFAULT 'new' CHECK (status IN ('new', 'in_review', 'in_progress', 'resolved', 'closed', 'wont_fix')),
    category VARCHAR(100),
    affected_feature VARCHAR(100),
    browser_info JSONB,
    device_info JSONB,
    screenshot_url TEXT,
    attachments JSONB,
    admin_notes TEXT,
    admin_response TEXT,
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feedback comments/conversation thread
CREATE TABLE IF NOT EXISTS feedback_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_id UUID REFERENCES feedback_submissions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_admin_response BOOLEAN DEFAULT false,
    comment_text TEXT NOT NULL,
    attachments JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Admin activity log
CREATE TABLE IF NOT EXISTS admin_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    target_type VARCHAR(100),
    target_id UUID,
    action_details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System settings table (for admin panel configuration)
CREATE TABLE IF NOT EXISTS system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    category VARCHAR(50),
    is_public BOOLEAN DEFAULT false,
    last_modified_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_submissions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback_submissions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_submissions(feedback_type, status);
CREATE INDEX IF NOT EXISTS idx_feedback_priority ON feedback_submissions(priority, status);
CREATE INDEX IF NOT EXISTS idx_feedback_assigned ON feedback_submissions(assigned_to, status);

CREATE INDEX IF NOT EXISTS idx_feedback_comments_feedback ON feedback_comments(feedback_id, created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_comments_user ON feedback_comments(user_id);

CREATE INDEX IF NOT EXISTS idx_admin_log_user ON admin_activity_log(admin_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_log_action ON admin_activity_log(action_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_log_target ON admin_activity_log(target_type, target_id);

CREATE INDEX IF NOT EXISTS idx_system_settings_category ON system_settings(category);

-- Comments for documentation
COMMENT ON TABLE feedback_submissions IS 'User feedback, bug reports, and feature requests';
COMMENT ON TABLE feedback_comments IS 'Comments and conversation thread for feedback items';
COMMENT ON TABLE admin_activity_log IS 'Audit log of all admin actions';
COMMENT ON TABLE system_settings IS 'System-wide configuration settings';

COMMENT ON COLUMN feedback_submissions.feedback_type IS 'Type: bug, feature_request, general, other';
COMMENT ON COLUMN feedback_submissions.status IS 'Status: new, in_review, in_progress, resolved, closed, wont_fix';
COMMENT ON COLUMN feedback_submissions.priority IS 'Priority: low, medium, high, critical';
COMMENT ON COLUMN feedback_submissions.browser_info IS 'Browser and OS information for bug reports';
COMMENT ON COLUMN feedback_submissions.attachments IS 'Array of attachment URLs and metadata';
