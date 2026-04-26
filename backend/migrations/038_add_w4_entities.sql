-- 038 — W4 P2 entity tables: parliamentary_questions, transparency_meetings,
-- rsb_opinions, secondary_acts (delegated + implementing), tris_notifications.
-- Created: 25 April 2026 (GovClipping API roadmap, week 4).

-- ENUMS
DO $$ BEGIN
    CREATE TYPE question_type_enum AS ENUM ('written', 'oral', 'priority', 'question_time');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE rsb_verdict_enum AS ENUM ('positive', 'positive_with_reservations', 'negative', 'unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE secondary_act_type_enum AS ENUM ('delegated', 'implementing');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE secondary_act_status_enum AS ENUM ('draft', 'adopted', 'objected', 'rejected', 'published', 'unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- 1.15 EP Parliamentary Questions
CREATE TABLE IF NOT EXISTS parliamentary_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_reference VARCHAR(50) UNIQUE NOT NULL,
    question_type question_type_enum NOT NULL DEFAULT 'written',
    parliamentary_term INTEGER NOT NULL DEFAULT 10,

    subject TEXT NOT NULL,
    text_question TEXT,
    text_answer TEXT,

    submitted_date DATE,
    answered_date DATE,

    asking_mep_ids TEXT[] DEFAULT '{}',
    asking_mep_names TEXT[] DEFAULT '{}',
    answering_institution VARCHAR(50),
    answering_commissioner VARCHAR(255),

    committees TEXT[] DEFAULT '{}',
    procedure_ref VARCHAR(50),
    related_celex TEXT[] DEFAULT '{}',
    policy_areas TEXT[] DEFAULT '{}',

    source_url TEXT,
    answer_url TEXT,

    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_parl_q_submitted ON parliamentary_questions(submitted_date);
CREATE INDEX IF NOT EXISTS ix_parl_q_term ON parliamentary_questions(parliamentary_term);
CREATE INDEX IF NOT EXISTS ix_parl_q_question_reference ON parliamentary_questions(question_reference);

ALTER TABLE parliamentary_questions ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_read_parliamentary_questions ON parliamentary_questions FOR SELECT USING (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- 1.8 Commission Transparency Initiative meetings
CREATE TABLE IF NOT EXISTS transparency_meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_uuid VARCHAR(64) NOT NULL,
    host_name VARCHAR(255),
    host_role VARCHAR(255),
    host_dg VARCHAR(20),
    host_cabinet VARCHAR(100),

    meeting_date DATE NOT NULL,
    location VARCHAR(255),
    subject TEXT NOT NULL,

    organisation_met VARCHAR(500) NOT NULL,
    transparency_register_id VARCHAR(50),
    organisation_type VARCHAR(50),
    representatives TEXT,

    source_url TEXT NOT NULL,

    policy_areas TEXT[] DEFAULT '{}',
    related_celex TEXT[] DEFAULT '{}',

    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_tr_meet_host_uuid ON transparency_meetings(host_uuid);
CREATE INDEX IF NOT EXISTS ix_tr_meet_org ON transparency_meetings(organisation_met);
CREATE INDEX IF NOT EXISTS ix_tr_meet_date ON transparency_meetings(meeting_date);
CREATE INDEX IF NOT EXISTS ix_tr_meet_dg ON transparency_meetings(host_dg);
CREATE INDEX IF NOT EXISTS ix_tr_meet_register_id ON transparency_meetings(transparency_register_id);

ALTER TABLE transparency_meetings ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_read_transparency_meetings ON transparency_meetings FOR SELECT USING (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- 1.10 Regulatory Scrutiny Board opinions
CREATE TABLE IF NOT EXISTS rsb_opinions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opinion_reference VARCHAR(100) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    target_initiative VARCHAR(255),
    target_dg VARCHAR(20),
    procedure_ref VARCHAR(50),

    opinion_type VARCHAR(50) NOT NULL DEFAULT 'impact_assessment',
    verdict rsb_verdict_enum NOT NULL DEFAULT 'unknown',
    opinion_date DATE NOT NULL,

    summary TEXT,
    full_text TEXT,
    pdf_url TEXT,
    source_url TEXT NOT NULL,

    policy_areas TEXT[] DEFAULT '{}',

    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_rsb_opinion_date ON rsb_opinions(opinion_date);
CREATE INDEX IF NOT EXISTS ix_rsb_target_dg ON rsb_opinions(target_dg);
CREATE INDEX IF NOT EXISTS ix_rsb_procedure_ref ON rsb_opinions(procedure_ref);

ALTER TABLE rsb_opinions ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_read_rsb_opinions ON rsb_opinions FOR SELECT USING (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- B.4 Delegated + implementing acts
CREATE TABLE IF NOT EXISTS secondary_acts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    act_type secondary_act_type_enum NOT NULL,
    reference VARCHAR(100) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,

    parent_celex VARCHAR(30),
    parent_procedure_ref VARCHAR(50),
    status secondary_act_status_enum NOT NULL DEFAULT 'unknown',

    proposing_dg VARCHAR(20),
    publication_date DATE,
    objection_deadline DATE,
    ep_scrutiny JSONB DEFAULT '{}'::jsonb,
    council_scrutiny JSONB DEFAULT '{}'::jsonb,

    celex VARCHAR(30),
    source_url TEXT NOT NULL,
    pdf_url TEXT,

    policy_areas TEXT[] DEFAULT '{}',

    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_sa_act_type ON secondary_acts(act_type);
CREATE INDEX IF NOT EXISTS ix_sa_parent_celex ON secondary_acts(parent_celex);
CREATE INDEX IF NOT EXISTS ix_sa_publication_date ON secondary_acts(publication_date);
CREATE INDEX IF NOT EXISTS ix_sa_proposing_dg ON secondary_acts(proposing_dg);

ALTER TABLE secondary_acts ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_read_secondary_acts ON secondary_acts FOR SELECT USING (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- B.6 TRIS notifications
CREATE TABLE IF NOT EXISTS tris_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_number VARCHAR(50) UNIQUE NOT NULL,
    notifying_country VARCHAR(3) NOT NULL,
    title TEXT NOT NULL,
    short_summary TEXT,
    full_text_summary TEXT,

    notification_date DATE NOT NULL,
    standstill_until DATE,

    sector VARCHAR(255),
    products_or_services TEXT,
    main_content TEXT,

    commission_observations_url TEXT,
    member_state_observations JSONB DEFAULT '[]'::jsonb,
    detailed_opinions JSONB DEFAULT '[]'::jsonb,

    source_url TEXT NOT NULL,
    pdf_url TEXT,

    policy_areas TEXT[] DEFAULT '{}',
    related_celex TEXT[] DEFAULT '{}',

    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_tris_country ON tris_notifications(notifying_country);
CREATE INDEX IF NOT EXISTS ix_tris_date ON tris_notifications(notification_date);
CREATE INDEX IF NOT EXISTS ix_tris_sector ON tris_notifications(sector);

ALTER TABLE tris_notifications ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_read_tris_notifications ON tris_notifications FOR SELECT USING (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
