```md
# Open Fuel API

A free, public API for current South African fuel prices and monthly fuel-market summaries.

**Live API:** https://open-fuel-api.chiboyfeni.workers.dev

## Quick start

```bash
curl https://open-fuel-api.chiboyfeni.workers.dev/fuel/all
```

No API key is required.

## Endpoints

| Endpoint | Description |
| --- | --- |
| `GET /fuel/all` | All ten latest fuel prices |
| `GET /fuel/{fuel_type}/{location}` | One fuel price |
| `GET /fuel/history` | Up to 12 months of history |
| `GET /news` | Latest petrol and diesel summaries |
| `GET /news/{fuel_type}` | Petrol or diesel summary |

Fuel types: `unleaded93`, `unleaded95`, `diesel500`, `diesel50`, `lrp93`  
Locations: `inland`, `coast`

## Example

```json
{
  "fuel_type": "unleaded95",
  "location": "inland",
  "price": 24.85
}
```

## How it works

```text
AA fuel data → monthly scraper → Cloudflare D1 → Open Fuel API
```

The API is public and read-only. Data is validated before being stored in D1.

Built with FastAPI, Cloudflare Python Workers, and Cloudflare D1.
```
