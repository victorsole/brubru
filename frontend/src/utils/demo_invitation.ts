import type { TFunction } from 'i18next';

// The demo invitation replaced the self-serve /subscription page (13 Oct 2026).
// One constant to change if a booking link ever replaces the email.
export const DEMO_EMAIL = 'hello@beresol.eu';

/** mailto: link for the demo request, subject and body in the visitor's language. */
export function demoMailto(t: TFunction): string {
  const subject = encodeURIComponent(t('landing.demo.mailSubject'));
  const body = encodeURIComponent(t('landing.demo.mailBody'));
  return `mailto:${DEMO_EMAIL}?subject=${subject}&body=${body}`;
}

/** English-only variant for pages that carry hard-coded English copy (About, Terms). */
export const DEMO_MAILTO_EN =
  `mailto:${DEMO_EMAIL}?subject=${encodeURIComponent('Brubru - demo request')}`;
