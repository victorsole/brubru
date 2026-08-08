/**
 * One name per destination.
 *
 * Buttons that send the user somewhere ("Open My Tracked Files") must take
 * that name from the destination's own navigation label, never from a string
 * written at the call site. Hand-written CTA labels drifted away from the
 * navigation in every language: the sidebar read "Legislative Train: state of
 * play" while the Overview tile offered "Open Legislative Tracker", and "My
 * Tracked Files" was offered as "Open My Files".
 *
 * Usage:
 *   t('common.openNamed', { name: destinationName(t('bubble.tabs.myTrackedFiles')) })
 */

/**
 * The name part of a navigation label. Some labels carry a descriptor after a
 * colon ("Legislative Train: state of play"); that descriptor belongs in the
 * sidebar, not inside a button.
 */
export const destinationName = (label: string): string =>
  label.split(':')[0].trim();
