#!/usr/bin/env python3.12
"""Build the map-only LinkedIn carousel on the 2026 State of the Union (speech and debate).

Ten slides, 1080x1350, every slide a map. Style brief from Victor (16 September 2026):
"really visible", in the manner of The World in Maps: whole countries coloured, big
labels inside the countries with the number, the title over the sea, big legend swatches.

WHAT IS COUNTED (the two sides use different units, and every legend says which)
- Von der Leyen: occurrences of the place's NAME in the published speech text
  (speech_en.txt, SPEECH/26/1868). This is the count behind the already-published
  speech carousel ("Ukraine is named 14 times, Canada 7"). A place referred to only by
  an adjective is not counted: "American Patriot interceptor missiles" does not name
  the United States, "North Korean missiles" does not name North Korea.
- MEPs: the number of debate SPEECHES naming the place (debate_analysis.json
  place_frequency), from Brubru's recording of the English interpretation.
- Places named as a group (Western Balkans, Mercosur) colour their member countries
  and carry one label. Cities, sites, rivers and seas are pins.
- "Brussels" (standing for the EU institutions), "Africa", "Arab world" and "Soviet
  Union" are not mapped.

Inputs (backend/data/soteu_2026/, not tracked): speech_en.txt, places.json,
debate_analysis.json, geo/countries-50m.json, geo/debate_regions.geojson (Natural Earth
admin-1 subset). Group logos: frontend/public/assets/political_groups/.

Usage: python3.12 scripts/build_soteu_2026_maps_deck.py
Output: docs/marketing/designs/soteu_2026_maps_deck.html / .pdf / _slides/
"""

from __future__ import annotations

import base64
import collections
import json
import pathlib
import re
import shutil
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = _REPO_ROOT / "backend/data/soteu_2026"
ASSETS = _REPO_ROOT / "frontend/public/assets"
OUT = _REPO_ROOT / "docs/marketing/designs/soteu_2026_maps_deck.html"

# Sequential ramps (light to dark, one hue each): purple for her, orange for MEPs.
HER_RAMP = ["#e6d9fa", "#c9a9f2", "#a174e3", "#7a43cf", "#4c1d96"]
MEP_RAMP = ["#fde2c6", "#f8b97a", "#f08a3a", "#cf5f10", "#8f3a05"]
# Who named it. Colour-blind separation passes on ALL pairs (validate_palette.js
# --pairs all, worst deltaE 25); the dark "both" colour sits outside the categorical
# lightness band on purpose (overlap reads as the strongest state), and every country
# carries a text label, so colour is never the only carrier.
WHO = {"her": "#5aaef0", "meps": "#e8702a", "both": "#2b2f7a"}
# Subject of her mentions (validated categorical slots used on the speech carousel).
SPLIT = "#8e98a6"
THEME = {"partners": ("Economy, AI and partners", "#2a78d6"),
         "climate": ("Climate and preparedness", "#eb6834"),
         "security": ("Security, borders and democracy", "#1baf7a")}

TOPO_NAME = {"United States": "United States of America", "Bosnia and Herzegovina": "Bosnia and Herz.",
             "North Macedonia": "Macedonia"}
GROUP_FILLS = {"Western Balkans": ["Serbia", "Montenegro", "Albania", "Macedonia", "Bosnia and Herz.", "Kosovo"],
               "Mercosur": ["Argentina", "Brazil", "Paraguay", "Uruguay"]}
NOT_NAMED_BY_HER = {"United States", "North Korea"}  # adjective only, see docstring
NOT_MAPPED = {"Brussels", "Africa", "Arab world", "Soviet Union"}
DEBATE_REGIONS = ["Catalonia", "Galicia", "Valencia", "Balearic Islands", "Brittany", "Corsica",
                  "Saxony-Anhalt", "Northern Ireland"]
PIN_COORDS = {  # debate places that are not countries
    "Ceuta": (35.89, -5.32), "Gaza": (31.42, 34.37), "West Bank": (32.0, 35.25), "Lampedusa": (35.51, 12.6),
    "Leipzig": (51.34, 12.37), "Larnaca": (34.92, 33.63), "Paphos": (34.77, 32.42), "Srebrenica": (44.1, 19.3),
    "Gibraltar": (36.14, -5.35), "Rome": (41.9, 12.5), "Washington": (38.9, -77.04),
    "Lake Ontario": (43.7, -77.9), "Arctic": (78.0, 20.0), "Middle East": (31.5, 44.0), "Baltic": (57.0, 19.0),
    "Vatican": (41.9, 12.45),
}
GROUP_LOGO = {"EPP": "epp", "S&D": "sd", "PfE": "patriots", "ECR": "ecr", "Renew": "renew",
              "Greens/EFA": "greens_efa", "The Left": "the_left", "ESN": "esn", "Non-attached": "non_attached"}


def b64(path: pathlib.Path, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def ramp_colour(value: int, cuts: list[int], ramp: list[str]) -> str:
    """cuts are the lower bounds of each ramp step, e.g. [1, 2, 3, 5, 7]."""
    idx = 0
    for i, c in enumerate(cuts):
        if value >= c:
            idx = i
    return ramp[idx]


def load_data() -> dict:
    speech = (DATA / "speech_en.txt").read_text(encoding="utf-8")
    places = json.loads((DATA / "places.json").read_text(encoding="utf-8"))["places"]
    debate = json.loads((DATA / "debate_analysis.json").read_text(encoding="utf-8"))

    def name_count(term: str) -> int:
        return len(re.findall(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", speech))

    her_countries: dict[str, dict] = {}
    her_groups: list[dict] = []
    her_pins: list[dict] = []
    alias = {"Gaza and the West Bank": ["Gaza", "West Bank"], "The Arctic": ["Arctic"], "The Alps": ["Alps"],
             "Strait of Hormuz": ["Hormuz"], "Rhine": ["Rhein"], "Garonne": ["Garonne"],
             "Eiffel Tower": ["Tour Eiffel"], "Rio de Janeiro": ["Rio"], "Greek islands": ["islands of Greece"],
             "Croatian islands": ["Croatia"]}
    for p in places:
        name, kind = p["name"], p["kind"]
        if name in NOT_NAMED_BY_HER:
            continue
        n = sum(name_count(t) for t in alias.get(name, [name]))
        themes = collections.Counter(m["theme"] for m in p["mentions"]).most_common()
        # A tie is shown as its own category, never resolved by mention order.
        theme = "split" if len(themes) > 1 and themes[0][1] == themes[1][1] else themes[0][0]
        if kind == "country" or name == "Greenland":
            her_countries[TOPO_NAME.get(name, name)] = {"label": name, "n": n, "theme": theme}
        elif name in GROUP_FILLS:
            her_groups.append({"label": name, "n": n, "fills": GROUP_FILLS[name], "theme": theme,
                               "lat": p["lat"], "lon": p["lon"]})
        elif name in ("Croatian islands", "Greek islands"):
            continue  # "islands of Greece and Croatia": counted on the country, see Croatia below
        else:
            her_pins.append({"label": name, "n": n, "lat": p["lat"], "lon": p["lon"], "theme": theme})
    her_countries.setdefault("Croatia", {"label": "Croatia", "n": name_count("Croatia"), "theme": "climate"})
    her_countries.setdefault("Israel", {"label": "Israel", "n": name_count("Israel"), "theme": "security"})

    freq = debate["place_frequency"]
    by_group = collections.defaultdict(collections.Counter)
    for pl in debate["places"]:
        by_group[pl["place"]][pl["group"]] += 1
    topo = json.loads((DATA / "geo/countries-50m.json").read_text())
    topo_names = {g["properties"]["name"] for g in topo["objects"]["countries"]["geometries"]}
    mep_countries, mep_pins, mep_regions, unmapped = {}, [], {}, []
    for name, n in freq.items():
        if name in NOT_MAPPED:
            continue
        tn = TOPO_NAME.get(name, name)
        if name in DEBATE_REGIONS:
            mep_regions[name] = n
        elif name in PIN_COORDS and name != "Vatican":
            lat, lon = PIN_COORDS[name]
            mep_pins.append({"label": name, "n": n, "lat": lat, "lon": lon})
        elif tn in topo_names:
            mep_countries[tn] = {"label": name, "n": n}
        else:
            unmapped.append(name)
    if unmapped:
        sys.exit(f"[ERROR] debate places with no geometry or pin: {unmapped}")
    missing = [k for k in her_countries if k not in topo_names]
    if missing:
        sys.exit(f"[ERROR] speech countries not in the topology: {missing}")
    return {"her_countries": her_countries, "her_groups": her_groups, "her_pins": her_pins,
            "mep_countries": mep_countries, "mep_pins": mep_pins, "mep_regions": mep_regions,
            "by_group": {k: dict(v) for k, v in by_group.items()}, "freq": freq}


EUROPE = {"type": "azimuthal", "europe": True, "rotate": [-9, -51],
          "extent": [[-24, 65], [-11, 34], [37, 31], [46, 58], [26, 71]]}
GROUPS_VIEW = {"type": "azimuthal", "europe": True, "rotate": [-6, -51],
               "extent": [[-40, 62], [-30, 36], [37, 31], [46, 58], [26, 71]]}
WORLD_COUNTRIES = ["Canada", "United States of America", "Mexico", "Cuba", "Brazil", "Argentina", "Paraguay",
                   "Uruguay", "China", "Japan", "India", "Indonesia", "Australia", "Iran", "United Arab Emirates"]
WORLD_PINS = ["Terrace", "Times Square", "Rio de Janeiro", "Tokyo", "Central Asia",
              "Washington", "Lake Ontario", "Mercosur"]
AMERICAS = {"type": "azimuthal", "rotate": [88, -12],
            "extent": [[-128, 62], [-95, 74], [-58, 58], [-36, -6], [-68, -52], [-112, 18]]}
ASIA = {"type": "azimuthal", "rotate": [-102, -14],
        "extent": [[42, 42], [142, 46], [152, -38], [114, -36], [50, 14]]}
WEST = {"type": "azimuthal", "rotate": [-3, -46],
        "extent": [[-10, 56], [14, 55], [14, 38], [-10, 35]]}


def slides_config(d: dict) -> list[dict]:
    her_c, mep_c = d["her_countries"], d["mep_countries"]
    her_cuts, mep_cuts = [1, 2, 3, 5, 7], [1, 2, 3, 5, 10]

    def her_fills(names=None):
        f = {}
        for tn, v in her_c.items():
            if names is None or tn in names:
                f[tn] = {"color": ramp_colour(v["n"], her_cuts, HER_RAMP), "label": f"{v['label']} {v['n']}", "n": v["n"]}
        for g in d["her_groups"]:
            for tn in g["fills"]:
                f.setdefault(tn, {"color": ramp_colour(g["n"], her_cuts, HER_RAMP), "label": None})
        return f

    def her_group_labels():
        return [{"label": f"{g['label']} {g['n']}", "lat": g["lat"], "lon": g["lon"]} for g in d["her_groups"]]

    def mep_fills():
        return {tn: {"color": ramp_colour(v["n"], mep_cuts, MEP_RAMP), "label": f"{v['label']} {v['n']}", "n": v["n"]}
                for tn, v in mep_c.items()}

    minor = {"High Fens", "The Alps", "Danube", "Rhine", "Garonne", "Mediterranean", "Middle East"}
    her_pins = [{"label": f"{p['label']} {p['n']}", "n": p["n"], "lat": p["lat"], "lon": p["lon"], "color": "#4c1d96"}
                for p in d["her_pins"] if p["label"] not in minor]
    minor_note = ", ".join(f"{p['label'].replace('The ', 'the ')} ({p['n']})" for p in d["her_pins"] if p["label"] in minor)
    mep_pins = [{"label": f"{p['label']} {p['n']}", "n": p["n"], "lat": p["lat"], "lon": p["lon"], "color": "#8f3a05"}
                for p in d["mep_pins"]]
    world = set(WORLD_COUNTRIES) | set(WORLD_PINS) | {"Strait of Hormuz"}
    her_once = sorted([v["label"] for tn, v in her_c.items() if v["n"] == 1 and tn not in world]
                      + [p["label"] for p in d["her_pins"] if p["n"] == 1 and p["label"] not in world and p["label"] not in minor])
    mep_once = sorted([v["label"] for tn, v in mep_c.items() if v["n"] == 1 and tn not in world]
                      + [p["label"] for p in d["mep_pins"] if p["n"] == 1 and p["label"] not in world])
    her_legend = [{"color": c, "label": l} for c, l in zip(HER_RAMP, ["1", "2", "3 or 4", "5 or 6", "7 or more"])]
    mep_legend = [{"color": c, "label": l} for c, l in zip(MEP_RAMP, ["1", "2", "3 or 4", "5 to 9", "10 or more"])]

    her_set = set(her_c) | {tn for g in d["her_groups"] for tn in g["fills"]}
    if "Palestine" not in her_set:
        her_set.add("Palestine")  # "Gaza and the West Bank" is named four times
    mep_set = set(mep_c)
    both = her_set & mep_set
    who_fills = {}
    for tn in her_set | mep_set:
        key = "both" if tn in both else ("her" if tn in her_set else "meps")
        label = (her_c.get(tn) or mep_c.get(tn) or {}).get("label")
        who_fills[tn] = {"color": WHO[key], "label": label}
    all_named = {tn: {"color": "#6d3fc9", "label": None} for tn in her_set | mep_set}

    theme_fills = {tn: {"color": (SPLIT if v["theme"] == "split" else THEME[v["theme"]][1]), "label": v["label"]}
                   for tn, v in her_c.items()}
    for g in d["her_groups"]:
        for tn in g["fills"]:
            theme_fills.setdefault(tn, {"color": THEME[g["theme"]][1], "label": None})

    cards = []
    for place, pos in (("Canada", "canada"), ("Iceland", "iceland"), ("Ceuta", "ceuta"), ("Ukraine", "ukraine")):
        groups = sorted(d["by_group"][place].items(), key=lambda kv: (-kv[1], kv[0]))
        cards.append({"place": place, "n": d["freq"][place], "pos": pos,
                      "chips": [{"group": g, "n": n, "logo": GROUP_LOGO.get(g)} for g, n in groups]})

    counted_her = "Times each place is named in the published speech"
    counted_mep = "Debate speeches naming each place (78 in total)"
    return [
        {"kind": "cover", "title": "Where the State of the Union went",
         "sub": "Every country named on 16 September 2026, by von der Leyen or by MEPs in the debate",
         "panels": [{"proj": EUROPE, "fills": all_named}], "legend": None,
         "note": "Europe and its neighbours. Canada, the United States and Asia follow."},
        {"kind": "map", "title": "Her speech: Europe", "sub": counted_her,
         "panels": [{"proj": EUROPE, "fills": her_fills(), "pins": her_pins, "label_min": 2}],
         "legend": {"title": "Times named", "items": her_legend},
         "note": f"<b>Named once:</b> {', '.join(her_once)}; the Western Balkans. <b>Also:</b> {minor_note}."},
        {"kind": "map", "title": "Her speech: the world", "sub": counted_her,
         "panels": [{"proj": AMERICAS, "name": "The Americas", "fills": her_fills(), "group_labels": her_group_labels(), "pins": her_pins,
                     "only": WORLD_COUNTRIES, "onlyPins": WORLD_PINS},
                    {"proj": ASIA, "name": "Asia and the Pacific", "fills": her_fills(), "pins": her_pins,
                     "only": WORLD_COUNTRIES, "onlyPins": WORLD_PINS}],
         "legend": {"title": "Times named", "items": her_legend}, "note": "<b>Also named:</b> the Strait of Hormuz (1)."},
        {"kind": "map", "title": "What she talked about, where", "sub": "Each country coloured by the subject of most of its mentions",
         "panels": [{"proj": EUROPE, "fills": theme_fills, "max_r": 1}],
         "legend": {"title": "Subject", "items": [{"color": c, "label": l} for l, c in THEME.values()]
                    + [{"color": SPLIT, "label": "Two subjects equally"}]},
         "note": "Off the map: Canada, China, India, Indonesia and Mercosur were economy, AI and partners; Australia was split between trade and security."},
        {"kind": "map", "title": "The debate: Europe", "sub": counted_mep,
         "panels": [{"proj": EUROPE, "fills": mep_fills(), "pins": mep_pins, "label_min": 2, "max_r": 1}],
         "legend": {"title": "Speeches", "items": mep_legend},
         "note": f"<b>Named in one speech:</b> {', '.join(mep_once)}."},
        {"kind": "map", "title": "The debate: the world", "sub": counted_mep,
         "panels": [{"proj": AMERICAS, "name": "The Americas", "fills": mep_fills(), "pins": mep_pins,
                     "only": WORLD_COUNTRIES, "onlyPins": WORLD_PINS, "pin_min": 2},
                    {"proj": ASIA, "name": "Asia and the Pacific", "fills": mep_fills(), "pins": mep_pins,
                     "only": WORLD_COUNTRIES, "onlyPins": WORLD_PINS, "pin_min": 2, "max_r": 1,
                     "noLabel": ["United Arab Emirates"]}],
         "legend": {"title": "Speeches", "items": mep_legend},
         "note": "<b>Also named once:</b> Washington, Lake Ontario, the United Arab Emirates."},
        {"kind": "map", "title": "Her map and Parliament's", "sub": "Who named each country",
         "panels": [{"proj": EUROPE, "fills": who_fills, "max_r": 1}],
         "legend": {"title": "Named by", "items": [{"color": WHO["her"], "label": "Von der Leyen only"},
                                                  {"color": WHO["meps"], "label": "MEPs only"},
                                                  {"color": WHO["both"], "label": "Both"}]},
         "note": "Includes countries she named as a group (Western Balkans)."},
        {"kind": "regions", "title": "Regions MEPs named", "sub": "None of them is in her speech",
         "panels": [{"proj": WEST, "fills": {}, "regions": d["mep_regions"]}],
         "legend": {"title": "Speeches", "items": [{"color": MEP_RAMP[2], "label": "1"}, {"color": MEP_RAMP[4], "label": "2"}]},
         "note": "Six came from one Greens/EFA speech on regions ready to build Europe. Saxony-Anhalt: its election result. Northern Ireland: John Hume's peace legacy."},
        {"kind": "groups", "title": "Who named where", "sub": "Debate speeches by political group",
         "panels": [{"proj": GROUPS_VIEW, "fills": {"Iceland": {"color": MEP_RAMP[2], "label": None},
                                                    "Ukraine": {"color": MEP_RAMP[4], "label": None}},
                     "pins": [{"label": "", "key": "ceuta", "lat": 35.89, "lon": -5.32, "color": "#8f3a05"},
                              {"label": "", "key": "iceland", "lat": 64.9, "lon": -18.6, "color": "#8f3a05"},
                              {"label": "", "key": "ukraine", "lat": 49.0, "lon": 31.4, "color": "#8f3a05"}]}],
         "cards": cards, "legend": None,
         "note": "Not attributed: catch-the-eye speakers whose group could not be confirmed."},
        {"kind": "close", "title": "Ask Brubru where Europe is looking",
         "sub": "The speech, the debate and every place named, in six languages",
         "panels": [{"proj": EUROPE, "fills": all_named}], "legend": None, "note": ""},
    ]


PAGE_JS = r"""
const W=1080, H=1350, FOOT=100;
function projFor(p, box){
  const pr=d3.geoAzimuthalEqualArea().rotate(p.rotate).clipAngle(90);
  pr.fitExtent([[box.x+16,box.y+16],[box.x+box.w-16,box.y+box.h-16]],{type:"MultiPoint",coordinates:p.extent});
  pr.clipExtent([[box.x,box.y],[box.x+box.w,box.y+box.h]]);
  return pr;
}
function overlaps(a,b){return a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;}
function rel(root,e,pad){const r=e.getBoundingClientRect(), o=root.getBoundingClientRect(); return {x:r.left-o.left-pad,y:r.top-o.top-pad,w:r.width+2*pad,h:r.height+2*pad};}
function render(slide, i){
  const root=document.getElementById("s"+i);
  root.querySelectorAll("svg.map").forEach(e=>e.remove());
  const head=root.querySelector(".head"); const hb=rel(root,head,0);
  const top=Math.round(hb.y+hb.h+14);
  const svg=d3.select(root).insert("svg",":first-child").attr("width",W).attr("height",H-FOOT).attr("class","map");
  svg.append("rect").attr("width",W).attr("height",H-FOOT).attr("fill","#dbe8f3");
  const reserved=Array.from(root.querySelectorAll(".reserve")).map(e=>rel(root,e,8));
  const placed=[...reserved]; const dropped=[]; const anchors={};
  const nPanels=slide.panels.length;
  const noteEl=root.querySelector(".note"); const bottom = noteEl ? rel(root,noteEl,0).y-8 : H-FOOT;
  slide.panels.forEach((panel,pi)=>{
    const gy = nPanels===1 ? top : top+60;
    const box = nPanels===1 ? {x:0,y:top,w:W,h:bottom-top} : {x:pi*W/2,y:gy,w:W/2,h:bottom-gy};
    const clipId=`c${i}_${pi}`;
    svg.append("clipPath").attr("id",clipId).append("rect").attr("x",box.x).attr("y",box.y).attr("width",box.w).attr("height",box.h);
    const g=svg.append("g").attr("clip-path",`url(#${clipId})`);
    const pr=projFor(panel.proj, box); const path=d3.geoPath(pr);
    g.append("path").attr("d",path(d3.geoGraticule10())).attr("fill","none").attr("stroke","#c9d9e8").attr("stroke-width",1);
    const fills=panel.fills||{};
    g.selectAll("path.c").data(COUNTRIES).join("path").attr("class","c").attr("d",path)
      .attr("fill",f=>fills[f.properties.name]?fills[f.properties.name].color:"#e4e7ec")
      .attr("stroke","#9aa5b1").attr("stroke-width",0.9);
    if(panel.regions){
      g.selectAll("path.r").data(REGIONS.features.filter(f=>f.properties.region!=="Ceuta")).join("path").attr("class","r").attr("d",path)
        .attr("fill",f=>(panel.regions[f.properties.region]||1)>=2?MEP_RAMP[4]:MEP_RAMP[2]).attr("stroke","#8f3a05").attr("stroke-width",1.4);
    }
    if(nPanels>1){
      svg.append("line").attr("x1",W/2).attr("x2",W/2).attr("y1",box.y).attr("y2",box.y+box.h).attr("stroke","#fff").attr("stroke-width",8);
      const t=svg.append("text").attr("class","panel").attr("x",box.x+box.w/2).attr("y",box.y-16).attr("text-anchor","middle").text(panel.name.toUpperCase());
    }
    const inBox=(x,y)=>x>=box.x+4&&x<=box.x+box.w-4&&y>=box.y+4&&y<=box.y+box.h-4;
    const labels=[];
    COUNTRIES.forEach(f=>{
      const v=fills[f.properties.name]; if(!v||!v.label) return;
      if(panel.label_min && (v.n||0)<panel.label_min) return;
      if(panel.noLabel && panel.noLabel.includes(f.properties.name)) return;
      if(panel.proj.europe && WORLD.includes(f.properties.name)) return;
      if(panel.only && !panel.only.includes(f.properties.name)) return;
      let geom=f; if(f.geometry.type==="MultiPolygon"){
        let best=null,ba=-1; f.geometry.coordinates.forEach(c=>{const pg={type:"Polygon",coordinates:c}; const a=d3.geoArea(pg); if(a>ba){ba=a;best=pg;}}); geom=best;}
      let [x,y]=path.centroid(geom); if(!isFinite(x)||!inBox(x,y)){ if(nPanels>1||path.area(f)<20000) return; [x,y]=path.centroid(f); if(!isFinite(x)||!inBox(x,y)) return; }
      labels.push({text:v.label.toUpperCase(),x,y,area:path.area(geom),kind:"country"});
    });
    (panel.group_labels||[]).forEach(l=>{if(panel.onlyPins&&!panel.onlyPins.includes(l.label.replace(/ \d+$/,'')))return; const p=pr([l.lon,l.lat]); if(p&&inBox(p[0],p[1])) labels.push({text:l.label.toUpperCase(),x:p[0],y:p[1],area:1e5,kind:"group"});});
    if(panel.regions){
      const byR={}; REGIONS.features.forEach(f=>{const r=f.properties.region; (byR[r]=byR[r]||[]).push(f);});
      Object.entries(byR).forEach(([r,fs])=>{if(r==="Ceuta")return; const fc={type:"FeatureCollection",features:fs}; const [x,y]=path.centroid(fc); if(inBox(x,y)) labels.push({text:(r+" "+(panel.regions[r]||"")).toUpperCase(),x,y,area:path.area(fc),kind:"region"});});
    }
    const pins=(panel.pins||[]).filter(p=>!panel.onlyPins||panel.onlyPins.includes(p.label.replace(/ \d+$/,''))).filter(p=>!(panel.pin_min||panel.label_min)||(p.n||0)>=(panel.pin_min||panel.label_min)).map(p=>{const xy=pr([p.lon,p.lat]); return xy&&inBox(xy[0],xy[1])?{...p,x:xy[0],y:xy[1]}:null;}).filter(Boolean);
    const pinLayer=svg.append("g");
    pins.forEach(p=>{pinLayer.append("circle").attr("cx",p.x).attr("cy",p.y).attr("r",12).attr("fill",p.color).attr("stroke","#fff").attr("stroke-width",4);
      placed.push({x:p.x-14,y:p.y-14,w:28,h:28}); if(p.key) anchors[p.key]=[p.x,p.y];
      if(p.label) labels.push({text:p.label.toUpperCase(),x:p.x,y:p.y,area:0,kind:"pin"});});
    labels.sort((a,b)=>(b.kind==="country")-(a.kind==="country")||b.area-a.area);
    const lineLayer=svg.insert("g",".lblLayer"); const layer=svg.append("g").attr("class","lblLayer");
    labels.forEach(l=>{
      const size = l.kind==="country" ? (l.area>2500?36:32) : 30;
      const t=layer.append("text").attr("class","lbl").style("font-size",size+"px").text(l.text);
      const bb=t.node().getBBox(); const w=bb.width, h=size*1.02;
      const cands=[];
      if(l.kind==="pin"){ [[18,0,"start"],[-18,0,"end"],[0,-26,"middle"],[0,40,"middle"]].forEach(c=>cands.push([...c,false])); }
      else if(l.area>2500){ [[0,0],[0,-h],[0,h]].forEach(c=>cands.push([c[0],c[1],"middle",false])); }
      for(const r of (panel.max_r?[45,65,85,105,130]:[45,65,85,95])) for(let a=0;a<360;a+=15){
        const rad=a*Math.PI/180; const dx=Math.cos(rad)*r, dy=Math.sin(rad)*r;
        cands.push([dx,dy,dx>w/2?"start":(dx<-w/2?"end":"middle"),true]);
      }
      let ok=null;
      for(const [dx,dy,anchor,lead] of cands){
        const x=l.x+dx, y=l.y+dy+size*0.36;
        const bx = anchor==="middle" ? x-w/2 : anchor==="start" ? x : x-w;
        const b={x:bx-3,y:y-size*0.8,w:w+6,h:h};
        if(b.x<box.x+6||b.x+b.w>box.x+box.w-6||b.y<box.y+6||b.y+b.h>box.y+box.h-6) continue;
        if(placed.some(o=>overlaps(o,b))) continue;
        ok={x,y,anchor,b,lead}; break;
      }
      if(!ok){ t.remove(); dropped.push(l.text+(nPanels>1?" [panel "+pi+" at "+Math.round(l.x)+","+Math.round(l.y)+"]":"")); return; }
      t.attr("x",ok.x).attr("y",ok.y).attr("text-anchor",ok.anchor); placed.push(ok.b);
      if(ok.lead){
        const cx=Math.max(ok.b.x,Math.min(l.x,ok.b.x+ok.b.w)), cy=Math.max(ok.b.y,Math.min(l.y,ok.b.y+ok.b.h));
        lineLayer.append("line").attr("x1",l.x).attr("y1",l.y).attr("x2",cx).attr("y2",cy).attr("stroke","#111827").attr("stroke-width",2.5);
        lineLayer.append("circle").attr("cx",l.x).attr("cy",l.y).attr("r",l.kind==="pin"?0:5).attr("fill","#111827");
      }
    });
  });
  // connectors from group cards to their places
  root.querySelectorAll(".card[data-key]").forEach(c=>{
    const a=anchors[c.dataset.key]; if(!a) return; const b=rel(root,c,0);
    const cx=Math.max(b.x,Math.min(a[0],b.x+b.w)), cy=Math.max(b.y,Math.min(a[1],b.y+b.h));
    svg.append("line").attr("x1",a[0]).attr("y1",a[1]).attr("x2",cx).attr("y2",cy).attr("stroke","#111827").attr("stroke-width",4);
  });
  window.DROPPED=window.DROPPED||{}; window.DROPPED[i+1]=dropped; window.ANCHORS=window.ANCHORS||{}; window.ANCHORS[i+1]=anchors;
}
document.fonts.ready.then(()=>{SLIDES.forEach((s,i)=>render(s,i)); document.title="ready";});
"""

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#2e3037;font-family:'Archivo',system-ui,sans-serif}
.slide{position:relative;width:1080px;height:1350px;margin:24px auto;background:#dbe8f3;overflow:hidden}
.map{position:absolute;left:0;top:0}
.lbl{font-family:'Archivo Black','Archivo',sans-serif;fill:#111827;paint-order:stroke;stroke:#fff;stroke-width:9px;stroke-linejoin:round;letter-spacing:.01em}
.panel{font-family:'Archivo Black',sans-serif;font-size:34px;fill:#111827;paint-order:stroke;stroke:#fff;stroke-width:9px}
.head{position:absolute;left:44px;top:36px;right:44px;z-index:3}
.head .ov{font-family:'Archivo Black',sans-serif;font-size:30px;letter-spacing:.06em;color:#4c1d96;text-transform:uppercase}
.head h1{font-family:'Adobe Caslon Pro',Georgia,serif;font-weight:700;font-size:92px;line-height:1.02;color:#0b1020;margin-top:6px;
}
.head .sub{display:inline-block;margin-top:12px;font-family:'Archivo',sans-serif;font-weight:700;font-size:34px;line-height:1.2;color:#1f2937;
  background:rgba(255,255,255,.88);padding:8px 14px;border-radius:6px;max-width:960px}
.legend{display:flex;flex-wrap:wrap;align-items:center;gap:8px 22px;margin-top:12px;background:rgba(255,255,255,.94);border-radius:8px;padding:10px 16px}
.legend .lt{font-family:'Archivo Black',sans-serif;font-size:30px;color:#111827;text-transform:uppercase;letter-spacing:.03em;margin-right:4px}
.legend .li{display:flex;align-items:center;gap:10px;font-family:'Archivo',sans-serif;font-weight:700;font-size:32px;color:#111827}
.legend .sw{width:42px;height:42px;border-radius:6px;border:2px solid rgba(0,0,0,.18);flex-shrink:0}
.note{position:absolute;z-index:3;left:44px;right:44px;bottom:112px;font-family:'Archivo',sans-serif;font-weight:700;font-size:30px;line-height:1.25;color:#1f2937;
  background:rgba(255,255,255,.9);padding:10px 16px;border-radius:6px}
.foot{position:absolute;left:0;right:0;bottom:0;height:100px;background:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 44px;z-index:4}
.foot .l{display:flex;align-items:center;gap:16px}
.foot img.i{height:46px}.foot img.b{height:60px}
.foot .w{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:27px;letter-spacing:.03em;color:#555;text-transform:uppercase}
.foot .by{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:24px;color:#777}
.foot .src{font-family:'Archivo',sans-serif;font-weight:700;font-size:22px;color:#555;text-align:right;max-width:430px;line-height:1.2}
.card{position:absolute;z-index:3;background:#fff;border-radius:12px;padding:16px 18px;box-shadow:0 4px 18px rgba(0,0,0,.18);width:486px}
.card .ct{font-family:'Archivo Black',sans-serif;font-size:36px;color:#111827;margin-bottom:10px}
.card .chips{display:flex;flex-wrap:wrap;gap:10px}
.chip{display:flex;align-items:center;gap:8px;border:2px solid #e5e7eb;border-radius:8px;padding:4px 10px 4px 4px}
.chip img{height:48px;display:block;border-radius:4px}
.chip .n{font-family:'Archivo Black',sans-serif;font-size:32px;color:#111827}
.chip .na{font-family:'Archivo',sans-serif;font-weight:800;font-size:30px;color:#374151;padding:6px 6px}
.close-cta{position:absolute;z-index:3;left:44px;bottom:150px;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:60px;color:#fff;background:#4c1d96;padding:16px 26px;border-radius:10px}
"""

LEGEND_POS = {"map": "left:44px;top:470px", "regions": "right:44px;top:300px"}
CARD_POS = {"canada": "right:24px;top:830px", "iceland": "left:24px;top:250px",
            "ceuta": "left:24px;top:650px", "ukraine": "right:24px;top:250px"}


def main() -> int:
    d = load_data()
    slides = slides_config(d)
    topo = json.loads((DATA / "geo/countries-50m.json").read_text())
    topo["objects"].pop("land", None)
    regions = json.loads((DATA / "geo/debate_regions.geojson").read_text())
    icon = b64(ASSETS / "brubru_icon_colours.png")
    beresol = b64(ASSETS / "beresol-logo_transparent.png")
    logos = {slug: b64(ASSETS / f"political_groups/{slug}_logo.png") for slug in set(GROUP_LOGO.values())}

    sections = []
    for i, s in enumerate(slides):
        legend = ""
        if s.get("legend"):
            items = "".join(f'<div class="li"><span class="sw" style="background:{it["color"]}"></span>{it["label"]}</div>'
                            for it in s["legend"]["items"])
            legend = f'<div class="legend"><span class="lt">{s["legend"]["title"]}</span>{items}</div>'
        cards = ""
        for c in s.get("cards", []):
            chips = ""
            for ch in c["chips"]:
                if ch["logo"]:
                    chips += f'<div class="chip"><img src="{logos[ch["logo"]]}" alt="{ch["group"]}"><span class="n">{ch["n"]}</span></div>'
                else:
                    chips += f'<div class="chip"><span class="na">Not attributed</span><span class="n">{ch["n"]}</span></div>'
            key = "" if c["place"] == "Canada" else f' data-key="{c["pos"]}"'
            cards += (f'<div class="card reserve"{key} style="{CARD_POS[c["pos"]]}"><div class="ct">{c["place"].upper()} {c["n"]}'
                      f'</div><div class="chips">{chips}</div></div>')
        note = f'<div class="note reserve">{s["note"]}</div>' if s.get("note") else ""
        if s["kind"] == "close":
            note = '<div class="close-cta reserve">brubru.beresol.eu</div>'
        overline = "State of the Union 2026 &middot; in maps"
        src = ("Sources: Commission published speech; European Parliament debate, "
               "Brubru recording") if s["kind"] != "close" else ""
        sections.append(f"""<section class="slide" id="s{i}">
  <div class="head reserve"><div class="ov">{overline}</div><h1>{s['title']}</h1><div class="sub">{s['sub']}</div>{legend}</div>
  {cards}{note}
  <div class="foot"><div class="l"><img class="i" src="{icon}" alt=""><span class="w">Brubru</span><span class="by">by</span><img class="b" src="{beresol}" alt="Beresol"></div>
  <div class="src">{src}<br><span style="font-family:'JetBrains Mono',monospace">{i+1:02d}/{len(slides):02d}</span></div></div>
</section>""")

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>State of the Union 2026 in maps - Brubru</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800&family=Archivo+Black&display=swap">
<style>{CSS}</style></head><body>
{''.join(sections)}
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>
<script>const TOPO={json.dumps(topo, separators=(',', ':'))};const REGIONS={json.dumps(regions, separators=(',', ':'))};
const SLIDES={json.dumps(slides, ensure_ascii=False)};const WORLD={json.dumps(WORLD_COUNTRIES)};const MEP_RAMP={json.dumps(MEP_RAMP)};
const COUNTRIES=topojson.feature(TOPO,TOPO.objects.countries).features.filter(f=>f.properties.name!=="Antarctica");</script>
<script>{PAGE_JS}</script></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {len(slides)} slides)")
    print("[INFO] her countries:", {v['label']: v['n'] for v in d['her_countries'].values()})
    print("[INFO] her pins:", {p['label']: p['n'] for p in d['her_pins']})
    return export(len(slides))


def export(n: int) -> int:
    from playwright.sync_api import sync_playwright
    from PIL import Image

    shots = OUT.parent / (OUT.stem + "_slides")
    if shots.exists():
        shutil.rmtree(shots)
    shots.mkdir(parents=True)
    code = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        pg.goto(OUT.as_uri())
        pg.wait_for_function("document.title==='ready'", timeout=120000)
        pg.wait_for_timeout(600)
        dropped = pg.evaluate("window.DROPPED")
        also = pg.evaluate("window.ALSO || {}")
        if also:
            print(f"[INFO] listed in the note instead of on the map: {also}")
        bad = {k: v for k, v in dropped.items() if v}
        if bad:
            print(f"[ERROR] labels still unplaced after the note was added: {bad}")
            code = 1
        else:
            print(f"[OK] every label is on the map or listed in its slide note ({n} slides)")
        clip = pg.evaluate("""Array.from(document.querySelectorAll('section.slide')).map((s,i)=>{
          const o=s.getBoundingClientRect(); const bad=[];
          s.querySelectorAll('.head,.legend,.note,.card,.close-cta').forEach(e=>{const r=e.getBoundingClientRect();
            if(r.right>o.right+1||r.bottom>o.bottom-100+1||r.left<o.left-1||r.top<o.top-1) bad.push(e.className);});
          return {i:i+1,bad};}).filter(x=>x.bad.length)""")
        if clip:
            print(f"[ERROR] overlay outside the map area: {clip}")
            code = 1
        for i in range(n):
            el = pg.locator("section.slide").nth(i)
            el.scroll_into_view_if_needed()
            pg.wait_for_timeout(100)
            el.screenshot(path=str(shots / f"slide_{i + 1:02d}.png"))
        b.close()
    imgs = [Image.open(x).convert("RGB") for x in sorted(shots.glob("slide_*.png"))]
    pdf = OUT.with_suffix(".pdf")
    imgs[0].save(str(pdf), save_all=True, append_images=imgs[1:], resolution=150.0)
    print(f"[OK] {pdf} ({pdf.stat().st_size / 1e6:.2f} MB, {len(imgs)} pages)")
    return code


if __name__ == "__main__":
    sys.exit(main())
