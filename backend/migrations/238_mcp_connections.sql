-- 238: mcp_connections, one row per API key, MCP server, client and day on
-- which a connector listed its tools (23 Sep 2026).
--
-- Why: /users could not tell a client that has Brubru installed but never
-- calls it from a client that is gone. The only trace was
-- api_keys.last_used_at, which (tested 23 Sep) is stamped by ANY authenticated
-- MCP request, including the tool listing a Claude client sends by itself at
-- start-up; keeps only the latest time, throttled to once a minute; and was
-- never stamped for OAuth connections. A tool listing is proof the connector is
-- installed and its client was running that day. It is NOT proof anyone asked
-- Brubru anything, and it is not a core action: WAPU never reads this table.
--
-- Private usage data: service_role only, like api_usage_events.

CREATE TABLE IF NOT EXISTS public.mcp_connections (
    id             BIGSERIAL PRIMARY KEY,
    api_key_id     UUID        NOT NULL,
    user_id        UUID        NOT NULL,
    server         TEXT        NOT NULL,            -- MCP server name, e.g. 'Brubru', 'Brubru DPP'
    client         TEXT        NOT NULL DEFAULT '', -- User-Agent of the listing request, truncated
    auth           TEXT        NOT NULL,            -- 'key' or 'oauth'
    day            DATE        NOT NULL,
    first_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    listings       INTEGER     NOT NULL DEFAULT 1,
    CONSTRAINT mcp_connections_auth_check CHECK (auth IN ('key', 'oauth')),
    CONSTRAINT mcp_connections_one_row_per_day UNIQUE (api_key_id, server, client, day)
);

CREATE INDEX IF NOT EXISTS idx_mcp_connections_user_day ON public.mcp_connections (user_id, day DESC);

ALTER TABLE public.mcp_connections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mcp_connections_service_all ON public.mcp_connections;
CREATE POLICY mcp_connections_service_all ON public.mcp_connections
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT ALL ON public.mcp_connections TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.mcp_connections_id_seq TO service_role;
-- Supabase's default privileges still hand anon and authenticated full table
-- rights on a new public table. RLS already blocks them (no policy), but a
-- private table should not carry the grant at all.
REVOKE ALL ON public.mcp_connections FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.mcp_connections_id_seq FROM anon, authenticated;
