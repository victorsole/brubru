-- 106_commissioner_meeting_event_type.sql
-- New calendar event type for individual Commissioner agenda items (their
-- scheduled meetings), fed from commissioner_agenda_client into My EU Calendar
-- and PI-filtered by commission_dg. Complements commission_college_meeting.
--
-- Created: 2 June 2026 (MEUB Section 3 — College + Commissioner agendas in Calendar).

ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS 'commissioner_meeting';
