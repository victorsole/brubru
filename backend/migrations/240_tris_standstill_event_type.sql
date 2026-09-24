-- 240: event type for TRIS standstill deadlines (24 Sep 2026)
--
-- Victor, 24 Sep 2026: show TRIS standstill deadlines in My EU Calendar. Under
-- Directive (EU) 2015/1535, a Member State notifying a draft technical rule may
-- not adopt it before its standstill period ends; a Commission or Member State
-- detailed opinion extends it. None of the existing event types fits.
ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS 'tris_standstill';
