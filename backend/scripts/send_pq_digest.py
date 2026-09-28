"""Weekly Parliamentary Questions digest: preview it, or create it by hand.

The scheduled run is the notification scheduler (Mondays 07:15 UTC). This script
is for reading what users WOULD get before anything is created:

    python3.12 scripts/send_pq_digest.py --preview ../logs/pq_digest_preview.md
    python3.12 scripts/send_pq_digest.py --preview out.md --allow-stale   # even on a stale feed
    python3.12 scripts/send_pq_digest.py --apply --only victor@hellobo.eu  # create for one user

Creating a notification is in-app only; email follows only when the email channel
is enabled (NOTIFICATION_EMAIL_ENABLED=true).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from core.database import SessionLocal  # noqa: E402
from services.notifications.pq_digest import StaleFeed, feed_newest, run  # noqa: E402


def _md(res, newest) -> str:
    out = [f"# Parliamentary Questions digest, preview", "",
           f"Newest question stored: {newest}. Eligible users: {res.users}; with Policy Interests: "
           f"{res.with_interests}; nothing on their topics: {res.skipped_empty}; already sent this week: "
           f"{res.skipped_recent}; would receive: {len(res.previews)}.", ""]
    for p in res.previews:
        w = p["week"]
        out += [f"## {p['email']} ({p['lang']})", "", f"**{p['title']}**", "", p["message"], ""]
        for q in w["asked"]:
            names = ", ".join(m["name"] for m in q["meps"] if m.get("name"))
            out.append(f"- asked {q['submitted_date']}: {q['subject']} ({names}) {q['source_url'] or ''}")
        for q in w["answered"]:
            out.append(f"- answered {q['answered_date']}: {q['subject']} {q['answer_url'] or q['source_url'] or ''}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="write what each user would get to this Markdown file")
    ap.add_argument("--apply", action="store_true", help="create the in-app notifications")
    ap.add_argument("--only", action="append", default=[], help="restrict to this email (repeatable)")
    ap.add_argument("--allow-stale", action="store_true", help="run even if the question feed is behind")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        newest = feed_newest(db)
        try:
            res = run(db, apply=args.apply, only={e.lower() for e in args.only} or None,
                      allow_stale=args.allow_stale)
        except StaleFeed as exc:
            print(f"[ERROR] {exc}")
            return 1
        print(f"[pq-digest] newest question {newest} | users {res.users} | with interests "
              f"{res.with_interests} | empty {res.skipped_empty} | recent {res.skipped_recent} | "
              f"{'created' if args.apply else 'would create'} {res.created if args.apply else len(res.previews)}")
        if args.preview:
            Path(args.preview).write_text(_md(res, newest), encoding="utf-8")
            print(f"[pq-digest] preview written to {args.preview}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
