# Vera — magicpin AI Challenge

A deterministic Python WhatsApp assistant that composes merchant- and customer-facing messages from category, merchant, trigger, and optional customer context.

## Files and approach

- `app.py` exposes `/v1/context`, `/v1/tick`, `/v1/reply`, `/v1/healthz`, and `/v1/metadata`.
- `bot.py` routes by trigger type and composes concise, context-grounded messages. It avoids unsupported claims, handles opt-outs and repeated auto-replies, and moves to an action when the merchant agrees.
- `dataset/` contains challenge seeds and the dataset generator. `Dockerfile` is for deployment.

The bot is deterministic and uses Python’s standard library; it needs no model key. Tradeoff: rule-based routing is predictable and inexpensive, but novel trigger types may receive a generic fallback. More complete customer consent, merchant language, and updated performance context would improve personalization.

## Run and test locally

Use Python 3.10 or later. In the project folder, start the bot and leave it running:

```bash
python3 app.py
```

In a second terminal, check the API:

```bash
curl http://localhost:8080/v1/healthz
curl http://localhost:8080/v1/metadata
```

For the judge simulator, set `BOT_URL = "http://localhost:8080"`, `LLM_PROVIDER = "openrouter"`, `LLM_API_KEY = os.getenv("OPENROUTER_API_KEY", "")`, and `LLM_MODEL = "openai/gpt-4o-mini"` in `judge_simulator.py`. Its API key is only for local scoring; the bot does not need it. Each user supplies their own key—never commit it or put it in this README. With the bot still running, enter the key privately in another terminal and run:

```bash
read -s "OPENROUTER_API_KEY?Paste your key (input hidden): "
export OPENROUTER_API_KEY
python3 judge_simulator.py
unset OPENROUTER_API_KEY
```

## Deploy and submit

Publish the project files to a Git repository without secrets. Create a public web service from that repository and select Docker to build the included `Dockerfile`. Once live, verify `/v1/healthz` and `/v1/metadata` on the HTTPS address. Submit the **base URL** (for example, `https://your-service.onrender.com`) in the challenge form—not a route or repository URL—and keep the service available during evaluation. See Render’s [Web Services guide](https://render.com/docs/web-services).
