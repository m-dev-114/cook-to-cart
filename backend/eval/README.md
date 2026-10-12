# Evaluation harness
`cd backend && python -m eval.run_eval` runs parse -> interpret -> retrieve -> validate -> rank -> quantity over mocked, live-shaped catalogs (`catalog.py`, never served to users).
Metrics: interpretation accuracy, suitable-product retrieval, auto-selection accuracy, incorrect exact-match rate, forbidden products labelled exact/suitable, unavailable-not-auto-selected, pack coverage, duplicate cart lines, search failures, latency.
Caveat: the dataset was written and then used to fix matching bugs, so the dev/held-out labels no longer mean "unseen". Re-run with fresh recipes after changes.
Optional model layer: set GROQ_API_KEY or ANTHROPIC_API_KEY (same as recipe extraction). Without a key the pipeline falls back to rules + live validation.
