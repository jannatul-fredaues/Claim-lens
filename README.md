# Evidence Review — Case Desk

A small full-stack demo wrapping the hackathon claim-adjudication logic in a
real upload-and-review UI: pick an object type, describe the claim, drop in
photos, and get a structured verdict back (supported / contradicted / not
enough information), styled like a case file with a stamped verdict.

```
project/
  pipeline/        # shared logic (copied from the hackathon code/ dir)
    schema.py
    prompts.py
    io_utils.py
  backend/
    app.py          # FastAPI: POST /api/claims (multipart upload -> verdict JSON)
    requirements.txt
  frontend/
    index.html
    styles.css
    app.js
```

## Run it

**Locally** — backend serves the frontend too now (no separate static server needed):
```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
uvicorn app:app --reload --port 8000
# open http://localhost:8000  -- this serves the UI AND the API from one process
```

## Deploy it online (Render, free tier)

This repo includes `render.yaml`, so it's a one-click deploy:

1. Push this project to a GitHub repo.
2. Go to [render.com](https://render.com) → **New** → **Blueprint** → connect the repo.
   Render reads `render.yaml` automatically and creates one web service.
3. When prompted, set the `ANTHROPIC_API_KEY` env var (marked `sync: false` in
   `render.yaml` so it's never committed to git — you paste it in Render's
   dashboard).
4. Deploy. Render gives you a URL like `https://evidence-review.onrender.com`
   — that one URL serves both the UI and the API (same origin, so no CORS
   config needed).

**Free-tier note**: Render's free web services spin down after ~15 minutes of
inactivity and take ~30–60s to wake back up on the next request — fine for a
demo/portfolio link, not for something you need always-warm.

### Alternative platforms
- **Railway** / **Heroku-style PaaS**: use the included `Procfile` instead of
  `render.yaml` — same idea, one process serving both UI and API.
- **Fly.io**: works the same way; add a `fly launch` and point its start
  command at `uvicorn app:app --host 0.0.0.0 --port 8080` from `backend/`.
- Any of these need the same single env var: `ANTHROPIC_API_KEY`.

### If you ever split frontend and backend onto different hosts
Set `window.EVIDENCE_REVIEW_API` in `frontend/index.html` before `app.js`
loads (e.g. `<script>window.EVIDENCE_REVIEW_API = "https://your-api.onrender.com";</script>`),
and add that frontend's origin to `allow_origins` in `backend/app.py` (it's
currently `"*"` for convenience, which is fine for a demo but should be
locked down to your actual frontend origin for anything real).

## What's real vs. what's a demo shortcut

- **Real**: the verdict logic is the same `schema.py` / `prompts.py` used by
  the batch pipeline — same enum enforcement, same system prompt rules
  (images are primary evidence, conversation defines what to check, history
  only adds risk context).
- **Demo shortcut**: `evidence_requirements.csv` and `user_history.csv`
  lookups aren't wired into `backend/app.py` yet (no `requirement`/real
  history is passed) — for a portfolio piece, hook those up the same way
  `claim_processor.py` does, keyed off a user ID field you'd add to the form.
- **Demo shortcut**: no persistence. Every submission is stateless — nothing
  is saved. For a real version: a database table per claim, the uploaded
  images in object storage (S3/GCS), and a verdict history view.
- **Demo shortcut**: no auth, no rate limiting, CORS wide open — fine for
  localhost, not fine for anything public.

## Natural next steps if you keep building this

1. Add a "case history" view (list of past submissions + verdicts) backed by
   a database — turns this from a single-shot tool into an actual claims log.
2. Add the `manual_review_required` flag as a real gate: claims flagged that
   way get routed to a review queue instead of an immediate verdict.
3. Add basic auth so claims are tied to a real user (this also lets you wire
   in `user_history.csv`-style risk context for real).
4. Add a confidence/uncertainty display alongside the verdict, not just a
   binary stamp — useful both for trust and for surfacing borderline cases.
