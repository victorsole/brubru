-- Migration 023: Amendment Alignment Scores
-- Phase 4 AI Analysis: cached alignment scores between user policy positions and MEP amendments
-- Created: February 2026

CREATE TABLE IF NOT EXISTS amendment_alignment_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    procedure_reference VARCHAR(50) NOT NULL,
    policy_position_hash VARCHAR(64) NOT NULL,
    mep_amendment_id UUID NOT NULL REFERENCES mep_amendments(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score BETWEEN -2 AND 2),
    explanation TEXT,
    scored_at TIMESTAMPTZ DEFAULT now()
);

-- Fast lookup: user's scores for a procedure + policy position
CREATE INDEX IF NOT EXISTS ix_alignment_user_proc
    ON amendment_alignment_scores(user_id, procedure_reference, policy_position_hash);

-- Prevent duplicate scores for the same user + policy + amendment
CREATE UNIQUE INDEX IF NOT EXISTS uq_alignment_score
    ON amendment_alignment_scores(user_id, policy_position_hash, mep_amendment_id);
