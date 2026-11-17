Authors: Jacob Wills-Brennan, Luke Vogel, Belqis Wahidi

# Timberwick Support Assistant

An AI customer service platform for Timberwick Outfitters, a fictional outdoor and camping gear
store. Customers ask questions in a chat, the AI answers from an approved knowledge base, and
anything the AI can't answer confidently is handed to a human agent as a support ticket.

This is the Alpha release. It covers the core flow end to end through the API. There is no
user interface yet; the built-in Swagger page at `/docs` is used to try it out.

> **Project history:** This project began as SkillPath AI, a workforce training recommender, and moved to this customer service platform starting with our Unit 3 design specification.

## What works in the Alpha

- Login with hashed passwords and short-lived bearer tokens, with customer and agent roles
- Customers chat with the AI and can continue a conversation across messages
- The AI answers from 16 approved help articles and cites the article it used
- Automatic escalation to a ticket when the customer asks for a person, asks for an account
  change, or the AI's confidence is too low
- Safe fallback: if the AI fails, the customer gets a ticket instead of an error
- Agents list tickets, filter by status, and assign or resolve them
- One consistent error format across every endpoint
- CI on every push: lint, format check, 59 tests with a 90% coverage minimum, and an AI
  quality check

## Tech stack

Python 3.12, FastAPI, SQLAlchemy, SQLite (PostgreSQL planned), scikit-learn, PyJWT, pytest, ruff

## Setup

Requires Python 3.12 or newer.

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set `SECRET_KEY` to a long random string.

## Run it

```bash
python -m app.seed
uvicorn app.main:create_app --factory --reload
```

`python -m app.seed` only needs to be run once. It creates these demo accounts:

| Role | Email | Password |
|---|---|---|
| Customer | `customer@timberwickexample.com` | `customer-demo-pass` |
| Agent | `agent@timberwickexample.com` | `agent-demo-pass` |

Leave the terminal open while you use the app. Press **Ctrl+C** in it to stop the server.

## Demo walkthrough

Open http://127.0.0.1:8000/docs in your browser. Every endpoint works the same way on this page:
click the endpoint's row to open it, click **Try it out**, fill in the boxes, click the blue
**Execute** button, then scroll down to **Server response** to see the result.

### Part 1: Customer

**Step 1. Log in as the customer.**
Open `POST /api/v1/auth/login` and click **Try it out**. The request body is already filled in
with the customer account. Click **Execute**. In the response body, copy the long
`access_token` value (only the text inside the quotes).

**Step 2. Tell the page who you are.**
Click the **Authorize** button with the lock icon at the top right. Paste the token into the
**Value** box, click **Authorize**, then **Close**. Every request you make now is sent as the
customer.

**Step 3. Ask a question the AI can answer.**
Open `POST /api/v1/chat/messages`, click **Try it out**, and click **Execute**. The prefilled
question asks about a broken tent zipper. You should see:
- `reply`: the tent warranty article
- `confidence`: about 0.52
- `cited_article_ids`: the ID of the article the answer came from
- `escalated`: `false`

Copy the `conversation_id` value. You need it for Steps 4 and 5.

**Step 4. Ask for a person.**
Stay in the same endpoint. Above the request body there is an **Examples** dropdown. Choose
**Ask for a person (paste your conversation_id)**. In the request body, replace
`PASTE-CONVERSATION-ID-HERE` with your conversation ID (keep the quotes), then click
**Execute**. You should see `escalated: true`, a `ticket_id`, and a reply that includes the
ticket number.

**Step 5. View the whole conversation.**
Open `GET /api/v1/conversations/{conversation_id}`, click **Try it out**, paste the
conversation ID into the `conversation_id` box, and click **Execute**. You should see all four
messages in order and a `status` of `escalated`.

**Optional: try the other examples.**
In `POST /api/v1/chat/messages`, pick these from the **Examples** dropdown and click **Execute**:
- **New question with no approved answer** (`Do you sell kayaks?`) escalates because no
  approved article covers it
- **New question that needs an account change** (`I forgot my password`) escalates because
  account changes need a person

You can also type your own question in place of the message text.

### Part 2: Agent

**Step 6. Log in as the agent.**
Open `POST /api/v1/auth/login` again and click **Try it out**. In the **Examples** dropdown,
choose **Demo agent account**. Click **Execute** and copy the new `access_token`.

**Step 7. Switch to the agent.**
Click **Authorize**, click **Logout**, paste the agent token into **Value**, click
**Authorize**, then **Close**.

**Step 8. See the ticket queue.**
Open `GET /api/v1/agent/tickets`, click **Try it out**, leave the boxes empty, and click
**Execute**. Your ticket from Step 4 is listed with `status: open` and the reason
`customer_requested_agent`. Copy its `ticket_id`.

**Step 9. Resolve the ticket.**
Open `PATCH /api/v1/agent/tickets/{ticket_id}`, click **Try it out**, paste the ticket ID into
the `ticket_id` box, and click **Execute**. The prefilled body sets the status to `resolved`.
The response shows the ticket with `status: resolved`.

### If something goes wrong

- **`invalid_credentials` when logging in:** stop the server, delete `support.db`, run
  `python -m app.seed` again, and restart the server.
- **`unauthenticated` or `token_expired`:** tokens last 30 minutes. Log in again and repeat the
  Authorize step.
- **`forbidden`:** you are authorized as the wrong role. Customers can only chat, and agents can
  only use the ticket endpoints.

## Run the tests

```bash
ruff check .
ruff format --check .
pytest -v --cov=app --cov-fail-under=90
```

`tests/test_ai_quality.py` scores the AI on 30 questions that are not in the knowledge base.
CI fails if answer accuracy drops below 80%, escalation recall drops below 90%, or more than
15% of answers cite the wrong article. Current results: 85% accuracy, 100% escalation recall,
10% wrong-article rate.

## Project layout

| Path | Purpose |
|---|---|
| `app/main.py` | Creates the app and connects all modules |
| `app/auth.py` | Login, tokens, password hashing, role checks |
| `app/conversations.py` | Chat endpoints; connects the AI and ticket modules |
| `app/orchestrator.py` | Decides whether to answer or escalate |
| `app/retriever.py` | Searches the knowledge base with scikit-learn |
| `app/tickets.py` | Ticket creation and agent ticket endpoints |
| `app/models.py`, `app/database.py` | Database tables and connection |
| `app/schemas.py`, `app/errors.py` | API contracts and the shared error format |
| `app/config.py` | Settings from environment variables |
| `app/seed.py` | Creates the demo accounts |
| `data/knowledge_base.json` | Approved help articles (Author: Belqis Wahidi) |
| `docs/architecture.md` | Module diagram, data model, Alpha scope |
| `docs/api.md` | Endpoint and interface specification |
| `TECH_DEBT.md` | Known shortcuts in this release and how they will be fixed |

## Planned for the final release

- Customer and agent web interface
- Feedback endpoint so customers can rate answers
- Calibrated AI confidence and more knowledge base articles
- PostgreSQL with database migrations
- Agent queues, rate limiting, and request ID deduplication
- CRM adapter for customer account lookups
