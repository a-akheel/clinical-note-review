# Security configuration and limitations

## Implemented

- Loopback-only native server; Docker port mapping binds to 127.0.0.1.
- Random 256-bit local password, constant-time comparison, required on application and API routes.
- Password and database files use owner-only permissions; local data directory is owner-only. Launcher sets umask 077.
- Secrets and data are excluded from source control and Docker build context.
- Server-side API credentials; fixed HTTPS provider endpoint; no arbitrary outbound endpoint input.
- Provider request sets store=false. This alone is not a guarantee of zero provider retention.
- Same-origin mutation checks, cross-site browser access blocking, trusted host checks, JSON mutation requirement, request size and schema limits.
- Content Security Policy, frame blocking, no-store responses, restricted browser permissions, no external scripts or fonts.
- SQL parameters for record data; output escaping; immutable approved records and stale revision checks.
- Access logging disabled by the native launcher. Generation events do not contain transcript text.

## Limits

Basic authentication is used only on loopback HTTP. It is not encryption. Do not bind the native app to 0.0.0.0 or deploy it publicly. The password is not an operating-system security boundary: processes under your account can read it. Browser credentials may stay cached; close the browser when finished. To rotate the local password, stop the server, replace data/.local-password with a new cryptographically random value, and restart.

SQLite is not encrypted by this application. Use macOS FileVault and a locked user account to protect the device; this project does not change those system settings. Backups, downloaded JSON, and screenshots require their own protection. No role-based authorization, tamper-proof audit service, or production security audit is included.

Live generation sends synthetic transcripts to OpenAI. The app does not redact patient identifiers automatically. Do not use real patient information. Prompt instructions and citations do not guarantee factual correctness or defeat all prompt injection.

API spending controls must be configured in the provider account. There is no global application spend cap or comprehensive rate limiter. Evaluation concurrency is limited to two runs, but each may make up to 30 model calls.

## Credential hygiene

Keep .env and data/.local-password local. Never paste secrets into chat or commit them. Revoke exposed API keys in the provider dashboard. Use a dedicated API project/key and only the permissions needed for model requests. Consult the provider's current controls before relying on them.

## Validation

Automated tests cover unauthorized access, invalid credentials, cross-site reads and writes, browser headers, private database permissions, malformed input, invalid citations, stale writes, and approval requirements. These are regression checks, not an independent penetration test.

## Local Ollama mode

The dedicated launcher sets OLLAMA_NO_CLOUD=1, binds 127.0.0.1:11434, and limits loaded models and queued requests. The app uses a fixed local model and fixed localhost URL, with HTTP proxy environment settings ignored. Ollama has a separate unauthenticated local API: the application password does not protect that port from other processes on your Mac. Do not expose it on your network. Model downloads need internet access; inference uses the downloaded model.
