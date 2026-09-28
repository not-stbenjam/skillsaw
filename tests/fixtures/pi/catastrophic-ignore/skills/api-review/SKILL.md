---
name: api-review
description: Use when reviewing changes to the service's HTTP handlers or response schemas.
---

# API review

Read each changed handler and confirm that:

- Every error path returns a structured error body with a stable `code`.
- New fields in response schemas are optional for existing clients.
- Pagination parameters are validated before they reach the database layer.

Summarize any breaking change at the top of the review.
