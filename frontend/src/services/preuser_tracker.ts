/**
 * Pre-User Event Tracker
 *
 * Fire-and-forget analytics for pre-user funnel tracking + A/B variant assignment.
 * Variant is deterministic from the last hex digit of the pre_user_id UUID,
 * matching the Python implementation in backend/api/preuser_analytics.py.
 */

const API_BASE_URL =
  import.meta.env?.VITE_API_URL ||
  (window as any).REACT_APP_API_URL ||
  'http://localhost:8000';

/**
 * Deterministic A/B variant from UUID.
 * Matches Python: "B" if int(pre_user_id[-1], 16) % 2 == 1 else "A"
 */
export const getAbVariant = (preUserId: string): 'A' | 'B' => {
  const lastChar = preUserId.charAt(preUserId.length - 1);
  return parseInt(lastChar, 16) % 2 === 1 ? 'B' : 'A';
};

/**
 * Fire-and-forget event tracking. Never throws, never blocks UX.
 */
export const trackPreUserEvent = (
  preUserId: string,
  eventType: string,
  metadata?: Record<string, any>,
): void => {
  fetch(`${API_BASE_URL}/api/analytics/preuser-event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pre_user_id: preUserId,
      event_type: eventType,
      event_metadata: metadata || undefined,
    }),
  }).catch(() => {});
};
