-- Migration 054: Comparator feature
--
-- The Comparator is a top-level Brubru feature (peer of Amendator + Tenderator)
-- that lets users build a spreadsheet-style grid across legislative files.
-- Rows = files (CELEX or OEIL refs). Columns = aspects (rapporteur, status,
-- amendments_deadline, etc.). Each cell carries a verifiable citation.
--
-- Two tables:
--   1. comparator_grids       — top-level grid metadata owned by a user
--   2. comparator_cells       — extracted (file_ref, column_key) -> value+citation
--
-- Tier limits enforced in api/comparator.py (not in SQL):
--   white  (free trial): 1 grid, 3 rows × 3 cols
--   yellow (advocate):   3 grids, 5 rows × 6 cols
--   blue   (professional, admin): unlimited grids, 10 rows × 6 cols
--
-- All access is user-scoped via RLS (auth.uid()).

BEGIN;

-- 1. Grids
CREATE TABLE IF NOT EXISTS comparator_grids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    file_refs JSONB NOT NULL DEFAULT '[]'::jsonb,   -- ["32024R1689", "2024/0079(COD)", ...]
    columns JSONB NOT NULL DEFAULT '[]'::jsonb,     -- [{"key":"rapporteur","label":"Rapporteur"}, ...]
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comparator_grids_user
    ON comparator_grids(user_id, updated_at DESC);

ALTER TABLE comparator_grids ENABLE ROW LEVEL SECURITY;

CREATE POLICY comparator_grids_owner_select
    ON comparator_grids FOR SELECT USING (user_id = auth.uid());

CREATE POLICY comparator_grids_owner_insert
    ON comparator_grids FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY comparator_grids_owner_update
    ON comparator_grids FOR UPDATE USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY comparator_grids_owner_delete
    ON comparator_grids FOR DELETE USING (user_id = auth.uid());

-- 2. Cells
CREATE TABLE IF NOT EXISTS comparator_cells (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grid_id UUID NOT NULL REFERENCES comparator_grids(id) ON DELETE CASCADE,
    file_ref TEXT NOT NULL,
    column_key TEXT NOT NULL,
    value_text TEXT,
    citation JSONB,                                  -- {"celex":"32024R1689","article":"53","verbatim":"...","url":"..."}
    computation_status TEXT NOT NULL DEFAULT 'pending',  -- pending | computed | failed | stale
    computation_error TEXT,
    computed_at TIMESTAMPTZ,
    UNIQUE (grid_id, file_ref, column_key)
);

CREATE INDEX IF NOT EXISTS idx_comparator_cells_grid
    ON comparator_cells(grid_id);
CREATE INDEX IF NOT EXISTS idx_comparator_cells_status
    ON comparator_cells(grid_id, computation_status);

ALTER TABLE comparator_cells ENABLE ROW LEVEL SECURITY;

-- Cells inherit ownership through their grid. The policy joins back to grids.
CREATE POLICY comparator_cells_owner_select
    ON comparator_cells FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM comparator_grids g
            WHERE g.id = comparator_cells.grid_id AND g.user_id = auth.uid()
        )
    );

CREATE POLICY comparator_cells_owner_insert
    ON comparator_cells FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM comparator_grids g
            WHERE g.id = comparator_cells.grid_id AND g.user_id = auth.uid()
        )
    );

CREATE POLICY comparator_cells_owner_update
    ON comparator_cells FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM comparator_grids g
            WHERE g.id = comparator_cells.grid_id AND g.user_id = auth.uid()
        )
    );

CREATE POLICY comparator_cells_owner_delete
    ON comparator_cells FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM comparator_grids g
            WHERE g.id = comparator_cells.grid_id AND g.user_id = auth.uid()
        )
    );

-- 3. updated_at trigger on grids
CREATE OR REPLACE FUNCTION comparator_grids_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_comparator_grids_updated_at ON comparator_grids;
CREATE TRIGGER trg_comparator_grids_updated_at
    BEFORE UPDATE ON comparator_grids
    FOR EACH ROW
    EXECUTE FUNCTION comparator_grids_set_updated_at();

COMMIT;

-- Down migration:
-- BEGIN;
-- DROP TRIGGER IF EXISTS trg_comparator_grids_updated_at ON comparator_grids;
-- DROP FUNCTION IF EXISTS comparator_grids_set_updated_at();
-- DROP TABLE IF EXISTS comparator_cells;
-- DROP TABLE IF EXISTS comparator_grids;
-- COMMIT;
