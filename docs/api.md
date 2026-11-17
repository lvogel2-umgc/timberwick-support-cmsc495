Author: Luke Vogel

# API Specification

All endpoints use JSON. IDs are UUID strings and timestamps are ISO 8601 in UTC. Protected
endpoints need an `Authorization: Bearer <token>` header from the login endpoint. The user's
identity always comes from the token, never from the request body. Request bodies reject
unknown fields.

Interactive documentation is generated at `/docs` while the app is running. It lists the
real error responses (400, 401, 403, 404) in the shared format below.

## Error format

Every error uses the same shape. The `request_id` matches the `X-Request-ID` response header.

```json
{"error": {"code": "invalid_input", "message": "message: String should have at least 1 character", "request_id": "6b1f..."}}
```

| Status | Codes | When |
|---|---|---|
| 400 | `invalid_input`, `invalid_transition` | Bad or missing fields, unknown fields, invalid ticket status change |
| 401 | `unauthenticated`, `invalid_credentials`, `token_expired` | Missing, invalid, or expired token; wrong login |
| 403 | `forbidden` | Wrong role, or another customer's conversation |
| 404 | `not_found` | Conversation or ticket does not exist |
| 500 | `internal_error` | Unexpected error (no stack trace is returned) |

## Endpoints

### POST /api/v1/auth/login
No token needed.

Request: `{"email": "customer@timberwickexample.com", "password": "..."}`

Emails are case-insensitive and surrounding spaces are ignored. An unknown email and a wrong
password return the same `invalid_credentials` error and take the same time, so responses do
not reveal which accounts exist.

Response 200: `{"access_token": "...", "token_type": "bearer", "role": "customer"}`

### POST /api/v1/chat/messages
Customer token. Starts a new conversation when `conversation_id` is left out.

Request:
```json
{"conversation_id": "optional UUID", "message": "1 to 2000 characters"}
```

Response 200:
```json
{
  "conversation_id": "UUID",
  "message_id": "UUID",
  "reply": "Refunds go back to your original payment method within 5 to 7 business days...",
  "confidence": 0.65,
  "cited_article_ids": ["UUID"],
  "escalated": false,
  "ticket_id": null
}
```
When `escalated` is true, `ticket_id` is set and the reply includes the ticket number.

### GET /api/v1/conversations/{id}
Customer token (own conversations only) or agent token (any conversation).

Response 200:
```json
{
  "id": "UUID",
  "status": "open",
  "messages": [{"message_id": "UUID", "role": "customer", "text": "...", "timestamp": "2026-01-01T12:00:00+00:00"}]
}
```

### GET /api/v1/agent/tickets
Agent token. Optional query parameters: `status` (`open`, `assigned`, `resolved`) and
`limit` (1 to 100, default 50). Newest tickets first.

Response 200:
```json
{"items": [{"ticket_id": "UUID", "conversation_id": "UUID", "reason": "low_confidence", "summary": "...", "status": "open", "assigned_agent_id": null, "created_at": "...", "updated_at": "..."}]}
```

Escalation reasons: `customer_requested_agent`, `account_change_requires_agent`,
`no_approved_answer`, `low_confidence`, `ai_unavailable`.

### PATCH /api/v1/agent/tickets/{id}
Agent token.

Request: `{"status": "assigned", "assigned_agent_id": "optional UUID"}`

Allowed status changes: open to assigned or resolved, assigned to open or resolved. Resolved
tickets cannot be changed. Assigning without `assigned_agent_id` assigns the ticket to the
agent making the request.

Response 200: the updated ticket, same shape as in the list.

### GET /health
No token needed. Response 200: `{"status": "ok"}`

## Internal interfaces

These are the contracts between modules, so each one can be swapped out on its own.

```python
KnowledgeRetriever.search(query: str, top_k: int = 5) -> list[KnowledgeMatch]
AIOrchestrator.respond(message: str) -> AIResult
ConversationService.send_message(user: User, message: str, conversation_id: str | None) -> ChatResult
EscalationService.create_ticket(conversation: Conversation, reason: str, summary: str) -> Ticket
```

- `KnowledgeMatch`: `article_id`, `title`, `excerpt`, `relevance_score` (0.0 to 1.0). An empty
  list means no approved article matched.
- `AIResult`: `reply`, `confidence` (0.0 to 1.0), `cited_article_ids`, `needs_escalation`,
  `reason`.
- `create_ticket` returns the conversation's existing unresolved ticket if there is one, so a
  conversation never gets duplicate tickets.
