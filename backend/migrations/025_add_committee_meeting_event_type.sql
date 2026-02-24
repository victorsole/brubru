-- Migration 025: Add committee_meeting event type
-- Created: February 2026
--
-- Adds 'committee_meeting' to the event_type_enum for individual
-- EP committee meeting events (vs the generic 'committee_week' block).

ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS 'committee_meeting';
