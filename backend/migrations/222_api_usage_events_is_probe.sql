-- 222_api_usage_events_is_probe.sql
-- Mark our own verification traffic on the API surface.
--
-- Why: `api_key_id` cannot separate Brubru's debugging from a client's real use,
-- because the key is theirs. On 13 Aug 2026, 178 MCP calls and 0.89 EUR of our own
-- debugging landed on a client's row and inflated her WAPU. Chat has carried the
-- `X-Brubru-Probe: 1` header and `chats.chat_metadata.is_probe` since 19 Aug; the
-- API surface never got the equivalent, so every `/users` and `/audit-queries`
-- figure still counts our probes as user traffic.
--
-- FALSE is the safe default: an unmarked call is real until proven otherwise, so a
-- caller that forgets the header over-reports usage rather than hiding it.

ALTER TABLE public.api_usage_events
    ADD COLUMN IF NOT EXISTS is_probe boolean NOT NULL DEFAULT false;

-- Partial index: probes are the small minority, and every consumer query filters
-- them OUT (`WHERE NOT is_probe`) or counts them alone. Indexing only the TRUE
-- rows keeps it tiny while still serving "show me the probe traffic" directly.
CREATE INDEX IF NOT EXISTS idx_api_usage_events_is_probe
    ON public.api_usage_events (created_at) WHERE is_probe;

COMMENT ON COLUMN public.api_usage_events.is_probe IS
    'TRUE = Brubru''s own synthetic traffic (deploy verification, debugging), set '
    'from the X-Brubru-Probe request header. Exclude from every user-facing metric. '
    'FALSE is the default and means "not marked", not "proven human".';
