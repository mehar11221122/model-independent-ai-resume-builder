# Model-Independent AI Engine & Resume Builder

A reusable, model-independent AI Engine built on **LangGraph** (stateful
orchestration) + **LangChain** (LLM integration) + **OpenRouter** (model
gateway), with the **Resume Builder** as its first vertical module. See
`Project_Scope_Document (1).docx` for the full scope.

## Architecture at a glance

```
Input → Document Extraction → Information Merging → Gap Detection →
Follow-up Questions (human-in-the-loop) → Structured Generation →
Validation (auto-retry on failure) → JSON Response
```

- `app/graph/` — the domain-agnostic engine: state schema, nodes, the graph itself, checkpointing.
- `app/llm/` — OpenRouter client + model-tier routing (primary / fallback / lightweight).
- `app/ingestion/` — multi-modal loaders: text, PDF, DOCX, image (OCR), plus merging.
- `app/modules/resume/` — the Resume vertical: schema, prompts, validation rules. This is the *only*
  place with resume-specific logic — everything else is reusable for future verticals (marketing,
  automotive, legal, ...).
- `app/api/` — FastAPI routes exposing the engine over REST.

Adding a new vertical = writing a new `app/modules/<vertical>/` package with a `VerticalConfig`, and
registering it in `app/graph/registry.py`. No engine code changes.

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

## Deploying on the free-tier stack

See `Free_Tier_Resource_Plan.docx` and `MILESTONE_1_CHECKLIST.md` for the full free-tier plan and
outstanding action items. Quick version:

1. Push this repo to GitHub.
2. Create a free [Render](https://render.com) account, connect the repo — `render.yaml` in this repo
   is picked up automatically and defines the web service, health check, and required env vars.
3. Create a free [Neon](https://neon.tech) Postgres project and paste its connection string into the
   `POSTGRES_DSN` env var on Render (free Render web services have no persistent disk, so SQLite/local
   storage won't survive a restart — Postgres + S3-compatible storage are required in this setup).
4. Create a free [Cloudflare R2](https://developers.cloudflare.com/r2/) bucket + API token, and fill in
   `AWS_S3_BUCKET` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `S3_ENDPOINT_URL` on Render.
5. Create a free [OpenRouter](https://openrouter.ai/keys) account and add `OPENROUTER_API_KEY`. The
   `render.yaml` defaults `MODEL_PRIMARY`/`MODEL_FALLBACK`/`MODEL_LIGHTWEIGHT` to `:free` OpenRouter
   models so the whole stack runs at $0/month.

CI (`.github/workflows/ci.yml`) runs lint + tests on every push via GitHub Actions' free tier.

## Configuration reference

All runtime behavior is controlled via `.env` (see `.env.example` for the full list), including:
- `MODEL_PRIMARY` / `MODEL_FALLBACK` / `MODEL_LIGHTWEIGHT` — OpenRouter model slugs. Swap providers or
  models without touching code.
- `CHECKPOINT_BACKEND` — `memory` | `sqlite` | `postgres`.
- `OCR_BACKEND` — `tesseract` | `google_vision` | `aws_textract` (the latter two are stubbed, not yet
  implemented — see `app/ingestion/ocr_loader.py`).
- `STORAGE_BACKEND` — `local` | `s3` (S3 not yet implemented — see `app/storage/local.py`).

## Status

This is the initial engine scaffold: project structure, config, OpenRouter integration, the full
LangGraph workflow skeleton, multi-modal ingestion, and the Resume vertical are wired end-to-end and
runnable. Remaining work per the scope doc's 6-week plan: hardening the extraction/generation prompts
against real sample resumes, Arabic QA, API auth, deployment, and documentation polish.
