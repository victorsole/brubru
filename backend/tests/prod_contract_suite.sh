#!/bin/zsh
# Production contract suite for the API v2 news/economy surfaces.
#
# Probes PRODUCTION and the live DB, not a local uvicorn: the fixes it covers are
# only real once Railway serves them, and a green local run proved nothing
# (feedback_deploy_tip_must_contain_the_fix).
#
# Run it after every deploy that touches these surfaces:
#     zsh backend/tests/prod_contract_suite.sh
# Exit 0 = all pass, 1 = at least one failure, 2 = the suite ran no checks.
#
# What it holds to account, beyond the individual fixes:
#   * the five-datapoint contract -- every news row in BOTH stores carries
#     body_txt and body_html, and no error page is stored as a body;
#   * date-window aliases (from/to and since/until must agree, or a caller
#     silently gets the unfiltered corpus);
#   * /news/latest as an honest instrument -- causes distinguished, counts summing
#     to the total, per-body threshold separate from the corpus one.
#
# Assertions are INVARIANTS, never the row count of the moment. An earlier version
# asserted "ombudsman honestly undated" and would have begun failing the moment the
# ombudsman fix worked.
B=https://brubru-production.up.railway.app
BACKEND="${0:A:h:h}"   # <repo>/backend, derived from this file
ENVF="$BACKEND/.env"
KEY=$(grep '^BRUBRU_API_KEY=' $ENVF | cut -d= -f2-)
DB=$(grep '^DATABASE_URL=' $ENVF | cut -d= -f2-)
H1="Authorization: Bearer $KEY"; H2="X-Brubru-Probe: 1"

PASS=0; FAIL=0
t() { if [[ "$2" == "$3" ]]; then echo "  PASS  $1  ($3)"; PASS=$((PASS+1));
      else echo "  FAIL  $1  expected=$2 got=$3"; FAIL=$((FAIL+1)); fi }
ge() { if (( $3 >= $2 )); then echo "  PASS  $1  ($3 >= $2)"; PASS=$((PASS+1));
       else echo "  FAIL  $1  ($3 < $2)"; FAIL=$((FAIL+1)); fi }
tot() { curl -s --max-time 60 -H "$H1" -H "$H2" "$B$1" | python3.12 -c "import sys,json;print(json.load(sys.stdin).get('total'))"; }
jq_() { curl -s --max-time 60 -H "$H1" -H "$H2" "$B$1" | python3.12 -c "import sys,json;d=json.load(sys.stdin);print($2)"; }
q()  { psql "$DB" -tAX -c "$1" 2>/dev/null | tr -d ' '; }

# Do not start through a container restart: the last run hit the 4809109b deploy
# window and 20 checks reported empty because prod was 502, which reads exactly like
# a broken fix. Wait for two consecutive healthy probes first.
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  a=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$B/health")
  sleep 3
  b=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$B/health")
  [[ "$a" == "200" && "$b" == "200" ]] && break
  echo "  waiting for production to be healthy (got $a/$b)"; sleep 20
done
echo "target: PRODUCTION + live DB   commit: $(cd /Users/victorsole/Developer/brubru && git log --oneline -1 | cut -c1-8)"
echo ""
echo "--- FIX 1: date-window aliases (both spellings must agree) ---"
t "news/all      from/to == since/until" "$(tot '/api/v2/news/all?from=2026-09-01&to=2026-09-08&limit=1')" "$(tot '/api/v2/news/all?since=2026-09-01&until=2026-09-08&limit=1')"
t "cedefop/news  since == from"          "$(tot '/api/v2/cedefop/news?since=2026-09-01&limit=1')" "$(tot '/api/v2/cedefop/news?from=2026-09-01&limit=1')"
t "consult/all   from == since"          "$(tot '/api/v2/consultations/all?from=2026-09-01&limit=1')" "$(tot '/api/v2/consultations/all?since=2026-09-01&limit=1')"
t "events/all    from/to == since/until" "$(tot '/api/v2/events/all?from=2026-09-01&to=2026-09-08&limit=1')" "$(tot '/api/v2/events/all?since=2026-09-01&until=2026-09-08&limit=1')"
t "explicit from/to wins over since/until" "$(tot '/api/v2/news/all?from=2026-09-01&to=2026-09-08&limit=1')" "$(tot '/api/v2/news/all?from=2026-09-01&to=2026-09-08&since=2000-01-01&until=2030-01-01&limit=1')"
UNF=$(tot '/api/v2/cedefop/news?limit=1'); WIN=$(tot '/api/v2/cedefop/news?since=2026-09-01&limit=1')
if (( WIN < UNF )); then echo "  PASS  window really filters ($WIN of $UNF)"; PASS=$((PASS+1)); else echo "  FAIL  window did not filter ($WIN of $UNF)"; FAIL=$((FAIL+1)); fi

echo ""
echo "--- FIX 2: query guard ---"
t "unknown param still 200"  "200" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 -H "$H1" -H "$H2" "$B/api/v2/news/all?nonsense=1&limit=1")"
t "warn header names it"     "nonsense" "$(curl -s -D - -o /dev/null --max-time 60 -H "$H1" -H "$H2" "$B/api/v2/news/all?nonsense=1&limit=1" | grep -i '^x-brubru-unknown-params' | tr -d '\r' | cut -d' ' -f2)"
t "two unknowns listed"      "alsobad,nonsense" "$(curl -s -D - -o /dev/null --max-time 60 -H "$H1" -H "$H2" "$B/api/v2/news/all?nonsense=1&alsobad=2&limit=1" | grep -i '^x-brubru-unknown-params' | tr -d '\r' | cut -d' ' -f2)"
t "hidden alias NOT flagged" "0" "$(curl -s -D - -o /dev/null --max-time 60 -H "$H1" -H "$H2" "$B/api/v2/news/all?since=2026-09-01&limit=1" | grep -ci '^x-brubru-unknown-params')"
t "format= NOT flagged"      "0" "$(curl -s -D - -o /dev/null --max-time 60 -H "$H1" -H "$H2" "$B/api/v2/echa/news?format=csv&limit=1" | grep -ci '^x-brubru-unknown-params')"
t "header CORS-exposed"      "1" "$(curl -s -D - -o /dev/null --max-time 60 -H 'Origin: https://brubru.beresol.eu' -H "$H1" "$B/api/v2/news/all?limit=1" | grep -i 'access-control-expose' | grep -ci 'X-Brubru-Unknown-Params')"

echo ""
echo "--- FIX 5: filter and sort use the same date expression ---"
t "undated-only body still served" "yes" "$(jq_ '/api/v2/news/all?body=euda&from=2020-01-01&to=2026-12-31&limit=1' "'yes' if d['total']>0 else 'no'")"
t "factory endpoint serves"         "yes" "$(jq_ '/api/v2/echa/news?since=2026-01-01&limit=1' "'yes' if isinstance(d.get('total'),int) else 'no'")"

echo ""
echo "--- FIX 8: order=soonest ---"
t "soonest == oldest" "$(jq_ '/api/v2/events/all?when=upcoming&order=oldest&limit=1' "str(d['data'][0]['document_date'])[:10]")" "$(jq_ '/api/v2/events/all?when=upcoming&order=soonest&limit=1' "str(d['data'][0]['document_date'])[:10]")"
RC=$(jq_ '/api/v2/events/all?when=upcoming&order=recent&limit=1' "str(d['data'][0]['document_date'])[:4]")
SO=$(jq_ '/api/v2/events/all?when=upcoming&order=soonest&limit=1' "str(d['data'][0]['document_date'])[:4]")
if [[ "$RC" != "$SO" ]]; then echo "  PASS  recent still the far-future trap (recent=$RC soonest=$SO)"; PASS=$((PASS+1)); else echo "  FAIL  recent==soonest"; FAIL=$((FAIL+1)); fi
t "invalid order rejected" "400" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 -H "$H1" -H "$H2" "$B/api/v2/events/all?order=nonsense&limit=1")"

echo ""
echo "--- REMINDER 2: five datapoints on the institutional half ---"
for f in public_url body_txt body_html document_date creation_date; do
  t "commission item has $f" "yes" "$(jq_ '/api/v2/news/all?body=commission&include_body=true&limit=1' "'yes' if d['data'][0].get('$f') else 'no'")"
done
t "body_html is composed HTML" "yes" "$(jq_ '/api/v2/news/all?body=commission&include_body=true&limit=1' "'yes' if str(d['data'][0]['body_html']).startswith('<article>') else 'no'")"
t "cheap list still omits bodies" "yes" "$(jq_ '/api/v2/news/all?body=commission&limit=1' "'yes' if d['data'][0].get('body_txt') is None else 'no'")"
t "DB: eu_news_items all composed" "0" "$(q "SELECT count(*) FROM eu_news_items WHERE body_txt IS NULL OR btrim(body_txt)='' OR body_html IS NULL OR btrim(body_html)=''")"
t "DB: body_source recorded on all" "0" "$(q "SELECT count(*) FROM eu_news_items WHERE body_source IS NULL")"
t "DB: economy_items news all have body_txt" "0" "$(q "SELECT count(*) FROM economy_items WHERE item_type IN ('news','press_release') AND (body_txt IS NULL OR btrim(body_txt)='')")"
t "DB: economy_items news all have body_html" "0" "$(q "SELECT count(*) FROM economy_items WHERE item_type IN ('news','press_release') AND (body_html IS NULL OR btrim(body_html)='')")"
t "DB: no error page stored as a body" "0" "$(q "SELECT count(*) FROM economy_items WHERE item_type IN ('news','press_release') AND (body_txt ILIKE '%404 Not Found%' OR body_txt ILIKE '%Requested page not found%' OR body_txt LIKE '%![template\\_%' OR body_txt LIKE '%[et_pb\\_%')")"

echo ""
echo "--- FIX 3: fra in, outlet/funding out ---"
# "not doubled" is the real property: fra is served out of eu_news_items and the
# union must not count it twice. A hardcoded 64 tested the row count of one
# afternoon instead, and failed on 9 Sep at 65 -- legitimate growth (65 rows, 65
# distinct entry_keys, 0 duplicates), the same mistake as the old ombudsman
# "deduped 21->16" assertion.
ge "fra reachable"                    1 "$(tot '/api/v2/news/all?body=fra&limit=1')"
t  "fra not doubled (no dup keys)" "0" "$(q "SELECT count(*) - count(DISTINCT entry_key) FROM eu_news_items WHERE institution='FRA'")"
t "fra carries body_html"      "yes" "$(jq_ '/api/v2/news/all?body=fra&include_body=true&limit=1' "'yes' if d['data'][0].get('body_html') else 'no'")"
t "outlet still excluded"      "0" "$(tot '/api/v2/news/all?body=outlet&limit=1')"
t "funding still excluded"     "0" "$(tot '/api/v2/news/all?body=funding&limit=1')"

echo ""
echo "--- FIX 4+6: /news/latest is an honest instrument ---"
ge "by_body returns >10 bodies" 11 "$(jq_ '/api/v2/news/latest' "len(d['by_body'])")"
t  "by_body_truncated False"   "False" "$(jq_ '/api/v2/news/latest' "d['by_body_truncated']")"
ge "stale bodies visible"      1 "$(jq_ '/api/v2/news/latest' "d['bodies_stale']")"
t  "stalest first"             "yes" "$(jq_ '/api/v2/news/latest' "'yes' if d['by_body'][0]['state'] in ('undated','stale') else 'no'")"
ge "causes distinguished"      2 "$(jq_ '/api/v2/news/latest' "len({b['likely_cause'] for b in d['by_body']}-{None})")"
t  "counts sum to total"       "yes" "$(jq_ '/api/v2/news/latest' "'yes' if d['bodies_fresh']+d['bodies_stale']+d['bodies_undated']==d['bodies_total'] else 'no'")"
t  "per-body threshold differs from corpus" "yes" "$(jq_ '/api/v2/news/latest?body_stale_after_days=3' "'yes' if d['bodies_stale']>0 else 'no'")"

echo ""
echo "--- FIX 7: date_parser recovery (DB truth) ---"
t "rail fully dated"        "0"   "$(q "SELECT count(*) FROM economy_items WHERE body_code='rail' AND item_type IN ('news','press_release') AND document_date IS NULL")"
ge "euda dated >= 970"      970   "$(q "SELECT count(*) FROM economy_items WHERE body_code='euda' AND item_type IN ('news','press_release') AND document_date IS NOT NULL")"
ge "eib dated >= 205"       205   "$(q "SELECT count(*) FROM economy_items WHERE body_code='eib' AND item_type IN ('news','press_release') AND document_date IS NOT NULL")"
t "no future dates"         "0"   "$(q "SELECT count(*) FROM economy_items WHERE body_code IN ('euda','eib','rail') AND item_type IN ('news','press_release') AND document_date > now()")"
t "no pre-1990 dates"       "0"   "$(q "SELECT count(*) FROM economy_items WHERE body_code IN ('euda','eib','rail') AND item_type IN ('news','press_release') AND document_date < '1990-01-01'")"
ge "euda rows not lost" 978 "$(q "SELECT count(*) FROM economy_items WHERE body_code='euda' AND item_type IN ('news','press_release')")"
ge "eib rows not lost"  247 "$(q "SELECT count(*) FROM economy_items WHERE body_code='eib' AND item_type IN ('news','press_release')")"
ge "rail rows not lost"  17 "$(q "SELECT count(*) FROM economy_items WHERE body_code='rail' AND item_type IN ('news','press_release')")"
t "bodies still intact on those rows" "0" "$(q "SELECT count(*) FROM economy_items WHERE body_code IN ('euda','eib','rail') AND item_type IN ('news','press_release') AND (body_txt IS NULL OR body_html IS NULL)")"
t "eib residual is all eif.org" "yes" "$(q "SELECT CASE WHEN count(*) FILTER (WHERE public_url NOT LIKE '%eif.org%')=0 THEN 'yes' ELSE 'no' END FROM economy_items WHERE body_code='eib' AND item_type IN ('news','press_release') AND document_date IS NULL")"
t "URL-year cross-check disagreements" "1" "$(q "SELECT count(*) FROM economy_items WHERE body_code='euda' AND item_type IN ('news','press_release') AND document_date IS NOT NULL AND substring(public_url from '/news/(\d{4})/') IS NOT NULL AND extract(year FROM document_date)::text <> substring(public_url from '/news/(\d{4})/')")"

echo ""
echo "--- FIX 7: production reclassified the bodies ---"
t "rail  now fresh"    "fresh"   "$(jq_ '/api/v2/news/latest' "[b['state'] for b in d['by_body'] if b['code']=='rail'][0]")"
t "eib   now fresh"    "fresh"   "$(jq_ '/api/v2/news/latest' "[b['state'] for b in d['by_body'] if b['code']=='eib'][0]")"
t "euda no longer undated" "yes" "$(jq_ '/api/v2/news/latest' "'yes' if [b['state'] for b in d['by_body'] if b['code']=='euda'][0]!='undated' else 'no'")"
t "sesar now dated from its RSS feed" "fresh" "$(jq_ '/api/v2/news/latest' "[b['state'] for b in d['by_body'] if b['code']=='sesar'][0]")"
t "ombudsman no longer undated (REST carries dates)" "yes" "$(jq_ '/api/v2/news/latest' "'yes' if [b['state'] for b in d['by_body'] if b['code']=='ombudsman'][0] != 'undated' else 'no'")"
t "ombudsman has no duplicate URLs" "0" "$(q "SELECT count(*) - count(DISTINCT public_url) FROM economy_items WHERE body_code='ombudsman' AND item_type IN ('news','press_release')")"
t "ombudsman fully dated" "0" "$(q "SELECT count(*) FROM economy_items WHERE body_code='ombudsman' AND item_type IN ('news','press_release') AND document_date IS NULL")"
t "ombudsman all canonical" "0" "$(q "SELECT count(*) FROM economy_items WHERE body_code='ombudsman' AND item_type IN ('news','press_release') AND public_url NOT LIKE '%/en/news-document/%'")"
t "no 404 page stored as a body anywhere" "0" "$(q "SELECT count(*) FROM economy_items WHERE item_type IN ('news','press_release') AND (body_txt ILIKE '%404 Not Found%' OR body_txt ILIKE '%Requested page not found%' OR body_txt LIKE '%![template_%')")"
t "sesar rows dated" "5" "$(q "SELECT count(*) FROM economy_items WHERE body_code='sesar' AND item_type IN ('news','press_release') AND document_date IS NOT NULL")"

echo ""
echo "--- regression: unrelated surfaces ---"
for ep in /api/v1/whoami "/api/v2/echa/candidate-list?limit=1" "/api/v2/legislative/eur-lex/laws?limit=1" /api/v2/news/bodies "/api/v2/parliament/eprs?limit=1" "/api/v2/funding/all?limit=1" "/api/v2/transparency-register?limit=1"; do
  t "$ep" "200" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 -H "$H1" -H "$H2" "$B$ep")"
done
MCPBODY='{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
mcpcount() { curl -s --max-time 40 -X POST "$B$1" -H "$H1" -H 'Content-Type: application/json' --data "$MCPBODY" | python3.12 -c 'import sys,json; d=json.load(sys.stdin); print(len(d["result"]["tools"]) if "result" in d else "ERR")'; }
t "MCP still serves 15 tools" "15" "$(mcpcount /api/mcp)"
t "DPP MCP still serves 11"   "11" "$(mcpcount /api/mcp/dpp)"

echo ""
echo "=========================================="
echo "  $PASS PASS / $FAIL FAIL"
echo "=========================================="
[[ $FAIL -gt 0 ]] && exit 1
[[ $PASS -eq 0 ]] && { echo "  [ERROR] zero checks ran -- the suite itself is broken"; exit 2; }
exit 0
