# Miaoon Customer Support Agent (real AI)

A conversational AI support agent for miaoon.in. Works with free AI providers (Gemini, Groq, Ollama) or Claude. It reads a company profile, understands any phrasing, remembers the conversation, answers in Miaoon's brand voice, and hands complex cases to your team with a summary, contact details and the full chat. Text only. There is no Q&A list: the model reasons over `data/knowledge.md`.

Python 3.9+ only. No packages to install.

## Run it

    cp .env.example .env     # set GEMINI_API_KEY (free) and ADMIN_TOKEN
    python server.py

- Chat demo: http://localhost:8000
- Team dashboard: http://localhost:8000/admin (asks for ADMIN_TOKEN)
- Tests (Claude mocked): `python -m unittest discover -s tests`

## Put it on miaoon.in

1. Deploy this folder (Docker, Railway, Render, or a VPS behind Caddy/nginx for HTTPS). Keep `/app/data` on a persistent disk.
2. Add before `</body>` on your site: `<script src="https://YOUR-DOMAIN/widget.js" defer></script>`
3. Set `ALLOWED_ORIGINS` to your site, and `NOTIFY_TO` plus SMTP or `SLACK_WEBHOOK_URL` for handoff alerts.

## How it works

- **Brain:** the AI model gets `voice.md` (personality and rules) + `data/knowledge.md` (company facts) + the last 20 messages on every turn.
- **Honesty:** facts come only from the knowledge base. Anything under "NOT published" (pricing, timelines, contracts...) is never guessed; the agent says the team will confirm.
- **Handoff:** Claude calls a `hand_off_to_team` tool (lead, complaint, urgent, support) with a summary. A keyword safety net ("human", "refund", "complaint", "urgent" and similar) always reaches a person, even if the model misses it. The agent asks for an email or WhatsApp number, creates a ticket, and alerts you by email and/or Slack.
- **Human takeover:** reply from `/admin`; it appears live in the customer's chat. The bot stays silent until you click "Mark resolved".
- **If the AI is unreachable:** the visitor is handed to your team instead of seeing an error.
- **Security:** message length cap, rate limit, CORS allowlist, admin token; customer text is treated as data, never as instructions.

## Make it yours

- `data/knowledge.md`: company facts. Add pricing, packages, policies and FAQs in plain prose when ready; the agent will use them. Restart to reload.
- `voice.md`: tone and rules.
- `LLM_PROVIDER` / `LLM_MODEL` in `.env`: switch between gemini, groq, openrouter, ollama (free) or anthropic (paid).

## Free tier notes

- Free tiers are rate-limited. If the limit is hit, the visitor is handed to your team instead of seeing an error. Check your limits in the provider's dashboard.
- Google's free Gemini tier may use the content you send to improve Google products. Don't use it for sensitive customer data; for full privacy use Ollama on your own server, or a paid plan.
- Free quality is a notch below Claude. Test a few real chats, then upgrade the provider later by changing two lines in `.env`.

## Before you go live

- Fill the gaps in `data/knowledge.md` that say "NOT published", or the agent will keep handing those questions to your team.
- Run a few real chats with your key. The live API calls were only tested with mocked responses, because my build environment had no internet.
- The widget tells visitors they're talking to an AI and that chats are saved. Link a privacy policy on your site (India's DPDP Act 2023).
- Single-server design (SQLite, in-memory rate limit). Fine for a company site.
