# Radox AI + Hindi Shorts Lab (test-only)

A manually triggered GitHub Actions workflow that diagnoses Radox's OpenAI-compatible chat endpoint and compares a small set of model candidates on the same fictional Hindi Shorts script task. It never publishes to YouTube and does not call image-generation endpoints.

## What it checks

- Authenticated `GET /v1/models` and model metadata.
- Actual non-empty text extraction from chat-completion responses. An HTTP 200 with missing/empty message text is now marked **FAIL**, not PASS.
- By default, compares available candidates among `claude-fable-5`, `gpt-5.6-sol`, `gemini-3.7-flash`, and `qwen3.8-max`. The list is a test shortlist, not a claim that these are the best or cheapest models.
- Optional JSON mode, streaming, and tool-calling probes.
- Writes `output/radox-report.json` and `output/radox-report.md` as an Actions artifact.

## Setup

1. Upload these files to a new GitHub repository, preserving `.github/workflows/`.
2. Rotate/revoke any API key previously shared in chat. Add the replacement in **Settings → Secrets and variables → Actions** as `RADOXAI_API_KEY`.
3. Open **Actions → Radox API Diagnostic and Model Comparison → Run workflow**.
4. First run: leave `model_id` blank, keep model comparison on, and keep extended tests off. Model comparison makes up to four small chat calls, depending on which candidates exist in the catalog.
5. Download the `radox-api-test-report` artifact and review the Markdown and JSON reports.

To test only one model, enter its exact ID in `model_id`; this skips the comparison shortlist. Turn on extended tests only if you accept the additional API calls.

## Limitations

- This is a diagnostic, not a complete news production workflow.
- The test story is fictional, so the test cannot establish current-news accuracy.
- Vision input does not imply image generation. Image generation, real-news retrieval, Hindi TTS, visual sourcing, rendering and YouTube publishing are not tested or implemented here.
- Model listing capability fields may be absent even when a feature works, so runtime results matter more than zero capability counts.
- No secret is written into the report or printed by the script.
