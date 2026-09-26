# Vera — magicpin AI Challenge

A deterministic WhatsApp assistant that composes merchant and customer messages from the challenge’s category, merchant, trigger, and optional customer contexts.

## Project and approach

- `app.py` serves `/v1/context`, `/v1/tick`, `/v1/reply`, `/v1/healthz`, and `/v1/metadata`.
- `bot.py` uses category voice, digest, trends, seasonal beats, peer benchmarks, merchant performance/offers/signals/history, and customer relationship/preferences/consent to compose messages.
- `dataset/` contains the supplied context seeds and deterministic dataset generator. `make_submission.py` creates the 30-pair JSONL deliverable. `Dockerfile` deploys the API.

The API stores contexts as the judge pushes them; it does not preload them at startup. This keeps initial health counts at zero and lets newer context versions replace older ones. The composer is deterministic and uses no model key. Tradeoff: rules are auditable and avoid external calls, while unfamiliar trigger types get a conservative fallback.

## Run, test, and generate submission

Use Python 3.10 or later. In one terminal, run `python3 app.py`. In another, check `curl http://localhost:8080/v1/healthz` and `curl http://localhost:8080/v1/metadata`. Keep the server running while testing.

`judge_simulator.py` uses an OpenRouter key only to score locally; the bot does not need it. Set `BOT_URL = "http://localhost:8080"`, `LLM_PROVIDER = "openrouter"`, `LLM_API_KEY = os.getenv("OPENROUTER_API_KEY", "")`, and `LLM_MODEL = "openai/gpt-4o-mini"` in its configuration. Use your own key; never commit or share it. In a second terminal, enter it privately and run the simulator:

```bash
read -s "OPENROUTER_API_KEY?Paste your key (input hidden): "
export OPENROUTER_API_KEY
python3 judge_simulator.py
unset OPENROUTER_API_KEY
```

To build the canonical 30-pair output from all generated contexts:

```bash
python3 dataset/generate_dataset.py --seed-dir dataset --out /tmp/magicpin-expanded
python3 make_submission.py --dataset /tmp/magicpin-expanded
```

This writes `submission.jsonl` in the project root. Customer outreach with no matching consent is intentionally suppressed.

## Deploy and submit

Publish the project to GitHub without secrets. Create a public web service from the repository and choose Docker to build `Dockerfile`. After deployment, verify `/v1/healthz` and `/v1/metadata` on the HTTPS host. Submit the **base URL** (for example, `https://your-service.onrender.com`)—not a route or repository URL—and keep the service available during evaluation. See [Render Web Services](https://render.com/docs/web-services).
