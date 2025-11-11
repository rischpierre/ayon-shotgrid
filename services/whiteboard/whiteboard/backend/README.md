Whiteboard Backend Notes

- 2025-11-11: Annotations now persist by absolute calendar date keys (YYYY-MM-DD). The POST /api/annotations endpoint converts the provided (week, day) into an ISO date and stores under that key. GET /api/week maps stored ISO dates that fall within the requested week back to legacy keys like "w0/mon" for UI display. Legacy keys are still read and are removed on next write to avoid drift over time.
