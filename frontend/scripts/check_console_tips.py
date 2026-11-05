#!/usr/bin/env python3.12
"""Every field the console can show, on every route, in every language: does it have a label and a plain tip, in that language?
A new field with no tip still works: its tip shows the route's English words. Run after adding a filter; write the tip in all six.

    python3.12 frontend/scripts/check_console_tips.py
"""
import json, pathlib, ssl, urllib.request, certifi
L = pathlib.Path(__file__).resolve().parents[1] / "src/i18n/locales"
ctx = ssl.create_default_context(cafile=certifi.where())
spec = json.load(urllib.request.urlopen("https://brubru-production.up.railway.app/api/v2/openapi.json", timeout=120, context=ctx))
HIDDEN = {"format", "force_recompute", "refresh"}
fields = {}
routes = 0
for p, item in spec["paths"].items():
    o = item.get("get")
    if not o:
        continue
    routes += 1
    for prm in o.get("parameters", []):
        if prm.get("in") in ("query", "path") and prm["name"] not in HIDDEN:
            fields.setdefault(prm["name"], 0)
            fields[prm["name"]] += 1
print("routes", routes, "distinct fields", len(fields), "uses", sum(fields.values()))
en = json.loads((L / "en.json").read_text())["api"]["console"]["fields"]
for lang in ("en", "fr", "nl", "es", "ca", "it"):
    f = json.loads((L / f"{lang}.json").read_text())["api"]["console"]["fields"]
    no_label = [k for k in fields if not (f.get(k) or {}).get("label")]
    no_help = [k for k in fields if not (f.get(k) or {}).get("help")]
    same = [k for k in fields if lang != "en" and (f.get(k) or {}).get("help") and f[k]["help"] == en[k]["help"]]
    print(lang, "no label", len(no_label), no_label[:6], "| no tip", len(no_help), no_help[:6], "| tip same as English", len(same), same[:6])
