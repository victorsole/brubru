"""
Greeting Service

Generates a personalised greeting for the chatbot using the user's profile
and current local time in their timezone. Holidays supported: Christmas,
Season's greetings window, New Year. Time-of-day greetings follow business norms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover - fallback not expected in this project
    ZoneInfo = None  # type: ignore

try:
    from dateutil.easter import easter  # For dynamic Easter calculation
except ImportError:
    easter = None  # type: ignore


@dataclass
class GreetingResult:
    message: str
    metadata: Dict[str, str]


def _get_local_now(user_timezone: Optional[str]) -> datetime:
    """
    Return current datetime in user's timezone. Defaults to Europe/Brussels
    if not provided or invalid.
    """
    default_tz = "Europe/Brussels"
    tz = (user_timezone or default_tz).strip()
    try:
        if ZoneInfo is None:
            # As a conservative fallback, use naive UTC; callers shouldn't rely on this.
            return datetime.utcnow()
        return datetime.now(ZoneInfo(tz))
    except Exception:
        # Invalid timezone input – use default
        return datetime.now(ZoneInfo(default_tz)) if ZoneInfo else datetime.utcnow()


def _special_date_greeting(local_dt: datetime) -> Optional[str]:
    """
    Return a seasonal greeting if today matches a known holiday.

    Rules:
    - 1 January → "Happy New Year"
    - 8 March → "Happy International Women's Day"
    - Easter Week (dynamic) → "Happy Easter"
    - 23 April → "Bon Sant Jordi" (Catalan book & rose day)
    - 9 May → "Happy Europe Day"
    - 5 June → "Happy World Environment Day"
    - 21 September → "Happy International Day of Peace"
    - 31 October → "Happy Halloween"
    - 10 December → "Happy Human Rights Day"
    - 24–26 December → "Season's greetings" (unless 25th)
    - 25 December → "Merry Christmas"
    """
    month = local_dt.month
    day = local_dt.day

    # New Year (1 January)
    if month == 1 and day == 1:
        return "Happy New Year"

    # International Women's Day (8 March)
    if month == 3 and day == 8:
        return "Happy International Women's Day"

    # Easter Week (dynamic calculation)
    if easter:
        easter_date = easter(local_dt.year)
        # Easter Week: from Palm Sunday (7 days before) to Easter Monday (1 day after)
        days_from_easter = (local_dt.date() - easter_date).days
        if -7 <= days_from_easter <= 1:
            return "Happy Easter"

    # Sant Jordi (23 April) - Catalan book and rose day
    if month == 4 and day == 23:
        return "Bon Sant Jordi"

    # Europe Day (9 May)
    if month == 5 and day == 9:
        return "Happy Europe Day"

    # World Environment Day (5 June)
    if month == 6 and day == 5:
        return "Happy World Environment Day"

    # International Day of Peace (21 September)
    if month == 9 and day == 21:
        return "Happy International Day of Peace"

    # Halloween (31 October)
    if month == 10 and day == 31:
        return "Happy Halloween"

    # Human Rights Day (10 December)
    if month == 12 and day == 10:
        return "Happy Human Rights Day"

    # Christmas window
    if month == 12:
        if day == 25:
            return "Merry Christmas"
        if 24 <= day <= 26:
            return "Season's greetings"

    return None


def _time_of_day_greeting(local_dt: datetime) -> str:
    """
    Time-of-day greeting windows:
    - 05:00–11:59 → Good morning
    - 12:00–17:59 → Good afternoon
    - 18:00–22:59 → Good evening
    - 23:00–04:59 → Hello (neutral)
    """
    hour = local_dt.hour
    if 5 <= hour <= 11:
        return "Good morning"
    if 12 <= hour <= 17:
        return "Good afternoon"
    if 18 <= hour <= 22:
        return "Good evening"
    return "Hello"


def _welcome_back_tail(previous_last_login: Optional[datetime], local_now: datetime) -> str:
    """
    Generate a welcome-back phrase based on when the user last logged in.

    Rules:
    - Never logged in before (None) → first-time user welcome
    - Gap > 7 days → enthusiastic welcome back
    - Gap > 3 days → simple welcome back
    - Gap <= 3 days → empty (regular greeting suffices)
    """
    if previous_last_login is None:
        return "Welcome to Brubru! Ask me anything about EU policy."

    # Make comparison timezone-naive if needed
    prev = previous_last_login.replace(tzinfo=None) if previous_last_login.tzinfo else previous_last_login
    now = local_now.replace(tzinfo=None) if local_now.tzinfo else local_now
    gap = now - prev

    if gap > timedelta(days=7):
        return "Great to see you again! A lot has happened in EU policy since your last visit."
    if gap > timedelta(days=3):
        return "Welcome back!"
    return ""


def _resolve_name(first_name: Optional[str], preferred_name: Optional[str], full_name: Optional[str]) -> str:
    if preferred_name and preferred_name.strip():
        return preferred_name.strip()
    if first_name and first_name.strip():
        return first_name.strip()
    # Fallback: derive first token from full_name
    if full_name and full_name.strip():
        return full_name.strip().split()[0]
    return "there"


def generate_personalized_greeting(
    *,
    first_name: Optional[str],
    preferred_name: Optional[str],
    timezone: Optional[str],
    language: Optional[str],
    full_name: Optional[str] = None,
    previous_last_login: Optional[datetime] = None,
) -> GreetingResult:
    """
    Build a personalised greeting string and metadata for the chatbot.

    Args:
        previous_last_login: When the user last logged in (before this session).
            None for first-time users. Used to generate welcome-back messages.

    Returns:
        GreetingResult with `message` (string) and `metadata` for optional LLM use.
    """
    local_now = _get_local_now(timezone)

    # Pick holiday greeting if applicable, else time-of-day
    special = _special_date_greeting(local_now)
    salutation = special or _time_of_day_greeting(local_now)

    name = _resolve_name(first_name, preferred_name, full_name)

    # Tail phrases – friendly and contextual to Brubru's purpose
    if special == "Merry Christmas":
        tail = "If you still feel like thinking about Brussels today, I am here."
    elif special == "Happy New Year":
        tail = "Let's kick off the year with smart EU insights."
    elif special == "Season's greetings":
        tail = "Wishing you a restful season. I'm here if needed."
    elif special == "Happy International Women's Day":
        tail = "Celebrating the achievements of women leaders across Europe!"
    elif special == "Happy Easter":
        tail = "Wishing you a peaceful Easter. Ready to tackle EU policy when you are!"
    elif special == "Bon Sant Jordi":
        tail = "Books and roses! A perfect day for EU legislative reading, no?"
    elif special == "Happy Europe Day":
        tail = "Celebrating European unity, peace, and cooperation. How can I assist you today?"
    elif special == "Happy World Environment Day":
        tail = "Let's explore Europe's green policies and climate action together!"
    elif special == "Happy International Day of Peace":
        tail = "Peace and cooperation – the foundation of the European project. How can I help?"
    elif special == "Happy Halloween":
        tail = "No tricks here, just treats of EU policy insights!"
    elif special == "Happy Human Rights Day":
        tail = "Upholding dignity and rights across Europe. Ready to discuss EU policy?"
    else:
        tail = ""

    # Welcome-back phrase (appended after holiday tail or as standalone tail)
    welcome_back = _welcome_back_tail(previous_last_login, local_now)

    # Build final message
    parts = [f"{salutation}, {name}."]
    if tail:
        parts.append(tail)
    if welcome_back:
        parts.append(welcome_back)
    message = " ".join(parts)

    metadata = {
        "name": name,
        "timezone": (timezone or "Europe/Brussels"),
        "local_time": local_now.replace(microsecond=0).isoformat(),
        "language": (language or "en"),
        "salutation": salutation,
        "is_special_greeting": str(bool(special)).lower(),
        "welcome_back": welcome_back,
    }

    return GreetingResult(message=message, metadata=metadata)

