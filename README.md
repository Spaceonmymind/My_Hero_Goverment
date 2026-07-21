## Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

uvicorn app.main:app --reload
```

## MAX bot webhook

Webhook endpoint: `/max/webhook`.

Set these environment variables:

```bash
MAX_BOT_TOKEN=your_max_bot_token
MAX_VERIFY_SSL=true
MAX_WEBHOOK_SECRET=your_webhook_secret
MAX_MINI_APP_URL=https://max.ru/your_bot_username?startapp
```

Subscribe the bot to `bot_started` and `message_created` events in MAX.

For MAX WebView on HTTPS production, set:

```bash
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
AUTH_URL_TOKEN_ENABLED=true
```
