-- The EP voting tables have been empty since migration 014 (found 24 September 2026).
--
-- Not because the importer is broken, and not because HowTheyVote stopped publishing: the
-- groups import is the FIRST step of `scripts/import_howtheyvote.py`, and it dies on one
-- row. HowTheyVote carries a legacy group whose short_label is its full name --
-- "Confederal Group of the European United Left - Nordic Green Left", 63 characters --
-- against a VARCHAR(20). The insert raises StringDataRightTruncation, the transaction
-- rolls back, and members, group memberships and member votes never run. So
-- ep_members, ep_delegations, ep_group_memberships, ep_political_groups and
-- ep_member_votes all held 0 rows, and the Predictions cohesion analyser, which inner
-- joins ep_member_votes to ep_members, could only ever return None.
--
-- short_label is a display label, not a code: it gets the width of a label. label is
-- widened with it, because the same source row fills both and 100 leaves no headroom
-- for a future group with a long name. `code` stays VARCHAR(20): it is an identifier,
-- and the longest HowTheyVote uses is GUE_NGL_1995_0 at 14.

ALTER TABLE ep_political_groups ALTER COLUMN short_label TYPE VARCHAR(255);
ALTER TABLE ep_political_groups ALTER COLUMN label       TYPE VARCHAR(255);

COMMENT ON COLUMN ep_political_groups.short_label IS
    'Display abbreviation (EPP, S&D, PfE). HowTheyVote repeats the full name here for '
    'legacy groups, so this is label-width, not code-width.';
