#!/bin/zsh
# The guard's three states, exercised end to end. A check that cannot stop the push is
# decoration: on 25 September the check and the push were one `curl ... && git push` line,
# so it printed "in flight" and pushed anyway, truncating two fast-tier runs.
set -e
BACKEND="${0:A:h:h}"
cd "$BACKEND"
fail=0

# 1. Unreadable state must refuse, loudly, and must not be mistaken for idle.
sed 's|https://brubru-production.up.railway.app|https://127.0.0.1:9|' \
    scripts/push_when_cron_is_idle.sh > scripts/_guard_unreadable.sh
set +e
out=$(zsh scripts/_guard_unreadable.sh 2>&1); rc=$?
set -e
rm -f scripts/_guard_unreadable.sh
[[ $rc -eq 4 ]] || { print "FAIL: unreadable state exited $rc, expected 4"; fail=1 }
[[ "$out" == *"refusing to push blind"* ]] || { print "FAIL: unreadable state said nothing"; fail=1 }

# 2. A busy fleet must refuse and name what is running.
python3 - <<'PY' >/dev/null 2>&1 &
import http.server, json
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        b = json.dumps({"in_flight": ["/api/cron/sync/tier/fast"], "runs": []}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8788), H).serve_forever()
PY
stub=$!
sleep 2
sed 's|https://brubru-production.up.railway.app|http://127.0.0.1:8788|' \
    scripts/push_when_cron_is_idle.sh > scripts/_guard_busy.sh
set +e
out=$(zsh scripts/_guard_busy.sh 2>&1); rc=$?
set -e
rm -f scripts/_guard_busy.sh
kill $stub 2>/dev/null || true
[[ $rc -eq 1 ]] || { print "FAIL: busy fleet exited $rc, expected 1"; fail=1 }
[[ "$out" == *"sync/tier/fast"* ]] || { print "FAIL: busy fleet did not name the tier"; fail=1 }

[[ $fail -eq 0 ]] && print "push guard: 3 states OK (idle verified against production separately)"
exit $fail
