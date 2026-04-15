#!/usr/bin/env python3
"""
europa_sources_enumerator.py

Enumerates all discoverable subdomains under .europa.eu using free passive
sources, verifies which are live, auto-classifies each by parent institution,
and writes the result to europa_sources.csv (columns: url, institution).

Free sources used:
    1. subfinder (Go binary, ProjectDiscovery) - aggregates ~30 passive sources
    2. amass    (Go binary, OWASP)              - additional passive sources
    3. crt.sh   (Certificate Transparency logs) - HTTPS JSON API, no key
    4. Wayback Machine CDX API                  - historical archived URLs
    5. httpx    (Go binary, ProjectDiscovery)   - liveness verification

Required external binaries: subfinder, amass, httpx
The script checks for these upfront and exits cleanly if any are missing.

Usage:
    python3 europa_sources_enumerator.py
    python3 europa_sources_enumerator.py --skip-liveness   # faster, unverified
    python3 europa_sources_enumerator.py --output path.csv

Author: Built for Brubru (Beresol BV) to map the .europa.eu ecosystem.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

TARGET_DOMAIN = "europa.eu"
DEFAULT_OUTPUT = "europa_sources.csv"
REQUIRED_BINARIES = ["subfinder", "amass", "httpx"]

CRT_SH_URL = (
    "https://crt.sh/?q=" + urllib.parse.quote("%." + TARGET_DOMAIN) + "&output=json"
)
WAYBACK_CDX_URL = (
    "http://web.archive.org/cdx/search/cdx"
    "?url=*." + TARGET_DOMAIN
    + "&output=json&fl=original&collapse=urlkey"
)

# Timeouts (seconds)
HTTP_TIMEOUT = 60
SUBFINDER_TIMEOUT = 900
AMASS_TIMEOUT = 1800
HTTPX_TIMEOUT = 1800

# -----------------------------------------------------------------------------
# Institution classification
# -----------------------------------------------------------------------------
#
# Classification is applied in order: the first rule whose pattern matches
# the hostname wins. Patterns are matched as (a) exact host equality, or
# (b) host suffix after splitting on dots (so "ema.europa.eu" matches
# "clinicaldata.ema.europa.eu" and "ema.europa.eu" itself).
#
# Unknown hosts fall through to a generic "Unclassified - <parent>" label.

# Exact DG subdomain -> institution
DG_EXACT = {
    "agriculture.ec.europa.eu": "European Commission - DG AGRI (Agriculture and Rural Development)",
    "climate.ec.europa.eu": "European Commission - DG CLIMA (Climate Action)",
    "competition.ec.europa.eu": "European Commission - DG COMP (Competition)",
    "civil-protection-humanitarian-aid.ec.europa.eu": "European Commission - DG ECHO (Civil Protection and Humanitarian Aid)",
    "economy-finance.ec.europa.eu": "European Commission - DG ECFIN (Economic and Financial Affairs)",
    "education.ec.europa.eu": "European Commission - DG EAC (Education and Culture)",
    "employment.ec.europa.eu": "European Commission - DG EMPL (Employment and Social Affairs)",
    "employment-social-affairs.ec.europa.eu": "European Commission - DG EMPL (Employment and Social Affairs)",
    "energy.ec.europa.eu": "European Commission - DG ENER (Energy)",
    "environment.ec.europa.eu": "European Commission - DG ENV (Environment)",
    "finance.ec.europa.eu": "European Commission - DG FISMA (Financial Stability and Capital Markets)",
    "fisheries.ec.europa.eu": "European Commission - DG MARE (Maritime Affairs and Fisheries)",
    "food.ec.europa.eu": "European Commission - DG SANTE (Food Safety)",
    "health.ec.europa.eu": "European Commission - DG SANTE (Health)",
    "home-affairs.ec.europa.eu": "European Commission - DG HOME (Migration and Home Affairs)",
    "international-partnerships.ec.europa.eu": "European Commission - DG INTPA (International Partnerships)",
    "justice.ec.europa.eu": "European Commission - DG JUST (Justice and Consumers)",
    "neighbourhood-enlargement.ec.europa.eu": "European Commission - DG NEAR (Neighbourhood and Enlargement)",
    "defence-industry-space.ec.europa.eu": "European Commission - DG DEFIS (Defence Industry and Space)",
    "digital-strategy.ec.europa.eu": "European Commission - DG CNECT (Digital Strategy)",
    "reform-support.ec.europa.eu": "European Commission - DG REFORM (Structural Reform Support)",
    "regional-policy.ec.europa.eu": "European Commission - DG REGIO (Regional and Urban Policy)",
    "research-and-innovation.ec.europa.eu": "European Commission - DG RTD (Research and Innovation)",
    "single-market-economy.ec.europa.eu": "European Commission - DG GROW (Internal Market and Industry)",
    "taxation-customs.ec.europa.eu": "European Commission - DG TAXUD (Taxation and Customs Union)",
    "trade.ec.europa.eu": "European Commission - DG TRADE (Trade)",
    "transport.ec.europa.eu": "European Commission - DG MOVE (Mobility and Transport)",
    "anti-fraud.ec.europa.eu": "European Commission - OLAF (European Anti-Fraud Office)",
    "communication.ec.europa.eu": "European Commission - DG COMM (Communication)",
    "secretariat-general.ec.europa.eu": "European Commission - Secretariat-General",
    "budget.ec.europa.eu": "European Commission - DG BUDG (Budget)",
    "hera.ec.europa.eu": "European Commission - HERA (Health Emergency Preparedness)",
}

# Suffix -> institution. Matches any host ending in the given suffix.
# Order matters: more specific suffixes must come before less specific ones
# (e.g. "jrc.ec.europa.eu" before "ec.europa.eu").
SUFFIX_RULES: list[tuple[str, str]] = [
    # --- European Parliament and its sub-services ---
    ("oeil.secure.europarl.europa.eu", "European Parliament - Legislative Observatory (OEIL)"),
    ("ecprd.secure.europarl.europa.eu", "European Parliament - ECPRD (Parliamentary Research)"),
    ("historia.europa.eu", "European Parliament - House of European History"),
    ("jean-monnet.europa.eu", "European Parliament - Jean Monnet House"),
    ("europarl.europa.eu", "European Parliament"),
    ("elections.europa.eu", "European Parliament - EU Election Results"),
    ("appf.europa.eu", "Authority for European Political Parties and Foundations"),

    # --- JRC sub-subdomains (must come before ec.europa.eu catch-all) ---
    ("jrc.ec.europa.eu", "European Commission - Joint Research Centre (JRC)"),
    ("joint-research-centre.ec.europa.eu", "European Commission - Joint Research Centre (JRC)"),

    # --- EC Representations in Member States ---
    ("austria.representation.ec.europa.eu", "European Commission - Representation in Austria"),
    ("belgium.representation.ec.europa.eu", "European Commission - Representation in Belgium"),
    ("bulgaria.representation.ec.europa.eu", "European Commission - Representation in Bulgaria"),
    ("croatia.representation.ec.europa.eu", "European Commission - Representation in Croatia"),
    ("cyprus.representation.ec.europa.eu", "European Commission - Representation in Cyprus"),
    ("czechia.representation.ec.europa.eu", "European Commission - Representation in Czechia"),
    ("denmark.representation.ec.europa.eu", "European Commission - Representation in Denmark"),
    ("estonia.representation.ec.europa.eu", "European Commission - Representation in Estonia"),
    ("finland.representation.ec.europa.eu", "European Commission - Representation in Finland"),
    ("france.representation.ec.europa.eu", "European Commission - Representation in France"),
    ("germany.representation.ec.europa.eu", "European Commission - Representation in Germany"),
    ("greece.representation.ec.europa.eu", "European Commission - Representation in Greece"),
    ("hungary.representation.ec.europa.eu", "European Commission - Representation in Hungary"),
    ("ireland.representation.ec.europa.eu", "European Commission - Representation in Ireland"),
    ("italy.representation.ec.europa.eu", "European Commission - Representation in Italy"),
    ("latvia.representation.ec.europa.eu", "European Commission - Representation in Latvia"),
    ("lithuania.representation.ec.europa.eu", "European Commission - Representation in Lithuania"),
    ("luxembourg.representation.ec.europa.eu", "European Commission - Representation in Luxembourg"),
    ("malta.representation.ec.europa.eu", "European Commission - Representation in Malta"),
    ("netherlands.representation.ec.europa.eu", "European Commission - Representation in Netherlands"),
    ("poland.representation.ec.europa.eu", "European Commission - Representation in Poland"),
    ("portugal.representation.ec.europa.eu", "European Commission - Representation in Portugal"),
    ("romania.representation.ec.europa.eu", "European Commission - Representation in Romania"),
    ("slovakia.representation.ec.europa.eu", "European Commission - Representation in Slovakia"),
    ("slovenia.representation.ec.europa.eu", "European Commission - Representation in Slovenia"),
    ("spain.representation.ec.europa.eu", "European Commission - Representation in Spain"),
    ("sweden.representation.ec.europa.eu", "European Commission - Representation in Sweden"),
    ("representation.ec.europa.eu", "European Commission - Representation / Regional Office"),

    # --- Executive Agencies ---
    ("cinea.ec.europa.eu", "CINEA - Climate Infrastructure and Environment Executive Agency"),
    ("eacea.ec.europa.eu", "EACEA - European Education and Culture Executive Agency"),
    ("hadea.ec.europa.eu", "HaDEA - European Health and Digital Executive Agency"),
    ("rea.ec.europa.eu", "REA - European Research Executive Agency"),
    ("eismea.ec.europa.eu", "EISMEA - European Innovation Council and SMEs Executive Agency"),
    ("erc.europa.eu", "ERCEA - European Research Council Executive Agency"),

    # --- Decentralised agencies (sorted so longest/most-specific hit first) ---
    ("bankingsupervision.europa.eu", "European Central Bank - Banking Supervision (SSM)"),
    ("ecb.europa.eu", "European Central Bank"),
    ("eca.europa.eu", "European Court of Auditors"),
    ("curia.europa.eu", "Court of Justice of the European Union"),
    ("eeas.europa.eu", "European External Action Service"),
    ("eesc.europa.eu", "European Economic and Social Committee"),
    ("cor.europa.eu", "European Committee of the Regions"),
    ("consilium.europa.eu", "Council of the European Union"),
    ("european-council.europa.eu", "European Council"),
    ("ombudsman.europa.eu", "European Ombudsman"),
    ("edps.europa.eu", "European Data Protection Supervisor"),
    ("edpb.europa.eu", "European Data Protection Board"),
    ("eib.europa.eu", "European Investment Bank"),
    ("eif.europa.eu", "European Investment Fund"),
    ("esm.europa.eu", "European Stability Mechanism"),
    ("esrb.europa.eu", "European Systemic Risk Board"),

    ("acer.europa.eu", "ACER - Agency for Cooperation of Energy Regulators"),
    ("berec.europa.eu", "BEREC Office"),
    ("era.europa.eu", "ERA - EU Agency for Railways"),
    ("easa.europa.eu", "EASA - EU Aviation Safety Agency"),
    ("emsa.europa.eu", "EMSA - European Maritime Safety Agency"),
    ("eea.europa.eu", "EEA - European Environment Agency"),
    ("eionet.europa.eu", "EEA - Eionet (European Environment Information Network)"),
    ("biodiversity.europa.eu", "EEA - Biodiversity Information System (BISE)"),
    ("water.europa.eu", "EEA - WISE (Water Information System)"),
    ("efsa.europa.eu", "EFSA - European Food Safety Authority"),
    ("ecdc.europa.eu", "ECDC - European Centre for Disease Prevention and Control"),
    ("ema.europa.eu", "EMA - European Medicines Agency"),
    ("emea.europa.eu", "EMA - European Medicines Agency (legacy)"),
    ("echa.europa.eu", "ECHA - European Chemicals Agency"),
    ("efca.europa.eu", "EFCA - European Fisheries Control Agency"),
    ("cpvo.europa.eu", "CPVO - Community Plant Variety Office"),
    ("esma.europa.eu", "ESMA - European Securities and Markets Authority"),
    ("eba.europa.eu", "EBA - European Banking Authority"),
    ("eiopa.europa.eu", "EIOPA - European Insurance and Occupational Pensions Authority"),
    ("srb.europa.eu", "SRB - Single Resolution Board"),
    ("amla.europa.eu", "AMLA - Anti-Money Laundering Authority"),
    ("europol.europa.eu", "Europol"),
    ("eurojust.europa.eu", "Eurojust"),
    ("frontex.europa.eu", "Frontex"),
    ("euaa.europa.eu", "EUAA - EU Agency for Asylum"),
    ("euda.europa.eu", "EUDA - EU Drugs Agency"),
    ("emcdda.europa.eu", "EMCDDA (legacy, now EUDA)"),
    ("eulisa.europa.eu", "eu-LISA"),
    ("cepol.europa.eu", "CEPOL"),
    ("eppo.europa.eu", "EPPO - European Public Prosecutor's Office"),
    ("enisa.europa.eu", "ENISA - EU Agency for Cybersecurity"),
    ("fra.europa.eu", "FRA - EU Agency for Fundamental Rights"),
    ("eige.europa.eu", "EIGE - European Institute for Gender Equality"),
    ("ela.europa.eu", "ELA - European Labour Authority"),
    ("ejn-crimjust.europa.eu", "European Judicial Network (Criminal Matters)"),
    ("euspa.europa.eu", "EUSPA - EU Agency for the Space Programme"),
    ("gsa.europa.eu", "European GNSS Agency (legacy, now EUSPA)"),
    ("eda.europa.eu", "EDA - European Defence Agency"),
    ("satcen.europa.eu", "SatCen - EU Satellite Centre"),
    ("iss.europa.eu", "EUISS - EU Institute for Security Studies"),
    ("cybersecurity-centre.europa.eu", "ECCC - European Cybersecurity Competence Centre"),
    ("cedefop.europa.eu", "Cedefop"),
    ("etf.europa.eu", "ETF - European Training Foundation"),
    ("eurofound.europa.eu", "Eurofound"),
    ("osha.europa.eu", "EU-OSHA"),
    ("euipo.europa.eu", "EUIPO - EU Intellectual Property Office"),
    ("tmview.europa.eu", "EUIPO - TMview"),
    ("cdt.europa.eu", "CdT - Translation Centre for the Bodies of the EU"),

    # --- Euratom / Joint Undertakings ---
    ("fusionforenergy.europa.eu", "Fusion for Energy (F4E)"),
    ("euratom-supply.ec.europa.eu", "Euratom Supply Agency"),
    ("chips-ju.europa.eu", "Chips Joint Undertaking"),
    ("cbe.europa.eu", "CBE JU - Circular Bio-based Europe"),
    ("clean-hydrogen.europa.eu", "Clean Hydrogen Joint Undertaking"),
    ("rail-research.europa.eu", "Europe's Rail Joint Undertaking"),
    ("eurohpc-ju.europa.eu", "EuroHPC Joint Undertaking"),
    ("ihi.europa.eu", "IHI JU - Innovative Health Initiative"),
    ("smart-networks.europa.eu", "SNS JU - Smart Networks and Services"),
    ("global-health-edctp3.europa.eu", "Global Health EDCTP3 Joint Undertaking"),
    ("eit.europa.eu", "EIT - European Institute of Innovation and Technology"),

    # --- Interinstitutional / legal / data ---
    ("eur-lex.europa.eu", "Publications Office - EUR-Lex"),
    ("n-lex.europa.eu", "Publications Office - N-Lex"),
    ("e-justice.europa.eu", "European Commission - e-Justice Portal"),
    ("iate.europa.eu", "CdT - IATE Terminology Database"),
    ("ted.europa.eu", "Publications Office - TED (Tenders Electronic Daily)"),
    ("eurovoc.europa.eu", "Publications Office - EuroVoc"),
    ("op.europa.eu", "Publications Office of the EU"),
    ("publications.europa.eu", "Publications Office of the EU"),
    ("bookshop.europa.eu", "Publications Office - EU Bookshop (legacy)"),
    ("data.europa.eu", "Publications Office - EU Open Data Portal"),
    ("open-data.europa.eu", "Publications Office - EU Open Data Portal"),
    ("transparency.europa.eu", "EU Transparency Register"),
    ("transparency-register.europa.eu", "EU Transparency Register"),
    ("cordis.europa.eu", "Publications Office / DG RTD - CORDIS"),
    ("whoiswho.europa.eu", "Publications Office - EU Who Is Who"),
    ("epso.europa.eu", "EPSO - European Personnel Selection Office"),
    ("eu-careers.europa.eu", "EU Careers Portal"),
    ("cert.europa.eu", "CERT-EU"),
    ("trusted-digital-identity.europa.eu", "EU Login Portal"),

    # --- Citizens / democracy portals ---
    ("citizens-initiative.europa.eu", "European Commission - European Citizens' Initiative"),
    ("youth.europa.eu", "European Commission - European Youth Portal"),
    ("european-solidarity-corps.europa.eu", "European Commission - European Solidarity Corps"),
    ("europass.europa.eu", "European Commission / Cedefop - Europass"),
    ("eures.europa.eu", "European Labour Authority - EURES"),
    ("futureu.europa.eu", "Conference on the Future of Europe"),
    ("next-generation-eu.europa.eu", "European Commission - NextGenerationEU"),
    ("digital-skills-jobs.europa.eu", "European Commission - Digital Skills and Jobs Platform"),

    # --- EC catch-alls (must come LAST) ---
    ("commission.europa.eu", "European Commission"),
    ("ec.europa.eu", "European Commission"),
    ("european-union.europa.eu", "European Union - Gateway Site"),
    ("europa.eu", "European Union - General"),
]

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

# Basic hostname regex: labels of alphanumerics/hyphens separated by dots.
HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)+$")


def info(msg: str) -> None:
    print(f"[INFO] {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"[WARN] {msg}", file=sys.stderr, flush=True)


def error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)


def check_binaries(binaries: list[str]) -> None:
    """Exit cleanly if any required Go binary is missing from PATH."""
    missing = [b for b in binaries if shutil.which(b) is None]
    if missing:
        error("Missing required external tool(s): " + ", ".join(missing))
        print(
            "\nInstall the missing tools and re-run. Installation instructions:\n"
            "  subfinder: go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest\n"
            "  amass:     go install -v github.com/owasp-amass/amass/v4/...@master\n"
            "  httpx:     go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest\n"
            "\nAlso ensure $(go env GOPATH)/bin is on your PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    info("All required binaries found: " + ", ".join(binaries))


def normalise_host(raw: str) -> str | None:
    """Strip wildcards, protocols, paths, and ports. Return a bare hostname or None."""
    if not raw:
        return None
    host = raw.strip().lower()
    # Strip protocol
    if "://" in host:
        host = host.split("://", 1)[1]
    # Strip path
    host = host.split("/", 1)[0]
    # Strip port
    host = host.split(":", 1)[0]
    # Strip leading wildcards like *.
    while host.startswith("*."):
        host = host[2:]
    # Strip leading dots
    host = host.lstrip(".")
    if not host:
        return None
    # Must end in the target domain
    if not (host == TARGET_DOMAIN or host.endswith("." + TARGET_DOMAIN)):
        return None
    if not HOSTNAME_RE.match(host):
        return None
    return host


def run_command(cmd: list[str], timeout: int) -> str:
    """Run a command and return stdout. Empty string on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            warn(f"{cmd[0]} exited {result.returncode}: {result.stderr.strip()[:300]}")
        return result.stdout or ""
    except subprocess.TimeoutExpired:
        warn(f"{cmd[0]} timed out after {timeout}s")
        return ""
    except FileNotFoundError:
        warn(f"{cmd[0]} not found on PATH")
        return ""


# -----------------------------------------------------------------------------
# Source: subfinder
# -----------------------------------------------------------------------------

def fetch_subfinder() -> set[str]:
    info("Running subfinder (this can take several minutes)...")
    output = run_command(
        ["subfinder", "-d", TARGET_DOMAIN, "-all", "-silent"],
        timeout=SUBFINDER_TIMEOUT,
    )
    hosts = {h for h in (normalise_host(line) for line in output.splitlines()) if h}
    info(f"subfinder returned {len(hosts)} unique hosts")
    return hosts


# -----------------------------------------------------------------------------
# Source: amass (passive)
# -----------------------------------------------------------------------------

def fetch_amass() -> set[str]:
    info("Running amass (passive mode, this can take a while)...")
    output = run_command(
        ["amass", "enum", "-passive", "-d", TARGET_DOMAIN, "-silent"],
        timeout=AMASS_TIMEOUT,
    )
    hosts = {h for h in (normalise_host(line) for line in output.splitlines()) if h}
    info(f"amass returned {len(hosts)} unique hosts")
    return hosts


# -----------------------------------------------------------------------------
# Source: crt.sh
# -----------------------------------------------------------------------------

def fetch_crtsh() -> set[str]:
    info("Querying crt.sh (Certificate Transparency logs)...")
    hosts: set[str] = set()
    try:
        req = urllib.request.Request(
            CRT_SH_URL,
            headers={"User-Agent": "europa-enumerator/1.0"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        warn(f"crt.sh query failed: {exc}")
        return hosts

    for entry in data:
        name_value = entry.get("name_value", "")
        # crt.sh can return multiple names per cert separated by newlines
        for raw in name_value.split("\n"):
            host = normalise_host(raw)
            if host:
                hosts.add(host)
    info(f"crt.sh returned {len(hosts)} unique hosts")
    return hosts


# -----------------------------------------------------------------------------
# Source: Wayback Machine CDX
# -----------------------------------------------------------------------------

def fetch_wayback() -> set[str]:
    info("Querying Wayback Machine CDX API...")
    hosts: set[str] = set()
    try:
        req = urllib.request.Request(
            WAYBACK_CDX_URL,
            headers={"User-Agent": "europa-enumerator/1.0"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        warn(f"Wayback CDX query failed: {exc}")
        return hosts

    # First row is the header (["original"])
    for row in data[1:]:
        if not row:
            continue
        host = normalise_host(row[0])
        if host:
            hosts.add(host)
    info(f"Wayback Machine returned {len(hosts)} unique hosts")
    return hosts


# -----------------------------------------------------------------------------
# Liveness check with httpx
# -----------------------------------------------------------------------------

def verify_live_hosts(hosts: Iterable[str]) -> set[str]:
    host_list = sorted(hosts)
    info(f"Probing {len(host_list)} hosts with httpx (this is the slow step)...")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fp:
        input_path = Path(fp.name)
        for h in host_list:
            fp.write(h + "\n")

    try:
        output = run_command(
            [
                "httpx",
                "-l", str(input_path),
                "-silent",
                "-no-color",
                "-follow-redirects",
                "-timeout", "10",
                "-threads", "50",
            ],
            timeout=HTTPX_TIMEOUT,
        )
    finally:
        input_path.unlink(missing_ok=True)

    live: set[str] = set()
    for line in output.splitlines():
        host = normalise_host(line)
        if host:
            live.add(host)
    info(f"httpx confirmed {len(live)} live hosts")
    return live


# -----------------------------------------------------------------------------
# Classification
# -----------------------------------------------------------------------------

def classify(host: str) -> str:
    """Map a hostname to its parent institution."""
    if host in DG_EXACT:
        return DG_EXACT[host]

    for suffix, institution in SUFFIX_RULES:
        if host == suffix or host.endswith("." + suffix):
            return institution

    # Fallback: take the two rightmost labels above europa.eu as a hint
    labels = host.split(".")
    if len(labels) >= 3:
        parent = ".".join(labels[-3:])
        return f"Unclassified - {parent}"
    return "Unclassified - europa.eu"


# -----------------------------------------------------------------------------
# CSV writer
# -----------------------------------------------------------------------------

def write_csv(hosts: Iterable[str], output_path: Path) -> int:
    rows = sorted({(f"https://{h}", classify(h)) for h in hosts})
    with output_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["url", "institution"])
        writer.writerows(rows)
    return len(rows)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enumerate all .europa.eu subdomains from free sources and write a CSV.",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--skip-liveness",
        action="store_true",
        help="Skip httpx liveness probing (faster, but includes dead hosts)",
    )
    args = parser.parse_args()

    required = ["subfinder", "amass"]
    if not args.skip_liveness:
        required.append("httpx")
    check_binaries(required)

    info(f"Target domain: {TARGET_DOMAIN}")
    all_hosts: set[str] = set()
    all_hosts |= fetch_subfinder()
    all_hosts |= fetch_amass()
    all_hosts |= fetch_crtsh()
    all_hosts |= fetch_wayback()

    info(f"Total unique hosts across all sources: {len(all_hosts)}")

    if not all_hosts:
        error("No hosts discovered from any source. Aborting.")
        return 2

    if args.skip_liveness:
        final_hosts = all_hosts
    else:
        final_hosts = verify_live_hosts(all_hosts)
        if not final_hosts:
            warn("httpx returned zero live hosts; falling back to unverified list")
            final_hosts = all_hosts

    output_path = Path(args.output).resolve()
    written = write_csv(final_hosts, output_path)
    info(f"Wrote {written} rows to {output_path}")

    # Quick breakdown of unclassified vs classified
    unclassified = sum(1 for h in final_hosts if classify(h).startswith("Unclassified"))
    classified = written - unclassified
    info(f"Classified: {classified} | Unclassified: {unclassified}")
    info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
