# ReceptHyveln

A lightweight web app that takes a recipe URL, extracts ingredients and cooking steps, and displays them in a clean, cookbook-style page — without ads, images, or clutter.

Nothing is saved on the server. Results live only in your browser tab (optionally restored from `sessionStorage` on refresh).

Licensed under [GNU GPLv3](LICENSE).

## How it works

1. You paste a recipe URL.
2. The server fetches the page HTML (with SSRF protection and rate limiting).
3. The backend extracts structured recipe data using a fallback chain:
   - [recipe-scrapers](https://github.com/hhursev/recipe-scrapers) (Schema.org JSON-LD, microdata, site parsers)
   - HTML structure parsers (grouped ingredients from tables, `<br>` blocks, JSON-LD headers)
   - Generic section parser (`INGREDIENSER` / `Gör så här` headings)
4. The frontend renders a simple, printable recipe card with optional measurement conversion hints.

## Quick start

**Requirements:** Python 3.12+

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

Run tests:

```bash
pytest
```

API docs (development only):

```bash
OPENAPI_DOCS=true uvicorn app.main:app --reload
```

Then open `/docs`.

## Docker

Build and run:

```bash
docker build -t recept-hyveln .
docker run -p 8000:8000 recept-hyveln
```

With Docker Compose (copy `.env.production.example` to `.env` first if you need custom settings):

```bash
docker compose up -d
curl -s http://127.0.0.1:8000/health
```

`docker-compose.yml` binds to `127.0.0.1:8000` by default.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_ORIGINS` | `*` | Browser origins allowed to call the API (CORS) |
| `ALLOWED_HOSTS` | `*` | Allowed `Host` header values |
| `ALLOWED_FETCH_PORTS` | `80,443` | Ports the server may fetch recipe URLs from |
| `OPENAPI_DOCS` | off | Expose `/docs` and `/redoc` |
| `TRUST_PROXY_HEADERS` | off | Use `X-Forwarded-For` for rate limiting behind a proxy |
| `EXTRACT_TIMEOUT` | `15` | Max seconds for recipe parsing per request |
| `MAX_CONCURRENT_FETCHES` | `5` | Max simultaneous outbound HTTP fetches |

When the HTML and API are served from the same URL, CORS usually does not matter. Set `ALLOWED_ORIGINS` and `ALLOWED_HOSTS` to your real domain in production.

Hosting, VPS bootstrap, and CI deploy: **`DEPLOY.md`** (local file, gitignored).

## API

**`POST /api/extract`**

```json
{ "url": "https://www.ica.se/recept/..." }
```

Response:

```json
{
  "title": "Klassisk köttfärssås",
  "yield": "4 portioner",
  "ingredients": ["500 g köttfärs", "..."],
  "ingredient_groups": [
    { "title": null, "ingredients": ["500 g köttfärs", "..."] }
  ],
  "steps": ["Hacka löken.", "..."],
  "measurement_hints": [
    { "from": "1 cup", "to": "2,4 dl" }
  ]
}
```

`measurement_hints` is only included when imperial or English units are detected. Ingredient text is not converted automatically.

Rate limit: 10 requests per minute per IP.

**`GET /health`** — returns `{ "status": "ok" }`.

## Security

- SSRF protection with DNS validation, private-IP blocking, port allowlist, and IP pinning
- Redirects are re-validated (max 5)
- Response size and fetch timeouts are enforced
- Security headers (CSP, `X-Frame-Options`, `nosniff`, etc.)
- Rate limit: 10 requests per minute per client IP

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Limitations

- Some sites block automated fetching; those URLs may fail with a clear error.
- Obscure blogs without structured recipe markup may not be extractable.
- This tool is for personal reading convenience — respect the terms and copyright of source websites. Extracted content remains the property of its original publisher.

## License

This project is licensed under the GNU General Public License v3.0 or later. See [LICENSE](LICENSE).
