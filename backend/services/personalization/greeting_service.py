"""
Greeting Service

Generates a personalised greeting for the chatbot using the user's profile
and current local time in their timezone. Holidays supported: Christmas,
Season's greetings window, New Year. Time-of-day greetings follow business norms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

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
    policy_hooks: List[Dict[str, str]] = field(default_factory=list)


# Hard cap on hooks shown under the greeting. Two keeps the empty state calm.
MAX_GREETING_HOOKS = 2


def _shorten(text: str, max_len: int = 90) -> str:
    """Trim a label to keep the chip on a single visual line."""
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def compose_hooks_from_briefings(
    briefings: List[Any], max_hooks: int = MAX_GREETING_HOOKS
) -> List[Dict[str, str]]:
    """
    Turn ProactiveBriefing objects (or dicts) into greeting chips.

    Each chip is ``{label, suggested_query, source}``. Order is preserved
    from the input list, which is already prioritised by trigger_engine.
    """
    hooks: List[Dict[str, str]] = []
    for b in briefings or []:
        if len(hooks) >= max_hooks:
            break
        title = getattr(b, "title", None) or (b.get("title") if isinstance(b, dict) else None)
        query = getattr(b, "suggested_query", None) or (
            b.get("suggested_query") if isinstance(b, dict) else None
        )
        source = getattr(b, "trigger_source", None) or (
            b.get("trigger_source") if isinstance(b, dict) else None
        )
        summary = getattr(b, "summary", None) or (
            b.get("summary") if isinstance(b, dict) else None
        )
        if not title or not query:
            continue
        # The spoken line is the summary when available, otherwise the title.
        # The label (short pill text) is always the title.
        hooks.append(
            {
                "label": _shorten(title),
                "spoken": _shorten(str(summary or title), max_len=180),
                "suggested_query": str(query).strip(),
                "source": str(source or "proactive"),
            }
        )
    return hooks


def compose_hooks_from_brief_headlines(
    items: List[Any], max_hooks: int = MAX_GREETING_HOOKS
) -> List[Dict[str, str]]:
    """
    Pre-user fallback. Turn daily_brief rows or dicts into greeting chips.
    """
    hooks: List[Dict[str, str]] = []
    for item in items or []:
        if len(hooks) >= max_hooks:
            break
        headline = getattr(item, "headline", None) or (
            item.get("headline") if isinstance(item, dict) else None
        )
        if not headline:
            continue
        suggested = getattr(item, "suggested_query", None) or (
            item.get("suggested_query") if isinstance(item, dict) else None
        )
        if not suggested:
            suggested = f"Tell me about: {headline}"
        hooks.append(
            {
                "label": _shorten(headline),
                "spoken": _shorten(str(headline), max_len=180),
                "suggested_query": str(suggested).strip(),
                "source": "daily_brief",
            }
        )
    return hooks


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


def _special_date_key(local_dt: datetime) -> Optional[str]:
    """
    Return a seasonal greeting KEY if today matches a known holiday.
    Keys resolve to per-language strings in GREETING_I18N.

    Rules:
    - 1 January → new_year
    - 8 March → womens_day
    - Easter Week (dynamic) → easter
    - 23 April → sant_jordi (Catalan book & rose day)
    - 9 May → europe_day
    - 5 June → environment_day
    - 21 September → peace_day
    - 31 October → halloween
    - 10 December → human_rights_day
    - 24–26 December → seasons (unless 25th)
    - 25 December → christmas
    """
    month = local_dt.month
    day = local_dt.day

    if month == 1 and day == 1:
        return "new_year"
    if month == 3 and day == 8:
        return "womens_day"

    # Easter Week (dynamic calculation)
    if easter:
        easter_date = easter(local_dt.year)
        # Easter Week: from Palm Sunday (7 days before) to Easter Monday (1 day after)
        days_from_easter = (local_dt.date() - easter_date).days
        if -7 <= days_from_easter <= 1:
            return "easter"

    if month == 4 and day == 23:
        return "sant_jordi"
    if month == 5 and day == 9:
        return "europe_day"
    if month == 6 and day == 5:
        return "environment_day"
    if month == 9 and day == 21:
        return "peace_day"
    if month == 10 and day == 31:
        return "halloween"
    if month == 12 and day == 10:
        return "human_rights_day"
    if month == 12:
        if day == 25:
            return "christmas"
        if 24 <= day <= 26:
            return "seasons"

    return None


def _time_of_day_key(local_dt: datetime) -> str:
    """
    Time-of-day greeting windows:
    - 05:00–11:59 → morning
    - 12:00–17:59 → afternoon
    - 18:00–22:59 → evening
    - 23:00–04:59 → hello (neutral)
    """
    hour = local_dt.hour
    if 5 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 17:
        return "afternoon"
    if 18 <= hour <= 22:
        return "evening"
    return "hello"


def _welcome_back_key(previous_last_login: Optional[datetime], local_now: datetime) -> Optional[str]:
    """
    Welcome-back phrase key based on when the user last logged in.

    Rules:
    - Never logged in before (None) → first_time
    - Gap > 7 days → long_gap
    - Gap > 3 days → short_gap
    - Gap <= 3 days → None (regular greeting suffices)
    """
    if previous_last_login is None:
        return "first_time"

    # Make comparison timezone-naive if needed
    prev = previous_last_login.replace(tzinfo=None) if previous_last_login.tzinfo else previous_last_login
    now = local_now.replace(tzinfo=None) if local_now.tzinfo else local_now
    gap = now - prev

    if gap > timedelta(days=7):
        return "long_gap"
    if gap > timedelta(days=3):
        return "short_gap"
    return None


# ---------------------------------------------------------------------------
# Greeting strings in Brubru's 6 languages (EN, ES, CA, FR, IT, NL).
# users.language drives the choice; unknown/missing languages fall back to EN.
# ---------------------------------------------------------------------------

SUPPORTED_GREETING_LANGUAGES = ("en", "es", "ca", "fr", "it", "nl")

GREETING_I18N: Dict[str, Dict[str, Dict[str, str]]] = {
    "en": {
        "tod": {
            "morning": "Good morning",
            "afternoon": "Good afternoon",
            "evening": "Good evening",
            "hello": "Hello",
        },
        "special": {
            "new_year": "Happy New Year",
            "womens_day": "Happy International Women's Day",
            "easter": "Happy Easter",
            "sant_jordi": "Happy Sant Jordi",
            "europe_day": "Happy Europe Day",
            "environment_day": "Happy World Environment Day",
            "peace_day": "Happy International Day of Peace",
            "halloween": "Happy Halloween",
            "human_rights_day": "Happy Human Rights Day",
            "christmas": "Merry Christmas",
            "seasons": "Season's greetings",
        },
        "tail": {
            "new_year": "Let's kick off the year with smart EU insights.",
            "womens_day": "Celebrating the achievements of women leaders across Europe!",
            "easter": "Wishing you a peaceful Easter. Ready to tackle EU policy when you are!",
            "sant_jordi": "Today is the day of books and roses! A perfect day for EU legislative reading, no?",
            "europe_day": "Celebrating European unity, peace, and cooperation. How can I assist you today?",
            "environment_day": "Let's explore Europe's green policies and climate action together!",
            "peace_day": "Peace and cooperation: the foundation of the European project. How can I help?",
            "halloween": "No tricks here, just treats of EU policy insights!",
            "human_rights_day": "Upholding dignity and rights across Europe. Ready to discuss EU policy?",
            "christmas": "If you still feel like thinking about Brussels today, I am here.",
            "seasons": "Wishing you a restful season. I'm here if needed.",
        },
        "welcome": {
            "first_time": "Welcome to Brubru! Ask me anything about EU policy.",
            "long_gap": "Great to see you again! A lot has happened in EU policy since your last visit.",
            "short_gap": "Welcome back!",
        },
    },
    "ca": {
        "tod": {
            "morning": "Bon dia",
            "afternoon": "Bona tarda",
            "evening": "Bon vespre",
            "hello": "Hola",
        },
        "special": {
            "new_year": "Bon any nou",
            "womens_day": "Bon Dia Internacional de les Dones",
            "easter": "Bona Pasqua",
            "sant_jordi": "Bon Sant Jordi",
            "europe_day": "Bon Dia d'Europa",
            "environment_day": "Bon Dia Mundial del Medi Ambient",
            "peace_day": "Bon Dia Internacional de la Pau",
            "halloween": "Bona Castanyada",
            "human_rights_day": "Bon Dia dels Drets Humans",
            "christmas": "Bon Nadal",
            "seasons": "Bones festes",
        },
        "tail": {
            "new_year": "Comencem l'any amb bones anàlisis sobre la UE.",
            "womens_day": "Celebrem els èxits de les dones líders d'arreu d'Europa!",
            "easter": "Et desitjo una Pasqua tranquil·la. A punt per a la política europea quan tu ho estiguis!",
            "sant_jordi": "Avui és el dia dels llibres i les roses! Un dia perfecte per llegir legislació europea, no?",
            "europe_day": "Celebrem la unitat, la pau i la cooperació europees. En què et puc ajudar avui?",
            "environment_day": "Explorem plegats les polítiques verdes i l'acció climàtica d'Europa!",
            "peace_day": "Pau i cooperació: els fonaments del projecte europeu. En què et puc ajudar?",
            "halloween": "Aquí no hi ha ensurts, només llaminadures d'anàlisi europea!",
            "human_rights_day": "Defensem la dignitat i els drets a tot Europa. Parlem de política europea?",
            "christmas": "Si avui encara et ve de gust pensar en Brussel·les, aquí em tens.",
            "seasons": "Et desitjo unes festes tranquil·les. Aquí em tens si em necessites.",
        },
        "welcome": {
            "first_time": "Et donem la benvinguda a Brubru! Pregunta'm el que vulguis sobre política de la UE.",
            "long_gap": "M'alegro de tornar-te a veure! Han passat moltes coses en la política europea des de la teva darrera visita.",
            "short_gap": "Hola de nou!",
        },
    },
    "es": {
        "tod": {
            "morning": "Buenos días",
            "afternoon": "Buenas tardes",
            "evening": "Buenas noches",
            "hello": "Hola",
        },
        "special": {
            "new_year": "Feliz Año Nuevo",
            "womens_day": "Feliz Día Internacional de la Mujer",
            "easter": "Feliz Pascua",
            "sant_jordi": "Feliz Sant Jordi",
            "europe_day": "Feliz Día de Europa",
            "environment_day": "Feliz Día Mundial del Medio Ambiente",
            "peace_day": "Feliz Día Internacional de la Paz",
            "halloween": "Feliz Halloween",
            "human_rights_day": "Feliz Día de los Derechos Humanos",
            "christmas": "Feliz Navidad",
            "seasons": "Felices fiestas",
        },
        "tail": {
            "new_year": "Empecemos el año con buenos análisis sobre la UE.",
            "womens_day": "¡Celebramos los logros de las mujeres líderes de toda Europa!",
            "easter": "Te deseo una Pascua tranquila. ¡Listo para la política europea cuando tú lo estés!",
            "sant_jordi": "¡Hoy es el día de los libros y las rosas! Un día perfecto para leer legislación europea, ¿no?",
            "europe_day": "Celebramos la unidad, la paz y la cooperación europeas. ¿En qué puedo ayudarte hoy?",
            "environment_day": "¡Exploremos juntos las políticas verdes y la acción climática de Europa!",
            "peace_day": "Paz y cooperación: los cimientos del proyecto europeo. ¿En qué puedo ayudarte?",
            "halloween": "¡Aquí no hay sustos, solo golosinas de análisis europeo!",
            "human_rights_day": "Defendemos la dignidad y los derechos en toda Europa. ¿Hablamos de política europea?",
            "christmas": "Si hoy todavía te apetece pensar en Bruselas, aquí me tienes.",
            "seasons": "Te deseo unas fiestas tranquilas. Aquí me tienes si me necesitas.",
        },
        "welcome": {
            "first_time": "¡Te damos la bienvenida a Brubru! Pregúntame lo que quieras sobre política de la UE.",
            "long_gap": "¡Me alegro de verte de nuevo! Han pasado muchas cosas en la política europea desde tu última visita.",
            "short_gap": "¡Hola de nuevo!",
        },
    },
    "fr": {
        "tod": {
            "morning": "Bonjour",
            "afternoon": "Bonjour",
            "evening": "Bonsoir",
            "hello": "Bonjour",
        },
        "special": {
            "new_year": "Bonne année",
            "womens_day": "Bonne Journée internationale des droits des femmes",
            "easter": "Joyeuses Pâques",
            "sant_jordi": "Bonne Sant Jordi",
            "europe_day": "Bonne Journée de l'Europe",
            "environment_day": "Bonne Journée mondiale de l'environnement",
            "peace_day": "Bonne Journée internationale de la paix",
            "halloween": "Joyeux Halloween",
            "human_rights_day": "Bonne Journée des droits de l'homme",
            "christmas": "Joyeux Noël",
            "seasons": "Joyeuses fêtes",
        },
        "tail": {
            "new_year": "Commençons l'année avec de bonnes analyses sur l'UE.",
            "womens_day": "Célébrons les réussites des femmes leaders à travers l'Europe !",
            "easter": "Je vous souhaite de paisibles fêtes de Pâques. Prêt à aborder la politique européenne quand vous l'êtes !",
            "sant_jordi": "Aujourd'hui, c'est le jour des livres et des roses ! Une journée parfaite pour lire de la législation européenne, non ?",
            "europe_day": "Célébrons l'unité, la paix et la coopération européennes. Comment puis-je vous aider aujourd'hui ?",
            "environment_day": "Explorons ensemble les politiques vertes et l'action climatique de l'Europe !",
            "peace_day": "Paix et coopération : les fondements du projet européen. Comment puis-je vous aider ?",
            "halloween": "Pas de mauvais tours ici, seulement des friandises d'analyse européenne !",
            "human_rights_day": "Défendons la dignité et les droits partout en Europe. Prêt à parler de politique européenne ?",
            "christmas": "Si vous avez encore envie de penser à Bruxelles aujourd'hui, je suis là.",
            "seasons": "Je vous souhaite des fêtes reposantes. Je suis là si besoin.",
        },
        "welcome": {
            "first_time": "Bienvenue sur Brubru ! Posez-moi toutes vos questions sur la politique européenne.",
            "long_gap": "Ravi de vous revoir ! Il s'est passé beaucoup de choses dans la politique européenne depuis votre dernière visite.",
            "short_gap": "Bon retour !",
        },
    },
    "it": {
        "tod": {
            "morning": "Buongiorno",
            "afternoon": "Buon pomeriggio",
            "evening": "Buonasera",
            "hello": "Salve",
        },
        "special": {
            "new_year": "Buon anno",
            "womens_day": "Buona Giornata internazionale della donna",
            "easter": "Buona Pasqua",
            "sant_jordi": "Buon Sant Jordi",
            "europe_day": "Buona Giornata dell'Europa",
            "environment_day": "Buona Giornata mondiale dell'ambiente",
            "peace_day": "Buona Giornata internazionale della pace",
            "halloween": "Buon Halloween",
            "human_rights_day": "Buona Giornata dei diritti umani",
            "christmas": "Buon Natale",
            "seasons": "Buone feste",
        },
        "tail": {
            "new_year": "Iniziamo l'anno con buone analisi sull'UE.",
            "womens_day": "Celebriamo i successi delle donne leader in tutta Europa!",
            "easter": "Ti auguro una Pasqua serena. Pronto per la politica europea quando lo sei tu!",
            "sant_jordi": "Oggi è il giorno dei libri e delle rose! Una giornata perfetta per leggere la legislazione europea, no?",
            "europe_day": "Celebriamo l'unità, la pace e la cooperazione europee. Come posso aiutarti oggi?",
            "environment_day": "Esploriamo insieme le politiche verdi e l'azione per il clima dell'Europa!",
            "peace_day": "Pace e cooperazione: le fondamenta del progetto europeo. Come posso aiutarti?",
            "halloween": "Niente scherzetti qui, solo dolcetti di analisi europea!",
            "human_rights_day": "Difendiamo la dignità e i diritti in tutta Europa. Parliamo di politica europea?",
            "christmas": "Se oggi hai ancora voglia di pensare a Bruxelles, sono qui.",
            "seasons": "Ti auguro feste serene. Sono qui se serve.",
        },
        "welcome": {
            "first_time": "Ti diamo il benvenuto su Brubru! Chiedimi qualsiasi cosa sulla politica dell'UE.",
            "long_gap": "Che bello rivederti! Sono successe molte cose nella politica europea dalla tua ultima visita.",
            "short_gap": "Che piacere rivederti!",
        },
    },
    "nl": {
        "tod": {
            "morning": "Goedemorgen",
            "afternoon": "Goedemiddag",
            "evening": "Goedenavond",
            "hello": "Hallo",
        },
        "special": {
            "new_year": "Gelukkig Nieuwjaar",
            "womens_day": "Fijne Internationale Vrouwendag",
            "easter": "Vrolijk Pasen",
            "sant_jordi": "Fijne Sant Jordi",
            "europe_day": "Fijne Dag van Europa",
            "environment_day": "Fijne Wereldmilieudag",
            "peace_day": "Fijne Internationale Dag van de Vrede",
            "halloween": "Fijne Halloween",
            "human_rights_day": "Fijne Dag van de Mensenrechten",
            "christmas": "Vrolijk kerstfeest",
            "seasons": "Fijne feestdagen",
        },
        "tail": {
            "new_year": "Laten we het jaar beginnen met scherpe EU-inzichten.",
            "womens_day": "We vieren de prestaties van vrouwelijke leiders in heel Europa!",
            "easter": "Ik wens je een vredig Pasen. Klaar voor EU-beleid wanneer jij dat bent!",
            "sant_jordi": "Vandaag is de dag van boeken en rozen! Een perfecte dag om EU-wetgeving te lezen, toch?",
            "europe_day": "We vieren Europese eenheid, vrede en samenwerking. Hoe kan ik je vandaag helpen?",
            "environment_day": "Laten we samen het groene beleid en de klimaatactie van Europa verkennen!",
            "peace_day": "Vrede en samenwerking: het fundament van het Europese project. Hoe kan ik helpen?",
            "halloween": "Geen trucjes hier, alleen traktaties vol EU-inzichten!",
            "human_rights_day": "We staan voor waardigheid en rechten in heel Europa. Klaar om over EU-beleid te praten?",
            "christmas": "Als je vandaag toch nog aan Brussel wilt denken, ben ik er.",
            "seasons": "Ik wens je rustige feestdagen. Ik ben er als het nodig is.",
        },
        "welcome": {
            "first_time": "Welkom bij Brubru! Vraag me alles over EU-beleid.",
            "long_gap": "Fijn je weer te zien! Er is veel gebeurd in het EU-beleid sinds je laatste bezoek.",
            "short_gap": "Welkom terug!",
        },
    },
}


def resolve_greeting_language(language: Optional[str]) -> str:
    """Normalise a users.language value to a supported greeting language."""
    code = (language or "en").strip().lower()[:2]
    return code if code in SUPPORTED_GREETING_LANGUAGES else "en"


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
    lang = resolve_greeting_language(language)
    strings = GREETING_I18N[lang]

    # Pick holiday greeting if applicable, else time-of-day
    special_key = _special_date_key(local_now)
    if special_key:
        salutation = strings["special"][special_key]
        tail = strings["tail"].get(special_key, "")
    else:
        salutation = strings["tod"][_time_of_day_key(local_now)]
        tail = ""

    name = _resolve_name(first_name, preferred_name, full_name)

    # Welcome-back phrase (appended after holiday tail or as standalone tail)
    welcome_key = _welcome_back_key(previous_last_login, local_now)
    welcome_back = strings["welcome"][welcome_key] if welcome_key else ""

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
        "language": lang,
        "salutation": salutation,
        "is_special_greeting": str(bool(special_key)).lower(),
        "welcome_back": welcome_back,
    }

    return GreetingResult(message=message, metadata=metadata)

