"""
Stakeholder Mapping graph builder (MEUB Section 4 - Strategy).

Builds a PI-aware actor graph around either a single tracked file (file mode) or
the user's whole tracked portfolio (PI-overview, the default). Node types:
file, committee, mep, dg, official, council_config, org. Every edge carries a
``source_kind`` so the UI can keep the evidence-vs-inference distinction.

Sources (all already in Brubru):
- LegislativeCarriage / UserCarriageTrack  -> file, committees, rapporteur, tracked set
- mep_lobby_meetings                       -> MEPs met + organisations that lobbied (evidence)
- consultation_feedback (Outcome Alignment)-> org stance (matched by TR id / org name)
- PI crosswalk                             -> lead DG + Council configuration (inference)
- eu_transparency_register                 -> org enrichment + Brussels-HQ ecosystem
- EU Who-is-Who org pages                  -> named officials behind the lead DG

No Anthropic. Read-only. Caps node counts so the graph stays legible.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from knowledge_base.eu_calendar_institutions import (
    COMMISSION_DG_NAME, COUNCIL_CONFIGURATIONS, EP_COMMITTEES,
)
from services.tracking.pi_committee_crosswalk import (
    PI_TO_COMMITTEES, PI_TO_DGS, PI_TO_COUNCIL_CONFIGS, keywords_for_interests,
)

logger = logging.getLogger(__name__)

_MEP_URL = "https://www.europarl.europa.eu/meps/en/{id}"
_WIW_URL = "https://op.europa.eu/en/web/who-is-who/organization/-/organization/{dg}/{dg}"
_TR_URL = "https://ec.europa.eu/transparencyregister/public/consultation/displaylobbyist.do?id={id}"

_TRADE = "Trade and business associations"
_NGO = "Non-governmental organisations, platforms and networks and similar"

_KB = Path(__file__).resolve().parents[2] / "knowledge_base"
_WIW_PATH = _KB / "whoiswho_officials.json"          # top-5 per DG (Web/Map graph)
_ORG_PATH = _KB / "whoiswho_org.json"                # full DG->dir->unit->head tree (Cards)
_wiw_officials: Optional[dict] = None
_org_data: Optional[dict] = None


def _officials_for(dg: str) -> List[dict]:
    """Named senior officials for a DG (from the ingested Who-is-Who PDF). [] if none."""
    global _wiw_officials
    if _wiw_officials is None:
        try:
            _wiw_officials = (json.loads(_WIW_PATH.read_text(encoding="utf-8")) or {}).get("officials", {})
        except Exception:
            _wiw_officials = {}
    return _wiw_officials.get(dg, [])


def _org() -> dict:
    global _org_data
    if _org_data is None:
        try:
            _org_data = (json.loads(_ORG_PATH.read_text(encoding="utf-8")) or {}).get("dgs", {})
        except Exception:
            _org_data = {}
    return _org_data


def dg_contacts(dg: str, keywords: List[str]) -> Optional[dict]:
    """Full Department -> Directorate -> Unit -> Head-of-Unit (+ email) tree for a DG,
    with the directorates/units whose remit matches the file's keywords flagged and
    sorted first (who to contact). All data is verbatim from the Who-is-Who PDF."""
    data = _org().get(dg)
    if not data:
        return None
    kws = [k.lower() for k in keywords if k]

    def rel(text: Optional[str]) -> bool:
        t = (text or "").lower()
        return any(k in t for k in kws)

    dirs = []
    for D in data.get("directorates", []):
        units = [{"code": u["code"], "name": u["name"], "head": u.get("head"),
                  "relevant": rel(u["name"]) or rel(D["name"])} for u in D.get("units", [])]
        units.sort(key=lambda u: (not u["relevant"], u["code"]))
        dirs.append({"code": D["code"], "name": D["name"], "director": D.get("director"),
                     "relevant": rel(D["name"]) or any(u["relevant"] for u in units), "units": units})
    dirs.sort(key=lambda D: (not D["relevant"], D["code"]))
    return {
        "dg": dg, "dg_name": COMMISSION_DG_NAME.get(dg, dg),
        "url": _WIW_URL.format(dg=dg),
        "director_general": data.get("director_general"),
        "deputies": data.get("deputies", []),
        "directorates": dirs,
        "relevant_count": sum(1 for D in dirs for u in D["units"] if u["relevant"]),
    }


# --------------------------------------------------------------------- graph
class _Graph:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.edges: List[dict] = []
        self._seen_edges = set()

    def node(self, nid: str, **kw) -> dict:
        if nid in self.nodes:
            n = self.nodes[nid]
            n["relevance"] = min(1.0, n.get("relevance", 0) + kw.get("relevance", 0.0))
            if kw.get("pi_match"):
                n["pi_match"] = True
            return n
        kw["id"] = nid
        kw.setdefault("relevance", 0.5)
        self.nodes[nid] = kw
        return kw

    def edge(self, source: str, target: str, rel: str, source_kind: str, weight: float = 1.0):
        key = (source, target, rel)
        if key in self._seen_edges or source == target:
            return
        if source not in self.nodes or target not in self.nodes:
            return
        self._seen_edges.add(key)
        self.edges.append({"source": source, "target": target, "rel": rel,
                           "source_kind": source_kind, "weight": weight})

    def payload(self, mode: str, focus: dict, pi_active: bool, sources_used: List[str]) -> dict:
        for n in self.nodes.values():
            n["relevance"] = round(min(1.0, n["relevance"]), 3)
        return {
            "mode": mode, "focus": focus, "pi_active": pi_active,
            "nodes": list(self.nodes.values()), "edges": self.edges,
            "counts": dict(Counter(n["type"] for n in self.nodes.values())),
            "sources_used": sources_used,
        }


# --------------------------------------------------------------------- helpers
def _domains_for_committee(code: Optional[str]) -> List[str]:
    if not code:
        return []
    return [d for d, coms in PI_TO_COMMITTEES.items() if code in coms]


def _dedup_list(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def _tr_records(db: Session, ids: List[str]) -> Dict[str, dict]:
    ids = [i for i in _dedup_list(ids) if i]
    if not ids:
        return {}
    rows = db.execute(text(
        "SELECT identification_code, original_name, acronym, website_url, public_url, "
        "registration_category, head_office_city, head_office_country, eu_office_city "
        "FROM eu_transparency_register WHERE identification_code = ANY(:ids)"
    ), {"ids": ids}).fetchall()
    out = {}
    for r in rows:
        city = r.head_office_city or r.eu_office_city
        out[r.identification_code] = {
            "tr_number": r.identification_code, "name": r.original_name, "acronym": r.acronym,
            "website": r.website_url, "register_url": r.public_url,
            "category": r.registration_category, "hq_city": city, "hq_country": r.head_office_country,
            "is_brussels": bool(city and re.search(r"brussel|bruxelles", city, re.I)),
        }
    return out


def _stance_by_org(db: Session, tr_ids: List[str], names: List[str]) -> Dict[str, dict]:
    """Latest consultation stance (Outcome Alignment) keyed by tr_id and org_norm."""
    out: Dict[str, dict] = {}
    try:
        from models.consultation_feedback import ConsultationFeedback as CF
        q = db.query(CF).filter(CF.stance.isnot(None))
        ids = [i for i in _dedup_list(tr_ids) if i]
        norms = [n for n in _dedup_list(names) if n]
        rows = []
        if ids:
            rows += q.filter(CF.transparency_register_id.in_(ids)).all()
        if norms:
            rows += q.filter(CF.organisation_norm.in_(norms)).all()
        for f in rows:
            if f.stance in (None, "attachment_only", "unclear"):
                continue
            rec = {"stance": f.stance, "summary": f.stance_summary, "excerpt": f.feedback_excerpt}
            if f.transparency_register_id:
                out.setdefault(f"tr:{f.transparency_register_id}", rec)
            if f.organisation_norm:
                out.setdefault(f"nm:{f.organisation_norm}", rec)
    except Exception as e:
        logger.warning("[stakeholders] stance lookup failed: %s", e)
    return out


# --------------------------------------------------------------------- file graph
def build_file_graph(db: Session, carriage, pi_domains: List[str], *, deep: bool = True) -> _Graph:
    g = _Graph()
    pi_committees = {c for d in pi_domains for c in PI_TO_COMMITTEES.get(d, [])}
    proc = carriage.oeil_procedure_ref
    fid = f"file:{proc or carriage.id}"
    g.node(fid, type="file", institution="file", label=carriage.title or proc or "File",
           sublabel=proc, relevance=1.0,
           url=(f"https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={proc}" if proc else None),
           meta={"status": getattr(carriage.current_status, "value", None),
                 "celex": (carriage.celex_numbers or [None])[0]})

    # committees
    for code, rel in [(carriage.lead_committee, "lead_committee")] + \
                     [(c, "opinion_committee") for c in (carriage.opinion_committees or [])]:
        if not code:
            continue
        cid = f"committee:{code}"
        g.node(cid, type="committee", institution="ep", label=code,
               sublabel=EP_COMMITTEES.get(code, "EP committee"),
               relevance=0.85 if rel == "lead_committee" else 0.55,
               pi_match=code in pi_committees, url=None, meta={})
        g.edge(cid, fid, rel, "oeil")

    # rapporteur (carriage) + shadows (oeil_procedure_data, best-effort)
    opd = carriage.oeil_procedure_data if isinstance(carriage.oeil_procedure_data, dict) else {}
    rapp_name = opd.get("rapporteur") or opd.get("rapporteur_name")
    if carriage.rapporteur_mep_id:
        mid = f"mep:{carriage.rapporteur_mep_id}"
        g.node(mid, type="mep", institution="ep", label=rapp_name or f"MEP {carriage.rapporteur_mep_id}",
               sublabel="Rapporteur", relevance=0.9, url=_MEP_URL.format(id=carriage.rapporteur_mep_id),
               meta={"role": "rapporteur"})
        g.edge(mid, fid, "rapporteur_of", "oeil")
    for sh in (opd.get("shadows") or opd.get("shadow_rapporteurs") or [])[:6]:
        sid = sh.get("id") or sh.get("mep_id") if isinstance(sh, dict) else None
        sname = (sh.get("name") if isinstance(sh, dict) else str(sh)) or (f"MEP {sid}" if sid else None)
        if not sname:
            continue
        nid = f"mep:{sid}" if sid else f"mep:{sname}"
        g.node(nid, type="mep", institution="ep", label=sname, sublabel="Shadow rapporteur",
               relevance=0.6, url=(_MEP_URL.format(id=sid) if sid else None), meta={"role": "shadow"})
        g.edge(nid, fid, "shadow_of", "oeil")

    # lobby meetings (evidence): MEPs met + organisations that lobbied this dossier
    org_ids, org_names = [], []
    lobby = []
    if proc:
        lobby = db.execute(text(
            "SELECT mep_id, mep_name, role, committee, organisation, organisation_norm, "
            "transparency_register_id, org_website, org_register_url "
            "FROM mep_lobby_meetings WHERE procedure_ref = :p LIMIT 400"
        ), {"p": proc}).fetchall()
    org_meet = Counter()
    org_seen: Dict[str, dict] = {}
    for row in lobby:
        if row.mep_id:
            mid = f"mep:{row.mep_id}"
            g.node(mid, type="mep", institution="ep", label=row.mep_name or f"MEP {row.mep_id}",
                   sublabel=(row.role or "Met on file").title(), relevance=0.55,
                   url=_MEP_URL.format(id=row.mep_id), meta={"role": row.role, "committee": row.committee})
            g.edge(mid, fid, "engaged_on", "mep_watch")
        key = row.transparency_register_id or (row.organisation_norm or row.organisation)
        if not key:
            continue
        org_meet[key] += 1
        if key not in org_seen:
            org_seen[key] = {"name": row.organisation, "norm": row.organisation_norm,
                             "tr": row.transparency_register_id, "website": row.org_website,
                             "register_url": row.org_register_url, "mep": row.mep_id}
            if row.transparency_register_id:
                org_ids.append(row.transparency_register_id)
            if row.organisation_norm:
                org_names.append(row.organisation_norm)

    tr = _tr_records(db, org_ids)
    stance = _stance_by_org(db, org_ids, org_names)
    for key, info in list(org_seen.items())[:14]:
        rec = tr.get(info["tr"] or "", {})
        st = stance.get(f"tr:{info['tr']}") or stance.get(f"nm:{info['norm']}") or {}
        oid = f"org:{info['tr'] or info['norm'] or info['name']}"
        node = g.node(oid, type="org", institution="stakeholder",
                      label=rec.get("acronym") or info["name"][:60],
                      sublabel=rec.get("category") or "Organisation",
                      relevance=min(0.85, 0.4 + 0.08 * org_meet[key]),
                      stance=st.get("stance"),
                      url=info["register_url"] or rec.get("register_url")
                          or (_TR_URL.format(id=info["tr"]) if info["tr"] else info["website"]),
                      meta={"full_name": info["name"], "tr_number": info["tr"],
                            "website": info["website"] or rec.get("website"),
                            "hq_city": rec.get("hq_city"), "hq_country": rec.get("hq_country"),
                            "is_brussels": rec.get("is_brussels", False),
                            "meetings": org_meet[key], "stance_summary": st.get("summary"),
                            "stance_excerpt": st.get("excerpt"), "kind": "lobbying"})
        g.edge(oid, fid, "lobbied_on", "lobby_meetings", weight=org_meet[key])
        if info.get("mep"):
            g.edge(oid, f"mep:{info['mep']}", "met", "lobby_meetings")

    # lead DG + Council configuration (inference via crosswalk)
    dom = _domains_for_committee(carriage.lead_committee) or pi_domains
    dgs = _dedup_list([d for x in dom for d in PI_TO_DGS.get(x, [])])[:2]
    lead_dg = dgs[0] if dgs else None
    for dg in dgs:
        did = f"dg:{dg}"
        g.node(did, type="dg", institution="ec", label=dg,
               sublabel=COMMISSION_DG_NAME.get(dg, "Commission DG"), relevance=0.7,
               pi_match=dg in {d for x in pi_domains for d in PI_TO_DGS.get(x, [])},
               url=_WIW_URL.format(dg=dg), meta={})
        g.edge(did, fid, "lead_dg", "pi_crosswalk")
    for cfg in _dedup_list([c for x in dom for c in PI_TO_COUNCIL_CONFIGS.get(x, [])])[:2]:
        cid = f"council:{cfg}"
        g.node(cid, type="council_config", institution="council", label=cfg,
               sublabel=COUNCIL_CONFIGURATIONS.get(cfg, "Council configuration"), relevance=0.55,
               url="https://www.consilium.europa.eu/en/council-eu/configurations/", meta={})
        g.edge(cid, fid, "responsible_config", "pi_crosswalk")

    # EU Who-is-Who: named senior officials behind the lead DG (ingested from the
    # static WhoisWho PDF). Falls back to a clickable org-chart node if a DG is not
    # in the directory.
    if deep and lead_dg:
        offs = _officials_for(lead_dg)[:4]
        if offs:
            for o in offs:
                oid = f"official:{lead_dg}:{o['name']}"
                g.node(oid, type="official", institution="ec", label=o["name"],
                       sublabel=o.get("function") or "Official", relevance=0.4,
                       url=_WIW_URL.format(dg=lead_dg), meta={"dg": lead_dg, "kind": "whoiswho"})
                g.edge(oid, f"dg:{lead_dg}", "official_of", "whoiswho")
        else:
            oid = f"official:{lead_dg}"
            g.node(oid, type="official", institution="ec", label=f"{lead_dg} leadership",
                   sublabel="EU Who-is-Who org chart", relevance=0.4, url=_WIW_URL.format(dg=lead_dg),
                   meta={"dg": lead_dg, "kind": "whoiswho_portal"})
            g.edge(oid, f"dg:{lead_dg}", "official_of", "whoiswho")

    # Brussels-HQ ecosystem (trade associations + NGOs matched to the policy keywords)
    if deep:
        kws = list(keywords_for_interests(dom))[:8]
        if kws:
            like = " OR ".join([f"original_name ILIKE :k{i}" for i in range(len(kws))])
            params = {f"k{i}": f"%{k}%" for i, k in enumerate(kws)}
            params["cats"] = [_TRADE, _NGO]
            try:
                rows = db.execute(text(
                    f"SELECT identification_code, original_name, acronym, website_url, public_url, "
                    f"registration_category, head_office_city, eu_office_city FROM eu_transparency_register "
                    f"WHERE registration_category = ANY(:cats) "
                    f"AND (head_office_city ILIKE '%brussel%' OR head_office_city ILIKE '%bruxelles%' "
                    f"OR eu_office_city ILIKE '%brussel%' OR eu_office_city ILIKE '%bruxelles%') "
                    f"AND ({like}) LIMIT 8"
                ), params).fetchall()
                for r in rows:
                    oid = f"org:{r.identification_code}"
                    if oid in g.nodes:
                        continue
                    g.node(oid, type="org", institution="stakeholder",
                           label=r.acronym or r.original_name[:60], sublabel=r.registration_category,
                           relevance=0.32, url=r.public_url or r.website_url,
                           meta={"full_name": r.original_name, "tr_number": r.identification_code,
                                 "website": r.website_url, "hq_city": r.head_office_city or r.eu_office_city,
                                 "is_brussels": True, "kind": "ecosystem"})
                    g.edge(oid, fid, "active_in_area", "transparency_register")
            except Exception as e:
                logger.warning("[stakeholders] ecosystem query failed: %s", e)

    return g


# --------------------------------------------------------------------- public
def file_graph(db: Session, carriage, pi_domains: List[str]) -> dict:
    g = build_file_graph(db, carriage, pi_domains, deep=True)
    return g.payload("file", {"id": f"file:{carriage.oeil_procedure_ref or carriage.id}",
                              "label": carriage.title or carriage.oeil_procedure_ref or "File"},
                     bool(pi_domains),
                     ["oeil", "mep_watch", "lobby_meetings", "consultation_feedback",
                      "pi_crosswalk", "transparency_register", "whoiswho"])


def strategy_draft(db: Session, carriage, pi_domains: List[str]) -> dict:
    """Assemble a pre-filled advocacy-strategy draft for a file from the Stakeholder
    Map: decision-makers (rapporteur, shadows, committees, lead DG, Council), who to
    contact (DG unit heads + emails), and the field (who supports / opposes / wants
    amendments). Returns {title, objectives, content (markdown), procedure_reference,
    stakeholders}. All data is real; the user fills objective, messages and asks."""
    g = build_file_graph(db, carriage, pi_domains, deep=True)
    nodes = list(g.nodes.values())
    by = lambda tp: [n for n in nodes if n["type"] == tp]
    name = lambda o: (o.get("meta") or {}).get("full_name") or o["label"]

    rapp = next((n for n in by("mep") if (n.get("sublabel") or "").lower().startswith("rapporteur")), None)
    shadows = [n for n in by("mep") if (n.get("sublabel") or "").lower().startswith("shadow")]
    committees = by("committee")
    lead_com = next((n for n in committees if n.get("relevance", 0) >= 0.8), committees[0] if committees else None)
    dgs, council, orgs = by("dg"), by("council_config"), by("org")
    sup = [o for o in orgs if o.get("stance") == "support"]
    opp = [o for o in orgs if o.get("stance") == "oppose"]
    amd = [o for o in orgs if o.get("stance") == "amend"]
    other = [o for o in orgs if not o.get("stance")]
    proc = carriage.oeil_procedure_ref

    contacts = None
    lead_dg = dgs[0]["label"] if dgs else None
    if lead_dg:
        dom = _domains_for_committee(carriage.lead_committee) or pi_domains
        contacts = dg_contacts(lead_dg, list(keywords_for_interests(dom)))

    L: List[str] = ["## Objective", "State the outcome you want on this file, and by when.", ""]
    L.append("## Decision-makers")
    if rapp:
        com = (rapp.get("meta") or {}).get("committee")
        L.append(f"- Rapporteur: {rapp['label']}" + (f" ({com})" if com else ""))
    for s in shadows:
        L.append(f"- Shadow rapporteur: {s['label']}")
    if lead_com:
        L.append(f"- Lead committee: {lead_com['label']} ({lead_com.get('sublabel')})")
    for d in dgs:
        L.append(f"- Commission lead: DG {d['label']} ({d.get('sublabel')})")
    for c in council:
        L.append(f"- Council: {c['label']} ({c.get('sublabel')})")
    L.append("")

    if contacts:
        L.append("## Who to contact in the Commission")
        dgp = contacts.get("director_general")
        if dgp:
            L.append(f"- {dgp['name']}, Director-General, DG {contacts['dg']}"
                     + (f" ({dgp.get('email')})" if dgp.get("email") else ""))
        n = 0
        for D in contacts.get("directorates", []):
            for u in D.get("units", []):
                h = u.get("head")
                if u.get("relevant") and h and h.get("email"):
                    L.append(f"- {h['name']}, Head of Unit, {u['code']} {u['name']} ({h['email']})")
                    n += 1
                    if n >= 6:
                        break
            if n >= 6:
                break
        L.append("")

    L.append("## The field")
    if sup:
        L.append("Supporting: " + ", ".join(name(o) for o in sup))
    if opp:
        L.append("Opposing: " + ", ".join(name(o) for o in opp))
    if amd:
        L.append("Seeking amendments: " + ", ".join(name(o) for o in amd))
    if other:
        L.append("Also active: " + ", ".join(name(o) for o in other[:10]))
    if not orgs:
        L.append("No lobbying footprint recorded yet on this file.")
    L.append("")
    L += ["## Key messages", "- ", "", "## Engagement plan", "- ", "", "## Asks", "- ", ""]

    return {
        "title": f"Advocacy strategy: {carriage.title or proc or 'file'}",
        "objectives": "",
        "content": "\n".join(L),
        "procedure_reference": proc,
        "stakeholders": [name(o) for o in orgs[:12]],
    }


def pi_graph(db: Session, carriages: List, pi_domains: List[str], limit_files: int = 12) -> dict:
    """PI-overview: union of the core actors across the user's tracked files, deduped;
    relevance rises with cross-file recurrence ('who keeps showing up')."""
    g = _Graph()
    hub = "pi:hub"
    g.node(hub, type="file", institution="file", label="Your interests", sublabel="Policy portfolio",
           relevance=1.0, url=None, meta={"files": len(carriages)})
    for c in carriages[:limit_files]:
        sub = build_file_graph(db, c, pi_domains, deep=False)  # skip who-is-who/ecosystem for speed
        fid = f"file:{c.oeil_procedure_ref or c.id}"
        # merge sub-graph nodes/edges into the union
        for n in sub.nodes.values():
            if n["type"] == "file":
                g.node(n["id"], **{k: v for k, v in n.items() if k != "id"})
                g.edge(n["id"], hub, "in_portfolio", "pi_crosswalk")
            else:
                merged = g.node(n["id"], **{k: v for k, v in n.items() if k not in ("id", "relevance")},
                                relevance=0.0)
                merged["relevance"] = min(1.0, merged.get("relevance", 0) + 0.18)  # recurrence bump
        for e in sub.edges:
            g.edge(e["source"], e["target"], e["rel"], e["source_kind"], e.get("weight", 1.0))
    return g.payload("pi", {"id": hub, "label": "Your interests"}, bool(pi_domains),
                     ["oeil", "mep_watch", "lobby_meetings", "pi_crosswalk"])
