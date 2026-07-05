# Credentials

None in v1 — docmend is fully offline (spec §13.3). If an external service is integrated later (LLM APIs, OCR, cloud storage), credentials must be read from environment variables only, documented in a `.env.example` (never a real `.env`), and never hardcoded or committed. Paths/names only belong here — never secret values.
