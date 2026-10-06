-- 274: mcp_requests, one row per authenticated MCP request (6 Oct 2026).
--
-- Why: on 6 Oct 2026 /users reported "0 tool calls" for a client whose key had
-- been used that morning and whose connector had listed Brubru's tools in 61
-- sessions in 11 days. The only usage record, api_usage_events, is written ONLY
-- after the scope check and the debit succeed, so a refused call, an unknown tool,
-- a bad request, a call to a method we do not serve, and any call that fails before
-- the debit left no trace at all. api_keys.last_used_at is stamped by every
-- authenticated request and cannot say what was asked. This table records every
-- authenticated request and how it ended, so that "no rows" can finally mean
-- "nothing was asked" instead of "nothing was recorded".
--
-- It stores NO arguments and NO query text (user content): only the method, the
-- tool name and the outcome. It is not billing and not WAPU: api_usage_events
-- stays the ledger. Private usage data: service_role only.

CREATE TABLE IF NOT EXISTS public.mcp_requests (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    api_key_id  UUID,                                -- NULL when authentication failed
    user_id     UUID,
    server      TEXT        NOT NULL,                -- 'Brubru', 'Brubru DPP'
    method      TEXT        NOT NULL,                -- 'tools/list', 'tools/call', or the unknown method name (truncated)
    tool        TEXT,                                -- tool name for tools/call, else NULL
    outcome     TEXT        NOT NULL,
    error_code  INTEGER,                             -- JSON-RPC code when the call failed
    auth        TEXT,                                -- 'key' or 'oauth'
    client      TEXT        NOT NULL DEFAULT '',     -- User-Agent, truncated
    is_probe    BOOLEAN     NOT NULL DEFAULT FALSE,  -- X-Brubru-Probe header
    CONSTRAINT mcp_requests_outcome_check CHECK (outcome IN (
        'ok', 'listed', 'auth_invalid', 'key_expired', 'scope_missing',
        'insufficient_balance', 'sandbox_capped', 'unknown_tool', 'bad_arguments',
        'handler_failed', 'method_not_found', 'error'))
);

CREATE INDEX IF NOT EXISTS idx_mcp_requests_key_time ON public.mcp_requests (api_key_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_mcp_requests_time ON public.mcp_requests (created_at DESC, id DESC);

ALTER TABLE public.mcp_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mcp_requests_service_all ON public.mcp_requests;
CREATE POLICY mcp_requests_service_all ON public.mcp_requests
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT ALL ON public.mcp_requests TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.mcp_requests_id_seq TO service_role;
REVOKE ALL ON public.mcp_requests FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.mcp_requests_id_seq FROM anon, authenticated;
