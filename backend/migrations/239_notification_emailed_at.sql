-- 239: notifications.emailed_at (24 Sep 2026)
--
-- Every notification Brubru creates is in-app only: nothing in the pipeline sent
-- email, and 42 status_change notifications to 13 real recipients in the week to
-- 24 Sep were read by nobody. The email channel (services/notifications/
-- notification_email.py) stamps this column when a notification has been sent by
-- email, so it is emailed once and only once. NULL = not emailed.
ALTER TABLE public.notifications
    ADD COLUMN IF NOT EXISTS emailed_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_notifications_unemailed
    ON public.notifications (user_id, created_at)
    WHERE emailed_at IS NULL AND is_read = false;
