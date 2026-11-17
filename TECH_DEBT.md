Authors: Jacob Wills-Brennan, Luke Vogel, Belqis Wahidi

# Technical Debt Register

Shortcuts we took on purpose to deliver a working Alpha, what each one will cost if left
alone, and how we plan to fix it. Items are ordered by risk.

| # | Shortcut | Impact if not fixed | Mitigation plan | Owner |
|---|---|---|---|---|
| 1 | **Confidence is raw TF-IDF similarity instead of a probability.** Our design spec from unit 3 escalates below 0.70, but raw scores for correct answers are currently ~0.35 to 0.60, so the Alpha threshold is 0.30. | A threshold tuned on a small set may answer wrong questions with confidence or escalate good ones as the knowledge base grows. Two of 20 test questions currently cite the wrong article. | Grow the test set, then calibrate scores (for example with scikit-learn's `CalibratedClassifierCV`) so 0.70 means what the spec intended. Re-run `test_ai_quality.py` after every knowledge base change. | Belqis Wahidi |
| 2 | **Escalation rules are hardcoded keyword lists** in `orchestrator.py`. | New phrasings ("can I get a manager?") slip through, and every change needs a code edit and redeploy. | Move rules to a reviewed config file, add test cases for each new phrasing, and later replace keywords with an intent classifier. | Belqis Wahidi |
| 3 | **Default secret key and demo passwords** are used when `.env` is missing. | If deployed as-is, anyone who reads the repo could forge login tokens or sign in as the agent. | Make the app refuse to start without `SECRET_KEY` outside development, and remove default demo passwords before deployment. | Luke Vogel |
| 4 | **No rate limiting and no refresh tokens.** | Login can be brute-forced, and users must log in again every 30 minutes. | Add per-user and per-IP rate limits (429 responses in the spec) and a refresh token flow. | Luke Vogel |
| 5 | **No request ID deduplication.** The spec's `client_request_id` is not implemented. | A client that retries after a network error creates duplicate messages. | Add `client_request_id` to the chat request with a unique constraint and return the original result on repeats. | Luke Vogel |
| 6 | **SQLite with tables created at startup** instead of PostgreSQL with migrations. | Schema changes would require deleting the database, and SQLite does not handle many users writing at once. | Switch to PostgreSQL and add Alembic migrations before the schema changes again. The SQLAlchemy models already work with both. | Jacob Wills-Brennan |
| 7 | **All agents see all tickets.** There are no queues or queue permissions. | Agents could see tickets outside their area, which breaks least-privilege access in the spec. | Add a queue field to tickets and agents, and filter ticket queries by the agent's queues. | Jacob Wills-Brennan |
| 8 | **The AI call is synchronous with no timeout.** | One slow AI call holds up the request, and under load the API slows down for everyone. | Add a timeout around `respond()` and move AI work to a background queue as described in the design spec. | Jacob Wills-Brennan |
| 9 | **The knowledge base is a JSON file loaded at startup.** | Article updates need a restart and have no review or approval record. | Store articles in the database with an approved flag and reload the index when articles change. | Belqis Wahidi |
