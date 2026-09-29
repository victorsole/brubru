-- 253: DG lobby meetings could never be stored, and one bad row took its host's batch
-- with it (29 Sep 2026).
--
-- `host_dg` is VARCHAR(20) and holds a DG ACRONYM: 'GROW', 'CNECT', 'FISMA'. The API
-- reads it that way (`_dg_name()` in api/lobby_meetings.py maps the code to a name via
-- COMMISSION_DG_NAME). The ingest, however, wrote the Transparency Register's link text
-- into it -- 'Information on meetings held by Directorate-General for Trade' -- which is
-- 45 to 121 characters for all 52 DG hosts, measured at the source. Every insert for
-- every DG host therefore raised
--     value too long for type character varying(20)
-- and the table has NOT ONE row with host_role='DG': 16,504 DG meetings were parsed and
-- discarded in a single run. /api/v2/commission/meetings has only ever served cabinet
-- and commissioner meetings.
--
-- Widening host_dg would have been the wrong fix: it would have put acronyms and
-- sentences in one column, splitting each DG into two spellings and breaking the
-- existing acronym filter. So the acronym column keeps its meaning, resolved from the
-- curated map and left NULL when the source's spelling is not in it (37 of 52 resolve
-- exactly; the remaining 15 are services, offices and task forces that are not DGs, plus
-- naming drift that a human should curate rather than a fuzzy match invent), and the
-- department's own name gets a column of its own so nothing the source gives is lost.

ALTER TABLE transparency_meetings
    ADD COLUMN IF NOT EXISTS host_department VARCHAR(255);

COMMENT ON COLUMN transparency_meetings.host_department IS
    'The hosting department as the Transparency Register names it, boilerplate prefix '
    'stripped (e.g. "Directorate-General for Trade"). Read from the source; never derived.';

COMMENT ON COLUMN transparency_meetings.host_dg IS
    'DG acronym (GROW, CNECT, FISMA), resolved against knowledge_base COMMISSION_DG_NAME. '
    'NULL when the host is not a DG or its spelling is not in the map. Never a full name.';

CREATE INDEX IF NOT EXISTS ix_transparency_meetings_host_department
    ON transparency_meetings (host_department);
