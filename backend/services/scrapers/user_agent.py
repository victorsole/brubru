"""One place to say who we are.

WHY THIS EXISTS (26 August 2026). The `/news` scrape reported
`[ERROR] Publications Office: Client error '403 Forbidden'` for
`https://op.europa.eu/en/home`, and the cause was not the site tightening up. It
was us: the scraper announced itself as **Chrome/124**, a build from April 2024.
Measured that morning against the live host:

    no User-Agent at all                    -> 200
    curl default                            -> 200
    python-httpx/0.27                       -> 200
    BrubruBot/1.0                           -> 200
    Firefox/127                             -> 200
    Safari/17.4                             -> 200
    Chrome/124  (what we were sending)      -> 403
    Edg/124                                 -> 403
    Chrome/133 and above                    -> 200

So the rule is a **minimum browser version**, a standard bot heuristic: nobody
browses on a two-year-old Chrome, so a request claiming to is treated as a bot.
Note what this means -- an HONEST bot UA sails through, and only the *stale
disguise* is punished. Pretending to be a browser is the thing that broke.

At the time of writing the codebase held **106 hardcoded Chrome versions across
96 files** (71x Chrome/124, 19x Chrome/120, 15x Chrome/126, 1x Chrome/121), each
of which becomes a 403 the day any host adds the same rule. Publications Office
was simply the first to fire. That is why this is a shared constant with a test
floor rather than a one-line fix in one scraper.

RULES
- Prefer `BOT_UA` for any EU host that does not require a browser UA. It is
  honest, it identifies us, it gives operators someone to contact, and it does
  not rot.
- Use `BROWSER_UA` only where a host genuinely refuses non-browser clients.
- Never hardcode a Chrome version anywhere else. `tests/test_user_agent_freshness.py`
  fails the build when a hardcoded version drops below `MIN_SUPPORTED_CHROME`.
- When bumping, set it to a real, current Chrome major version and say where the
  number came from. This one was read off the local install
  (`Google Chrome 151.0.7922.174`) on 26 August 2026, not guessed.
"""
from __future__ import annotations

# The lowest Chrome major version the freshness test will tolerate anywhere in
# the codebase. Chrome/124 was rejected by op.europa.eu; Chrome/133 was the
# lowest version verified to pass it. The floor sits above that with headroom,
# so the test fires while there is still time to act rather than after a 403.
MIN_SUPPORTED_CHROME = 140

# Verified current on 26 August 2026 (local install: 151.0.7922.174).
CHROME_MAJOR = 151

BROWSER_UA = (
    f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) Chrome/{CHROME_MAJOR}.0.0.0 Safari/537.36"
)

# The honest option, and the better default. Measured above: it is not blocked.
BOT_UA = "BrubruBot/1.0 (+https://brubru.beresol.eu; hello@beresol.eu)"

__all__ = ["BROWSER_UA", "BOT_UA", "CHROME_MAJOR", "MIN_SUPPORTED_CHROME"]
