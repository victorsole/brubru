-- Migration: Add user_documents table
-- Date: 2025-11-08
-- Description: Creates table for user-created documents (amendments, analyses, strategies, notes)

-- ============================================================================
-- User Documents Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Document type and metadata
    document_type VARCHAR(50) NOT NULL,  -- amendment, analysis, strategy, note
    title VARCHAR(500) NOT NULL,
    content TEXT,

    -- Links to EU legislation/procedures
    celex_number VARCHAR(100),
    procedure_reference VARCHAR(100),

    -- Policy areas and tags
    policy_areas TEXT[],
    tags TEXT[],

    -- Amendment-specific fields
    amendment_target TEXT,
    amendment_justification TEXT,
    amendment_status VARCHAR(50),  -- draft, submitted, adopted, rejected

    -- Analysis-specific fields
    executive_summary TEXT,
    methodology TEXT,
    conclusions TEXT,
    recommendations TEXT,

    -- Strategy-specific fields
    objectives TEXT,
    action_plan TEXT,
    timeline VARCHAR(500),
    stakeholders TEXT[],

    -- Flexible metadata
    metadata JSONB,

    -- Privacy and sharing
    is_private BOOLEAN DEFAULT TRUE,
    shared_with UUID[],

    -- Version control
    version INTEGER DEFAULT 1,
    parent_document_id UUID REFERENCES user_documents(id) ON DELETE SET NULL,

    -- Search and discovery
    is_featured BOOLEAN DEFAULT FALSE,
    view_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    last_accessed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_documents_user_id ON user_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_user_documents_type ON user_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_user_documents_celex ON user_documents(celex_number);
CREATE INDEX IF NOT EXISTS idx_user_documents_procedure ON user_documents(procedure_reference);
CREATE INDEX IF NOT EXISTS idx_user_documents_policy_areas ON user_documents USING GIN (policy_areas);
CREATE INDEX IF NOT EXISTS idx_user_documents_tags ON user_documents USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_user_documents_parent ON user_documents(parent_document_id);
CREATE INDEX IF NOT EXISTS idx_user_documents_updated ON user_documents(user_id, updated_at DESC);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_user_documents_title_search ON user_documents USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_user_documents_content_search ON user_documents USING gin(to_tsvector('english', content));

-- Comments
COMMENT ON TABLE user_documents IS 'User-created documents in My EU Bubble (amendments, analyses, strategies, notes)';
COMMENT ON COLUMN user_documents.document_type IS 'Type: amendment, analysis, strategy, or note';
COMMENT ON COLUMN user_documents.celex_number IS 'CELEX number of related EU legislation';
COMMENT ON COLUMN user_documents.procedure_reference IS 'Legislative procedure reference (e.g., 2021/0106(COD))';
COMMENT ON COLUMN user_documents.policy_areas IS 'Array of policy areas from user profile';
COMMENT ON COLUMN user_documents.amendment_status IS 'Amendment status: draft, submitted, adopted, rejected';
COMMENT ON COLUMN user_documents.is_private IS 'Whether document is private (default: true)';
COMMENT ON COLUMN user_documents.version IS 'Document version number';
COMMENT ON COLUMN user_documents.parent_document_id IS 'Parent document for version control';

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_user_documents_updated_at ON user_documents;
CREATE TRIGGER update_user_documents_updated_at
    BEFORE UPDATE ON user_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Constraints
-- ============================================================================

-- Check valid document types
ALTER TABLE user_documents
ADD CONSTRAINT check_document_type CHECK (document_type IN ('amendment', 'analysis', 'strategy', 'note'));

-- Check valid amendment status
ALTER TABLE user_documents
ADD CONSTRAINT check_amendment_status CHECK (
    amendment_status IS NULL OR
    amendment_status IN ('draft', 'submitted', 'adopted', 'rejected')
);

-- ============================================================================
-- Sample Data (Optional - for testing)
-- ============================================================================

-- Uncomment to insert sample documents
/*
INSERT INTO user_documents (user_id, document_type, title, content, policy_areas, is_private)
SELECT
    id,
    'note',
    'Welcome to My EU Bubble',
    'This is your personalized EU policy intelligence hub. Create amendments, analyses, strategies, and notes to organize your work.',
    ARRAY['EU Institutions'],
    FALSE
FROM users
LIMIT 1;
*/
