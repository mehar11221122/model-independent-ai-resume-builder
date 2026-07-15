# Model-Independent AI Engine & Resume Builder

A reusable, model-independent AI Engine built on **LangGraph** (stateful
orchestration) + **LangChain** (LLM integration) + **OpenRouter** (model
gateway), with the **Resume Builder** as its first vertical module. See
`Project_Scope_Document (1).docx` for the full scope.

## Architecture at a glance

```
Input (text/PDF/DOCX/image) → Load + label each source → Extraction
  (reconciles overlapping facts across sources, flags real disagreements
   as "conflicts" in the same LLM pass) → Gap Detection (missing fields +
   unresolved conflicts) → Follow-up Questions (human-in-the-loop, pausable)
  → Answer-Quality Check (rejects off-topic/incomplete answers, re-asks) →
   Tool Use (optional, vertical-supplied) → Structured Generation →
   Validation (auto-retry on failure) → JSON Response
```

There's no separate "merge" step in the graph: `app/ingestion/merge.py` just concatenates multi-source
text with source labels; the *extraction* node's LLM call is what actually reconciles/deduplicates
facts and flags genuine conflicts, in a single pass (see that module's docstring for why). Conflicts
and missing fields both resolve through the same clarify loop.

- `app/graph/` — the domain-agnostic engine: state schema, nodes, the graph itself, checkpointing.
- `app/llm/` — OpenRouter client + model-tier routing (primary / fallback / lightweight).
- `app/ingestion/` — multi-modal loaders: text, PDF (with OCR fallback for scanned pages), DOCX, image
  (OCR), plus the pre-extraction concatenation step.
- `app/modules/resume/` — the Resume vertical: schema, prompts, validation rules, and LangChain tools
  (`tools.py`, e.g. deterministic date normalization) the engine's tool-use node can call. This is the
  *only* place with resume-specific logic — everything else is reusable for future verticals
  (marketing, automotive, legal, ...).
- `app/api/` — FastAPI routes exposing the engine over REST.

Adding a new vertical = writing a new `app/modules/<vertical>/` package with a `VerticalConfig`,
registering it in `app/graph/registry.py`, and adding its own thin API routes under `app/api/routes/`
(mirroring `resume.py`) - the engine/graph code itself needs zero changes.

## Setup

### 1. Prerequisites
- Python 3.11+
- (Optional, for OCR) [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on your
  PATH, or set `TESSERACT_CMD` in `.env` to its executable path.
- (Optional, for Docker) Docker + Docker Compose.

### 2. Install dependencies
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

### 3. Configure environment
```bash
copy .env.example .env         # Windows
# cp .env.example .env          # macOS/Linux
```
At minimum, set `OPENROUTER_API_KEY` (get one at https://openrouter.ai/keys). Everything else has a
working default for local development (SQLite checkpointing, local file storage, Tesseract OCR).

### 4. Run the API
```bash
uvicorn app.main:app --reload
```
Then open http://127.0.0.1:8000/docs for the interactive OpenAPI/Swagger UI.

### 5. Run with Docker (includes Postgres + Redis for production-style state persistence)
```bash
docker compose up --build
```

### 6. Run tests
```bash
pytest
```

## Using the Resume API

1. `POST /resume/sessions` (multipart form: `language`, `text` and/or `files[]`) — kicks off the
   workflow. If required info is missing, the response comes back with
   `status: "awaiting_clarification"` and a list of `follow_up_questions`.
2. `POST /resume/sessions/{thread_id}/answers` (JSON `{"answers": {...}}`) — submit answers to the
   follow-up questions; the workflow resumes from its saved checkpoint.
3. `GET /resume/sessions/{thread_id}` — poll current status/result at any time.

A completed session returns `status: "completed"` with the generated resume in
`structured_output`, matching the schema in `app/modules/resume/schema.py`.

## Deploying for real users, for free (no credit card)

Local + Cloudflare Quick Tunnel (see below) is great for testing, but its URL changes every time the
tunnel restarts — not something to hand out to real users. For a **stable, permanent, still-$0** URL,
deploy the container to a host with an ephemeral filesystem + external Postgres for state. Render and
Belmo were tried first and dropped — both hit card/signup friction in practice despite marketing
themselves as free. **Koyeb** is the current recommendation; **Hugging Face Docker Spaces** is the
backup if Koyeb ever asks for a card.

### Primary: Koyeb + Neon
1. Push this repo to GitHub.
2. Create a free [Neon](https://neon.tech) Postgres project (no card) and copy its connection string.
3. Create a free [Koyeb](https://www.koyeb.com) account (no card in most signups) and deploy this repo
   as a Web Service — it auto-detects the `Dockerfile` at the repo root. It gives you a persistent
   `https://<app>-<org>.koyeb.app` URL.
4. In Koyeb's environment variables, set:
   - `OPENROUTER_API_KEY` — from [openrouter.ai/keys](https://openrouter.ai/keys)
   - `CHECKPOINT_BACKEND=postgres` and `POSTGRES_DSN=<your Neon connection string>` (Koyeb's free
     instance has no persistent disk, so SQLite would be wiped on every sleep/restart)
   - `MODEL_PRIMARY` / `MODEL_FALLBACK` / `MODEL_LIGHTWEIGHT` — `:free` OpenRouter model slugs (see
     `.env.example`)
5. (Optional, if you want uploaded files to survive restarts) create a free
   [Supabase Storage](https://supabase.com) bucket and set `STORAGE_BACKEND=s3` +
   `AWS_S3_BUCKET`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`S3_ENDPOINT_URL` to its S3-compatible
   credentials. Otherwise leave `STORAGE_BACKEND=local` — uploads just won't persist across restarts.

**Realistic expectations:** the free instance sleeps after ~1 hour with no traffic; the first request
after that takes 30-60s to wake up. Fine for a pilot with real users, not an SLA-backed product. There
is no cost risk as long as you never attach a payment method to either account.

### Backup: Hugging Face Docker Spaces + Neon
Same idea, same Neon database. Create a Space → Docker → paste this repo's `Dockerfile`. Gives more
RAM when awake (useful if you outgrow Koyeb's free instance) but sleeps after 48h idle instead of 1h,
and the Space (and its code) is public on the free tier.

A `render.yaml` blueprint is still included for reference if Render ever works smoothly for you, but
it's no longer the recommended path.

CI (`.github/workflows/ci.yml`) runs lint + tests on every push via GitHub Actions' free tier.

## Scaling past free quotas

OpenRouter's free tier (`:free`-suffixed models) is a **single quota shared across every free model on
one account** — 50 requests/day by default, or 1,000/day if you've ever added the one-time $10 credit.
A single resume session costs several LLM calls (extraction, clarification round(s), answer checks,
generation), so 50/day is only ~6-10 completed resumes/day *total across all users* — nowhere near enough
for a real launch, and easy to exhaust just testing manually.

Because that quota is per-*account*, not per-model, setting `MODEL_FALLBACK` to a different OpenRouter
model does **not** add capacity — both draw from the same bucket. `app/llm/router.py` instead chains on
Groq and Google Gemini as extra fallback links: they're separate companies with their own independent
free daily quotas, so a rate-limit on OpenRouter's shared pool spills over onto an entirely different
quota instead of failing the request. Both are optional and card-free to sign up for:

- **Groq** ([console.groq.com/keys](https://console.groq.com/keys)) — ~14,400 free req/day on its 8B
  model, ~1,000/day on its larger 70B/120B models. Set `GROQ_API_KEY` (see `.env.example`).
- **Google Gemini** ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) — ~250-1,500 free
  req/day depending on model, via Gemini's OpenAI-compatibility endpoint. Set `GEMINI_API_KEY`.

Configuring both alongside OpenRouter raises the effective daily ceiling from ~50 to several thousand
requests, all still $0 and card-free — enough for a real pilot/beta launch. This is a capacity multiplier,
not a permanent scaling story: real production traffic has real inference cost somewhere, so free-tier
stacking should be treated as "run the pilot for free," with a monetization or paid-credits decision to
make once real demand is proven. Other quick levers, in order of effort:
1. Add the one-time $10 OpenRouter credit → 1,000/day on OpenRouter alone (simplest, but needs a card once).
2. Reduce LLM calls per session (e.g. skip the answer-quality check for trivially-valid short answers).
3. Once there's real traction, fund actual paid API usage from revenue/investment like any other product.

## Configuration reference

All runtime behavior is controlled via `.env` (see `.env.example` for the full list), including:
- `MODEL_PRIMARY` / `MODEL_FALLBACK` / `MODEL_LIGHTWEIGHT` — OpenRouter model slugs. Swap providers or
  models without touching code.
- `GROQ_API_KEY` / `GEMINI_API_KEY` — optional secondary providers with independent free quotas, chained
  on as extra fallback links (see "Scaling past free quotas" above). Leave blank for OpenRouter-only.
- `CHECKPOINT_BACKEND` — `memory` | `sqlite` | `postgres`.
- `OCR_BACKEND` — `tesseract` | `google_vision` | `aws_textract` (the latter two are stubbed, not yet
  implemented — see `app/ingestion/ocr_loader.py`). Used both for uploaded images and automatically as
  a fallback inside `app/ingestion/pdf_loader.py` when a PDF has no extractable text layer (i.e. it's a
  scanned document).
- `STORAGE_BACKEND` — `local` | `s3` (both implemented — see `app/storage/local.py` / `app/storage/s3.py`).

## Status

This is the initial engine scaffold: project structure, config, OpenRouter integration, the full
LangGraph workflow skeleton, multi-modal ingestion, and the Resume vertical are wired end-to-end and
runnable. Remaining work per the scope doc's 6-week plan: hardening the extraction/generation prompts
against real sample resumes, Arabic QA, API auth, deployment, and documentation polish.
