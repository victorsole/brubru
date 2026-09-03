---
name: siteground
description: Build and pre-render the frontend dist folder for SiteGround deployment. Runs npm run build:prerender, verifies output, and reports file sizes. User deploys the dist/ folder manually.
argument-hint: ["build" (default) | "check" to verify existing dist]
allowed-tools: ["Read", "Bash", "Glob", "Grep"]
---

# Frontend Build for SiteGround

You are building the Brubru frontend for deployment to SiteGround. This produces the `frontend/dist/` folder that the user uploads manually to SiteGround.

## Step 1: Pre-flight Checks

Run these in parallel:

```bash
cd /Users/victorsole/Developer/brubru/frontend
node -v && npm -v
```

```bash
cd /Users/victorsole/Developer/brubru/frontend
git status -- src/ public/ index.html vite.config.ts package.json
```

If the argument is "check", skip to Step 4 to verify the existing dist folder.

Check for any TypeScript or build errors before the full build:

```bash
cd /Users/victorsole/Developer/brubru/frontend
npx tsc --noEmit 2>&1 | tail -20
```

If there are TypeScript errors, report them and ask the user whether to proceed (Vite may still build successfully despite TS errors).

## Step 2: Build with Pre-rendering

Run the production build with pre-rendering for AI crawlers:

```bash
cd /Users/victorsole/Developer/brubru/frontend
npm run build:prerender
```

This does two things:
1. `vite build` -- produces the SPA bundle in `dist/`
2. `scripts/prerender.mjs` -- boots Puppeteer, visits 9 public routes, saves static HTML

The 9 pre-rendered routes are: `/`, `/login`, `/signup`, `/about`, `/contact`, `/privacy`, `/terms`, `/cookies`, `/subprocessors`.

If the build fails, diagnose the error:
- **Vite build error**: check the error message, likely a missing import or syntax issue
- **Puppeteer error**: the pre-render step failed. Try `npm run build` (without pre-render) as fallback and warn the user that AI crawlers will not see content.

## Step 3: Verify Build Output

Run these checks in parallel:

```bash
cd /Users/victorsole/Developer/brubru/frontend
# Check dist exists and show top-level structure
ls -la dist/ && echo "---" && ls -la dist/assets/ | head -10
```

```bash
cd /Users/victorsole/Developer/brubru/frontend
# Check pre-rendered pages exist
for route in about contact cookies login privacy signup subprocessors terms; do
  if [ -f "dist/$route/index.html" ]; then
    echo "[OK] $route/index.html ($(wc -c < dist/$route/index.html) bytes)"
  else
    echo "[MISSING] $route/index.html"
  fi
done
```

```bash
cd /Users/victorsole/Developer/brubru/frontend
# Check main index.html has content (not empty div)
if grep -q '<div id="root">' dist/index.html && grep -q '<script' dist/index.html; then
  echo "[OK] dist/index.html has root div and script tag"
else
  echo "[WARN] dist/index.html may be incomplete"
fi
# Show total dist size
du -sh dist/
```

## Step 4: Report Summary

Present a deployment-ready summary:

```
SITEGROUND BUILD COMPLETE

  Dist folder: frontend/dist/
  Total size:  [X] MB
  JS bundle:   dist/assets/index-[hash].js ([size])
  CSS bundle:  dist/assets/index-[hash].css ([size])

  Pre-rendered pages (9):
    [OK] / (index.html)
    [OK] /about
    [OK] /contact
    [OK] /cookies
    [OK] /login
    [OK] /privacy
    [OK] /signup
    [OK] /subprocessors
    [OK] /terms

  Ready to deploy: Upload frontend/dist/ contents to SiteGround via File Manager or SFTP.
  Target: brubru.beresol.eu (public_html/)
```

## Step 5: Smoke Test (Self-Sufficient Verification Loop)

After the build succeeds, verify the output is actually valid:

```bash
cd /Users/victorsole/Developer/brubru/frontend
# Check that index.html has real content (not a blank page)
TITLE=$(grep -o '<title>[^<]*</title>' dist/index.html)
ROOT_SIZE=$(grep -c 'class=' dist/index.html)
echo "Title: $TITLE"
echo "HTML elements: $ROOT_SIZE"
if [ "$ROOT_SIZE" -lt 5 ]; then echo "[WARN] index.html looks empty -- build may have failed silently"; else echo "[OK] index.html has content"; fi
```

```bash
cd /Users/victorsole/Developer/brubru/frontend
# Verify JS bundle is not zero-size and CSS exists
JS_FILE=$(ls -S dist/assets/index-*.js 2>/dev/null | head -1)
CSS_FILE=$(ls -S dist/assets/index-*.css 2>/dev/null | head -1)
if [ -n "$JS_FILE" ] && [ "$(wc -c < "$JS_FILE")" -gt 1000 ]; then echo "[OK] JS bundle: $(du -h "$JS_FILE" | cut -f1)"; else echo "[FAIL] JS bundle missing or empty"; fi
if [ -n "$CSS_FILE" ] && [ "$(wc -c < "$CSS_FILE")" -gt 100 ]; then echo "[OK] CSS bundle: $(du -h "$CSS_FILE" | cut -f1)"; else echo "[FAIL] CSS bundle missing or empty"; fi
```

```bash
cd /Users/victorsole/Developer/brubru/frontend
# IMPORTANT (28 July 2026): dist/sitemap.xml is a sitemap INDEX, not a URL list.
# It legitimately contains exactly 2 <loc> entries (sitemap-pages.xml and
# sitemap-legislacio.xml). Counting <loc> in the index and reading "2" as a
# broken build is a FALSE ALARM -- it cost an unnecessary rebuild. Count the
# CHILDREN instead. Expect roughly 330 pages + ~34,000 Catalan legislation URLs.
SITEMAP_URLS=$(cat dist/sitemap-pages.xml dist/sitemap-legislacio.xml 2>/dev/null | grep -c '<loc>' || echo 0)
echo "Sitemap URLs (children): $SITEMAP_URLS"
if [ "$SITEMAP_URLS" -ge 1000 ]; then echo "[OK] Sitemap has $SITEMAP_URLS URLs"; else echo "[WARN] Sitemap looks incomplete ($SITEMAP_URLS URLs) -- rebuild in the FOREGROUND"; fi
```

Also check if there are uncommitted frontend source changes that should be committed:

```bash
cd /Users/victorsole/Developer/brubru
git status -- frontend/src/ frontend/public/ frontend/index.html frontend/vite.config.ts
```

If there are source changes, remind the user to commit them (source changes go to the repo, dist does not).

## Step 6: Deploy to SiteGround (FTP) — the canonical recipe

The deploy is an FTP mirror, NOT just `put index.html`. The single biggest
failure mode (caught 8 June 2026): pushing `index.html` but **not `app.html`**.
`app.html` is the CLEAN SPA shell that `.htaccess` rewrites every client route
(`/main`, `/my-eu-bubble`, `/amendator`, ...) to. If `app.html` is stale, the
whole app loads an OLD content-hashed bundle (old `dist/assets/*.js` are never
deleted on the server, so the stale reference keeps resolving) — the app
silently runs old code while `index.html` looks fine. **Always force-push every
root HTML shell, not just index.html.**

```bash
cd /Users/victorsole/Developer/brubru
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:$PATH   # lftp strips PATH
H=$(grep '^SITEGROUND_FTP_HOST=' .env | cut -d= -f2-)
U=$(grep '^SITEGROUND_FTP_USER=' .env | cut -d= -f2-)
P=$(grep '^SITEGROUND_FTP_PASS=' .env | cut -d= -f2-)

# DOCROOT (confirmed 12 June 2026): brubru.beresol.eu is served from
# `brubru.beresol.eu/public_html/`, NOT the FTP account-home root. The FTP home
# ALSO contains an app.html/assets/ copy, so it LOOKS like the docroot, but
# uploads there are never served — the SPA keeps running the OLD bundle and the
# `.htaccess` !-f fallback returns the React shell for any missing path. Always
# target /brubru.beresol.eu/public_html/. (memory: feedback_siteground_real_docroot)

# 1. Mirror the content-hashed assets (new files only; old ones harmlessly remain).
lftp -c "set ftp:ssl-allow true; set ssl:verify-certificate no; open -u '$U','$P' '$H'; \
  lcd frontend/dist/assets; mirror -R --parallel=4 --only-newer --exclude-glob .DS_Store ./ /brubru.beresol.eu/public_html/assets/"

# 2. FORCE-push EVERY HTML shell + .htaccess (mirror by glob, NO --only-newer so
#    nothing is silently skipped). app.html is mandatory.
lftp -c "set ftp:ssl-allow true; set ssl:verify-certificate no; open -u '$U','$P' '$H'; \
  lcd frontend/dist; \
  mirror -R --parallel=3 --include-glob '*.html' --exclude legislacio-ue-catala/ --exclude assets/ ./ /brubru.beresol.eu/public_html/; \
  put .htaccess -o /brubru.beresol.eu/public_html/.htaccess"
```

**Verify BOTH shells by content-hash (not just a 200):**

```bash
cd /Users/victorsole/Developer/brubru
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:$PATH
H=$(grep '^SITEGROUND_FTP_HOST=' .env | cut -d= -f2-); U=$(grep '^SITEGROUND_FTP_USER=' .env | cut -d= -f2-); P=$(grep '^SITEGROUND_FTP_PASS=' .env | cut -d= -f2-)
LOCAL=$(grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' frontend/dist/app.html | head -1)
lftp -c "set ftp:ssl-allow true; set ssl:verify-certificate no; open -u '$U','$P' '$H'; get brubru.beresol.eu/public_html/app.html -o /tmp/sg_app.html; get brubru.beresol.eu/public_html/index.html -o /tmp/sg_idx.html"
echo "local bundle:      $LOCAL"
echo "server app.html:   $(grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' /tmp/sg_app.html | head -1)"
echo "server index.html: $(grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' /tmp/sg_idx.html | head -1)"
# All three MUST match. If app.html differs, the app is serving old code.
```

**SiteGround dynamic-cache caveat.** SiteGround caches the HTML shells in its
NGINX dynamic cache (`x-proxy-cache-info: DT:1`, often `max-age=15552000`). The
on-disk file can be correct while HTTP still serves a stale body. The repo's
`.htaccess` now sends `Cache-Control: no-cache, no-store` for `*.html` so NEW
responses are not cached, but an EXISTING cached entry only clears via **Site
Tools -> Speed -> Caching -> Flush Cache** (dashboard only — no FTP/API
equivalent) or its TTL. After one flush the no-cache headers keep it fresh. So a
deploy's HTTP-level staleness ("live serves old bundle") is expected until that
flush; trust the FTP content-hash check above as the real success signal.

## Important Notes

- **`app.html` is mandatory in every deploy** (Step 6). The SPA shell, not
  index.html, is what `/my-eu-bubble` and all app routes load. Verify its
  content-hash matches local after every push.
- **NEVER commit the dist folder** to git -- it is deployed manually to SiteGround
- The dist folder is gitignored except for `frontend/dist/index.html` and `frontend/dist/sitemap.xml` which are tracked for SEO
- Use `npm run build:prerender` (not plain `npm run build`) for production deploys
- If Puppeteer fails, `npm run build` still produces a working SPA (just without pre-rendered static pages for crawlers)
- The user uploads `frontend/dist/` contents to SiteGround manually (via File Manager, SFTP, or rsync)
- SiteGround serves from `public_html/` with Apache -- `DirectoryIndex` handles the pre-rendered route folders
- `frontend/public/robots.txt` has AI crawler allow rules and must be included in the upload
- If a new public route was added, remind the user to add it to the `ROUTES` array in `frontend/scripts/prerender.mjs`
- **CRITICAL: `.htaccess` MUST be uploaded** (policy reversed 15 April 2026). The local `frontend/dist/.htaccess` contains the SPA fallback (`RewriteCond !-f !-d -> index.html`) without which any client-side route (`/main`, `/my-eu-bubble`, `/amendator`, `/eulawcomply`, `/tenderator`, ...) returns 404 on refresh. Do NOT exclude `.htaccess` from the FTP mirror. If SiteGround has injected panel-managed rules, download production `.htaccess` first, merge, then re-upload.
- **After FTP upload, also upload files NOT in frontend/dist/:**
  - Catalan landing page: `lftp put -O brubru.beresol.eu/public_html/legislacio-ue-catala/ data/legislacio-ue-catala/index.html`
  - These files live in `data/` not `frontend/`, so the dist mirror misses them
- **Post-upload verification:** Always check these URLs return 200 after deploying:
  - `https://brubru.beresol.eu/guides/index.html`
  - `https://brubru.beresol.eu/legislacio-ue-catala/`
  - `https://brubru.beresol.eu/main` (SPA fallback test -- 404 here means `.htaccess` did not upload or was overwritten)
  - `https://brubru.beresol.eu/api` (pre-rendered public page)
  - `https://brubru.beresol.eu/clientpitch/` (standalone client pitch deck, multilingual; lives at `frontend/public/clientpitch/index.html`)

- **MANDATORY: curl-verify Last-Modified for every changed user-visible HTML** (set 4 May 2026 after lftp `--only-newer` silently skipped the 3 deep-dive HTMLs). For each file modified in this build, run:

  ```bash
  # PATH-restoration prefix: lftp shell sessions strip PATH; without this prefix
  # `curl` / `sed` / `tr` / `date` come back as "command not found". Caught
  # 5 May 2026 during /siteground curl-verify step.
  export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:$PATH

  for path in eu-inc/ industrial-accelerator-act/ digital-networks-act/ guides/index.html data-architecture/index.html; do
    echo -n "$path : "
    curl -sI -A "Mozilla/5.0" "https://brubru.beresol.eu/$path" | grep -i "last-modified\|content-length" | tr '\n' ' '
    echo
  done
  ```

  Compare each `last-modified` against today's date and each `content-length` against `wc -c` of the local file. If a file is stale, **force-push it** via:

  ```bash
  lftp -c "set ftp:ssl-allow no; open -u $FTP_USER,$FTP_PASS $FTP_HOST; \
    cd brubru.beresol.eu/public_html; \
    put -O <subfolder> dist/<subfolder>/<file>; \
    bye"
  ```

  This is NOT optional. The `--only-newer` flag in the recommended mirror command can compare local-mtime vs server-mtime in ways that silently skip files Vite has just rebuilt with the source mtime preserved. Memory: `feedback_lftp_only_newer_skips.md` (4 May 2026 incident: production served Friday 1 May bytes for 30+ minutes after a green Mon 4 May build).

- **Cache-bust when verifying the JS bundle hash.** A plain `curl https://brubru.beresol.eu/` may return a CDN-cached `index.html` that still references the *previous* JS bundle, even though the new `index.html` is already on the server. Confirm the correct bundle is live by appending a unique query string:

  ```bash
  curl -s -A "Mozilla/5.0" "https://brubru.beresol.eu/?nocache=$(date +%s)" | grep -oE 'index-[A-Za-z0-9_-]+\.(js|css)' | sort -u
  # Compare with local:
  grep -oE 'index-[A-Za-z0-9_-]+\.(js|css)' /Users/victorsole/Developer/brubru/frontend/dist/index.html | sort -u
  ```

  If the two lists match, the deploy is live. If they don't match but `/assets/index-NEW.js` already exists on the server (verify via `lftp ... ls`), it's just CDN staleness -- wait 30-60s and retry with a fresh `nocache=`. Caught 15 April 2026 after Position Analysis deploy.

## Recommended FTP mirror command

```bash
FTP_HOST=$(grep '^SITEGROUND_FTP_HOST=' /Users/victorsole/Developer/brubru/.env | cut -d'=' -f2-)
FTP_USER=$(grep '^SITEGROUND_FTP_USER=' /Users/victorsole/Developer/brubru/.env | cut -d'=' -f2-)
FTP_PASS=$(grep '^SITEGROUND_FTP_PASS=' /Users/victorsole/Developer/brubru/.env | cut -d'=' -f2-)
cd /Users/victorsole/Developer/brubru/frontend
lftp -c "set ftp:ssl-allow no; open -u $FTP_USER,$FTP_PASS $FTP_HOST; mirror --reverse --verbose --only-newer --exclude .DS_Store dist/ brubru.beresol.eu/public_html/; bye"
```

Note: no `--exclude .htaccess`. The local dist `.htaccess` has the SPA rewrite rules and must reach the server.
