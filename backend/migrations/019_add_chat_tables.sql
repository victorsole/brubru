-- Migration 019: Add persistent chat storage tables
-- Replaces in-memory chat_storage dict with PostgreSQL persistence
-- Chat messages now survive server restarts and Railway deploys

-- Create chats table (conversation metadata)
CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(200),
    description TEXT,
    use_context BOOLEAN DEFAULT TRUE,
    model VARCHAR(100) DEFAULT 'mistral-small-latest',
    temperature INTEGER DEFAULT 7,
    message_count INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    total_cost_usd INTEGER DEFAULT 0,
    collections_searched JSONB,
    sources_used JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    is_starred BOOLEAN DEFAULT FALSE,
    is_shared BOOLEAN DEFAULT FALSE,
    last_message_at TIMESTAMPTZ,
    last_message_preview VARCHAR(500),
    chat_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_created_at ON chats(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chats_user_active ON chats(user_id, is_active) WHERE is_active = TRUE;

-- Create chat_messages table (individual messages)
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    tokens_used INTEGER,
    model VARCHAR(100),
    provider VARCHAR(50),
    citations JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
