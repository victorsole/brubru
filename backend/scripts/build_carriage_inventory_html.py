"""Build the PI-organised inventory of all legislative carriages into the (internal)
data-architecture page.

Analyses every carriage one by one, groups them by Brubru Policy Interest (policy_areas[0]),
and writes a browsable HTML inventory (collapsible <details> per PI, a table of procedures
each with status + measured activity from procedure_snapshots) into
frontend/public/data-architecture/index.html between PI-INVENTORY markers (idempotent).
Also refreshes the stale 1,717 headline + the status figure-cards to the live numbers.

No fabrication: a carriage with no policy_areas goes into an honest "Unclassified" bucket,
sub-grouped by its real lead committee (never an invented PI). Activity counts come from the
carriage's own daily snapshot row.

Run:  python3.12 scripts/build_carriage_inventory_html.py
"""
from __future__ import annotations

import html
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logging.disable(logging.INFO)

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal, engine  # noqa: E402
engine.echo = False

PAGE = (Path(__file__).resolve().parent.parent.parent
        / "frontend" / "public" / "data-architecture" / "index.html")

_STATUS_COLOUR = {
    "adopted": "green", "completed": "amber", "close_to_adoption": "green",
    "tabled": "blue", "announced": "purple", "blocked": "red", "withdrawn": "red",
}
_ADVANCED = {"adopted", "completed", "close_to_adoption"}


def _esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _fetch(db):
    """All carriages + their latest daily snapshot activity, one row each."""
    rows = db.execute(text("""
        SELECT c.id, c.oeil_procedure_ref, c.title, c.current_status::text AS status,
               c.policy_areas, c.lead_committee, c.celex_numbers,
               s.num_amendments, s.num_documents, s.num_committee_work,
               s.num_lobby_meetings, s.num_status_changes, s.days_in_current_status
        FROM legislative_carriages c
        LEFT JOIN LATERAL (
            SELECT * FROM procedure_snapshots p
            WHERE p.carriage_id = c.id AND p.snapshot_source = 'daily'
            ORDER BY p.snapshot_date DESC LIMIT 1
        ) s ON true
        ORDER BY c.oeil_procedure_ref NULLS LAST
    """)).mappings().all()
    return rows


def _pi_of(r) -> str:
    pa = r["policy_areas"]
    return pa[0] if pa else "(Unclassified)"


def _carriage_row_html(r) -> str:
    st = (r["status"] or "").lower()
    colour = _STATUS_COLOUR.get(st, "blue")
    ref = _esc(r["oeil_procedure_ref"] or "—")
    title = _esc((r["title"] or "")[:160])
    cmte = _esc(r["lead_committee"] or "")
    celex = _esc((r["celex_numbers"] or [""])[0] if r["celex_numbers"] else "")
    amd = r["num_amendments"] or 0
    ev = r["num_status_changes"] or 0
    stale = r["days_in_current_status"] or 0
    activity = []
    if amd:
        activity.append(f"{amd} amdt")
    if ev:
        activity.append(f"{ev} events")
    if stale:
        activity.append(f"{stale}d idle")
    act = " · ".join(activity) or "—"
    return (
        f'<tr><td><code>{ref}</code></td>'
        f'<td>{title}</td>'
        f'<td><span class="source-tag source-tag--{colour}">{_esc(st or "?")}</span></td>'
        f'<td>{cmte}</td><td>{f"<code>{celex}</code>" if celex else ""}</td>'
        f'<td class="count">{_esc(act)}</td></tr>'
    )


def _group_block(pi: str, items: list, unclassified: bool) -> str:
    advanced = sum(1 for r in items if (r["status"] or "").lower() in _ADVANCED)
    with_amd = sum(1 for r in items if (r["num_amendments"] or 0) > 0)
    summary = (f"{_esc(pi)} &mdash; {len(items)} procedures "
               f"({advanced} advanced, {with_amd} with amendments)")
    # unclassified: order by committee so they are still findable
    if unclassified:
        items = sorted(items, key=lambda r: (r["lead_committee"] or "zzz", r["oeil_procedure_ref"] or ""))
    else:
        items = sorted(items, key=lambda r: (-(r["num_amendments"] or 0), r["oeil_procedure_ref"] or ""))
    rows = "\n".join(_carriage_row_html(r) for r in items)
    return (
        f'<details class="reveal" style="margin:0.5rem 0;border:1px solid var(--color-border,#e5e5e5);border-radius:8px;padding:0.5rem 0.85rem;">'
        f'<summary style="cursor:pointer;font-weight:600;">{summary}</summary>'
        f'<div style="overflow-x:auto;"><table class="data-table" style="margin-top:0.6rem;font-size:0.82rem;">'
        f'<thead><tr><th>Procedure</th><th>Title</th><th>Status</th><th>Lead cmte</th><th>CELEX</th><th>Activity</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div></details>'
    )


def build_inventory_html(db) -> str:
    rows = _fetch(db)
    groups: dict[str, list] = defaultdict(list)
    for r in rows:
        groups[_pi_of(r)].append(r)

    total = len(rows)
    classified = sum(len(v) for k, v in groups.items() if k != "(Unclassified)")
    n_pi = len([k for k in groups if k != "(Unclassified)"])
    advanced = sum(1 for r in rows if (r["status"] or "").lower() in _ADVANCED)

    # PI groups by size desc, unclassified last
    ordered = sorted((k for k in groups if k != "(Unclassified)"),
                     key=lambda k: -len(groups[k]))
    blocks = [_group_block(k, groups[k], unclassified=False) for k in ordered]
    if "(Unclassified)" in groups:
        blocks.append(_group_block("(Unclassified)", groups["(Unclassified)"], unclassified=True))

    intro = (
        f'<div class="subsection reveal"><h3 class="subsection__title">'
        f'All {total:,} procedures, organised by Policy Interest</h3></div>'
        f'<p class="section__intro reveal" style="font-size:0.95rem;">Every tracked legislative '
        f'procedure, grouped by Brubru&rsquo;s Policy Interest classification for findability. '
        f'{classified:,} carry a Policy Interest across {n_pi} categories; '
        f'{total-classified:,} are not yet classified (shown in an honest Unclassified bucket, '
        f'sub-ordered by lead committee &mdash; never an invented label). {advanced:,} are at an '
        f'advanced stage (adopted / completed / close to adoption). Activity counts '
        f'(amendments, procedural events, idle days) come from each procedure&rsquo;s own daily '
        f'snapshot row. Click a group to expand.</p>'
    )
    return ("<!-- PI-INVENTORY-START -->\n" + intro + "\n" + "\n".join(blocks)
            + "\n<!-- PI-INVENTORY-END -->")


def _refresh_headline(src: str, db) -> str:
    counts = dict(db.execute(text(
        "SELECT current_status::text, count(*) FROM legislative_carriages GROUP BY 1")).fetchall())
    total = sum(counts.values())
    # stale 1,717 -> live total
    src = src.replace("all 1,717 legislative files", f"all {total:,} legislative files")
    src = src.replace("legislative_carriages table (1,717 files)",
                      f"legislative_carriages table ({total:,} files)")
    src = src.replace("A few examples from the 1,717 tracked files",
                      f"A few examples from the {total:,} tracked files")
    src = src.replace("These are just 4 out of 1,717 files",
                      f"These are just 4 out of {total:,} files")
    src = src.replace('<td class="count">1,717</td>', f'<td class="count">{total:,}</td>')
    # status figure-cards (data-count="...")
    for status, dc in (("tabled", "486"), ("announced", "477"), ("adopted", "137"),
                       ("completed", "107"), ("close_to_adoption", "67")):
        live = counts.get(status.upper(), counts.get(status, 0))
        src = src.replace(f'data-count="{dc}"', f'data-count="{live}"', 1)
    return src


def main() -> int:
    db = SessionLocal()
    src = PAGE.read_text()
    block = build_inventory_html(db)
    src = _refresh_headline(src, db)

    start, end = "<!-- PI-INVENTORY-START -->", "<!-- PI-INVENTORY-END -->"
    if start in src and end in src:
        pre = src[:src.index(start)]
        post = src[src.index(end) + len(end):]
        src = pre + block + post
        action = "replaced"
    else:
        anchor = "      </tbody>\n    </table>\n  </div>\n\n  <!-- Section 4: Knowledge base -->"
        if anchor not in src:
            print("[ERROR] insertion anchor not found; aborting")
            return 1
        src = src.replace(anchor,
                          "      </tbody>\n    </table>\n    " + block
                          + "\n  </div>\n\n  <!-- Section 4: Knowledge base -->")
        action = "inserted"

    PAGE.write_text(src)
    n = src.count('<tr><td><code>')
    print(f"[OK] inventory {action}; ~{n} carriage rows; page now {len(src):,} bytes")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
