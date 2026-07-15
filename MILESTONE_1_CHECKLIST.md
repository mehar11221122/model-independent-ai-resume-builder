# Milestone 1 Checklist — Card-Free Plan

Tracks what's left to finish Milestone 1 (AI Engine + Resume module) using the
fully card-free stack from `Free_Tier_Resource_Plan.docx` (OpenRouter free
models + GitHub/GitHub Actions + local hosting + Cloudflare Quick Tunnel +
SQLite + local disk + Tesseract — no account or card needed anywhere except
OpenRouter and GitHub, both already done).

## Agent-owned tasks (everything is CLI-driven now — no GUI signups left)

- [x] Delete the old Render/Belmo/Neon/R2-based plan and checklist
- [x] Install the `cloudflared` CLI (no account required)
- [x] Regenerate `Free_Tier_Resource_Plan.docx` for the new card-free stack
- [x] Regenerate this checklist
- [x] Start the FastAPI engine locally (`uvicorn`)
- [x] Start a Cloudflare Quick Tunnel pointed at the local engine and share the
      public `trycloudflare.com` link
- [x] Run a real end-to-end resume generation test through free OpenRouter
      models to confirm the whole path works (extraction → gap detection →
      clarification → answer merge → generation → validation → completed)
- [ ] Keep the server + tunnel running in background terminals so the link
      stays live; restart and re-share the link whenever it drops
- [ ] Harden resume extraction/generation prompts once real sample resumes
      are provided
- [ ] Run a full English + Arabic end-to-end test once sample documents and
      an Arabic reviewer are available

## Your action items (things only a human can provide)

- [ ] Provide sample resumes, PDFs, Word docs, and scanned/photographed
      images for QA of extraction and OCR accuracy (per the scope doc's
      stated dependency)
- [ ] Arrange a native Arabic speaker/reviewer to validate generated Arabic
      resume content (per the scope doc's stated dependency)
- [ ] Review `Free_Tier_Resource_Plan.docx` with your manager and confirm the
      revised, fully card-free plan is approved
- [ ] Whenever you want to demo the engine, just ask — I'll (re)start the
      local server + tunnel and hand you a fresh live link (it changes each
      time the tunnel restarts, since no permanent account is used)

## Notes

- No further account creation, card entry, or web-based signup is required
  anywhere in this plan. The only two external accounts in use (OpenRouter,
  GitHub) are already set up and working.
- This is a demo-ready deployment, not a 24/7 production one — the public
  link only works while the local server + tunnel are running. Per Section 8
  of the scope document, a permanent cloud deployment is intentionally
  deferred until after the MVP is validated, and moving to one later is a
  configuration change, not a rebuild (the app is already Dockerized and
  model-independent via OpenRouter).
