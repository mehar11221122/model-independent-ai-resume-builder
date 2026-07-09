# Milestone 1 Checklist — Free-Tier Plan

Tracks what's left to finish Milestone 1 (AI Engine + Resume module) using the
$0/month stack from `Free_Tier_Resource_Plan.docx` (Render + Neon + Cloudflare
R2 + OpenRouter free models + Tesseract + GitHub Actions).

## Engineering tasks (agent-owned, no external accounts needed)

- [ ] Implement a Cloudflare R2 / S3-compatible storage backend (drop-in for local disk)
- [ ] Add retry/backoff handling for OpenRouter free-model rate limits (429s)
- [ ] Write `render.yaml` for one-click Render deployment
- [ ] Set up GitHub Actions CI (lint + pytest on every push)
- [ ] Add unit tests for ingestion loaders, resume validation rules, and graph routing logic (mocked LLM calls, no API key needed)
- [ ] Harden resume extraction/generation prompts once real sample resumes are provided
- [ ] Run a full English + Arabic end-to-end test once a real OpenRouter key is added
- [ ] Polish API and architecture documentation for handover

## Your action items (accounts & external dependencies)

- [ ] Create a free **OpenRouter** account → generate an API key → add it to `.env` as `OPENROUTER_API_KEY`
- [ ] Push this project to a **GitHub** repo (free)
- [ ] Create a free **Render** account → connect the GitHub repo → deploy the web service
- [ ] Create a free **Neon** account → create a Postgres project → copy the connection string into `POSTGRES_DSN` (and set `CHECKPOINT_BACKEND=postgres`)
- [ ] Create a free **Cloudflare** account → create an R2 bucket + API token → add the credentials once the R2 storage backend is implemented
- [ ] Provide sample resumes, PDFs, Word docs, and scanned/photographed images for QA of extraction and OCR accuracy (per the scope doc's stated dependency)
- [ ] Arrange a native Arabic speaker/reviewer to validate generated Arabic resume content (per the scope doc's stated dependency)
- [ ] Review `Free_Tier_Resource_Plan.docx` with your manager and confirm the free-tier plan is approved
- [ ] Once deployed, smoke-test the live API at `/docs` and share feedback

## Notes
- Nothing here blocks the other side from progressing — engineering tasks can proceed in parallel with account setup.
- Once you've completed the account-creation items, send over the API key / connection strings / bucket credentials and I'll wire them in and redeploy.
