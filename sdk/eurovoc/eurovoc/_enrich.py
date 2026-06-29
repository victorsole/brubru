"""EuroVoc descriptor type + the hierarchy roll-up (descriptor -> microthesaurus
-> domain). The 21 top-level domains are a stable public vocabulary, embedded
here; the microthesaurus (`mt`) code's first two digits ARE the domain code."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# The 21 EuroVoc top-level domains (DO). domain code == mt[:2].
DOMAINS: Dict[str, str] = {
    "04": "POLITICS",
    "08": "INTERNATIONAL RELATIONS",
    "10": "EUROPEAN UNION",
    "12": "LAW",
    "16": "ECONOMICS",
    "20": "TRADE",
    "24": "FINANCE",
    "28": "SOCIAL QUESTIONS",
    "32": "EDUCATION AND COMMUNICATIONS",
    "36": "SCIENCE",
    "40": "BUSINESS AND COMPETITION",
    "44": "EMPLOYMENT AND WORKING CONDITIONS",
    "48": "TRANSPORT",
    "52": "ENVIRONMENT",
    "56": "AGRICULTURE, FORESTRY AND FISHERIES",
    "60": "AGRI-FOODSTUFFS",
    "64": "PRODUCTION, TECHNOLOGY AND RESEARCH",
    "66": "ENERGY",
    "68": "INDUSTRY",
    "72": "GEOGRAPHY",
    "76": "INTERNATIONAL ORGANISATIONS",
}


@dataclass
class Descriptor:
    """One EuroVoc subject descriptor with its hierarchy and (when classified)
    a confidence score."""

    id: str
    label: str
    score: Optional[float] = None
    mt: Optional[str] = None
    domain: Optional[str] = None
    domain_label: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"descriptor": self.label, "id": self.id, "mt": self.mt,
                "domain": self.domain, "domain_label": self.domain_label, "score": self.score}


def _enrich_one(d: Dict[str, Any]) -> Descriptor:
    mt = d.get("mt")
    domain = mt[:2] if mt and len(mt) >= 2 else None
    return Descriptor(
        id=str(d.get("id", "")),
        label=d.get("label") or d.get("descriptor") or "",
        score=d.get("score"),
        mt=mt,
        domain=domain,
        domain_label=DOMAINS.get(domain) if domain else None,
    )


def from_descriptors(raw: List[Dict[str, Any]]) -> List[Descriptor]:
    """Turn raw EuroVoc dicts (e.g. the ``eurovoc_descriptors`` an extract item
    carries, or the brubru SDK output) into domain-enriched Descriptor objects.
    This is the interop bridge: the API classifies, ``eurovoc`` types + rolls up."""
    return [_enrich_one(d) for d in (raw or [])]
