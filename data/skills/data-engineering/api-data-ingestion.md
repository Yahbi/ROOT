---
name: API Data Ingestion
description: Build reliable pipelines to ingest data from REST APIs, webhooks, and third-party services
version: "1.0.0"
author: ROOT
tags: [data-engineering, API, ingestion, REST, webhooks, rate-limiting, pagination]
platforms: [all]
difficulty: intermediate
---

# API Data Ingestion

Reliably extract data from external APIs while handling rate limits, pagination,
authentication, and partial failure gracefully.

## API Extraction Framework

```python
import requests
import time
from dataclasses import dataclass
from typing import Optional, Iterator

@dataclass
class APIConfig:
    base_url: str
    api_key: str
    rate_limit_requests_per_minute: int = 60
    timeout_seconds: int = 30
    max_retries: int = 3

class APIExtractor:
    def __init__(self, config: APIConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "DataPipeline/1.0"
        })
        self._request_times = []

    def _rate_limit(self):
        """Enforce rate limiting with sliding window."""
        now = time.time()
        window_start = now - 60
        self._request_times = [t for t in self._request_times if t > window_start]

        if len(self._request_times) >= self.config.rate_limit_requests_per_minute:
            sleep_time = 60 - (now - self._request_times[0]) + 0.1
            time.sleep(sleep_time)

        self._request_times.append(now)

    def get(self, endpoint: str, params: dict = None) -> dict:
        """GET with rate limiting and retry."""
        self._rate_limit()
        url = f"{self.config.base_url}/{endpoint.lstrip('/')}"

        for attempt in range(self.config.max_retries):
            try:
                response = self.session.get(url, params=params,
                                            timeout=self.config.timeout_seconds)

                if response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    time.sleep(retry_after)
                    continue

                if response.status_code == 503:  # Service unavailable
                    time.sleep(2 ** attempt)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt < self.config.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise

        raise Exception(f"Failed after {self.config.max_retries} attempts")
```

## Pagination Patterns

```python
class PaginatedExtractor(APIExtractor):

    def extract_cursor_based(self, endpoint: str, params: dict = None) -> Iterator[list]:
        """Cursor-based pagination (most APIs use this now)."""
        cursor = None
        while True:
            page_params = {**(params or {})}
            if cursor:
                page_params["cursor"] = cursor

            response = self.get(endpoint, page_params)
            yield response.get("items", response.get("data", []))

            cursor = response.get("next_cursor") or response.get("meta", {}).get("next")
            if not cursor:
                break

    def extract_page_based(self, endpoint: str, params: dict = None) -> Iterator[list]:
        """Page number-based pagination."""
        page = 1
        while True:
            response = self.get(endpoint, {**(params or {}), "page": page, "per_page": 100})
            items = response.get("items", [])
            if not items:
                break
            yield items
            if len(items) < 100:  # Partial page means last page
                break
            page += 1

    def extract_offset_based(self, endpoint: str, params: dict = None) -> Iterator[list]:
        """Offset/limit pagination."""
        offset, limit = 0, 100
        while True:
            response = self.get(endpoint, {**(params or {}), "offset": offset, "limit": limit})
            total = response.get("total", 0)
            items = response.get("items", [])
            yield items
            offset += limit
            if offset >= total or not items:
                break

    def extract_all(self, endpoint: str, params: dict = None) -> list:
        """Extract all pages and flatten into single list."""
        all_items = []
        for page in self.extract_cursor_based(endpoint, params):
            all_items.extend(page)
        return all_items
```

## Incremental Extraction

```python
import sqlite3

class IncrementalExtractor(PaginatedExtractor):
    def __init__(self, config: APIConfig, state_db: str = "api_state.db"):
        super().__init__(config)
        self.state_db = sqlite3.connect(state_db)
        self.state_db.execute("""
            CREATE TABLE IF NOT EXISTS extraction_state (
                endpoint TEXT PRIMARY KEY,
                last_extracted_at TIMESTAMP,
                last_cursor TEXT,
                total_extracted INTEGER DEFAULT 0
            )
        """)
        self.state_db.commit()

    def get_last_extracted_at(self, endpoint: str) -> Optional[str]:
        row = self.state_db.execute(
            "SELECT last_extracted_at FROM extraction_state WHERE endpoint = ?",
            (endpoint,)
        ).fetchone()
        return row[0] if row else None

    def save_extraction_state(self, endpoint: str, extracted_at: str,
                               cursor: str = None, count: int = 0):
        self.state_db.execute("""
            INSERT INTO extraction_state (endpoint, last_extracted_at, last_cursor, total_extracted)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (endpoint) DO UPDATE SET
                last_extracted_at = excluded.last_extracted_at,
                last_cursor = excluded.last_cursor,
                total_extracted = total_extracted + excluded.total_extracted
        """, (endpoint, extracted_at, cursor, count))
        self.state_db.commit()

    def extract_incremental(self, endpoint: str, date_field: str = "updated_at") -> list:
        """Only extract records newer than last extraction."""
        last_at = self.get_last_extracted_at(endpoint)
        extraction_start = datetime.now().isoformat()

        params = {}
        if last_at:
            params[f"{date_field}[gte]"] = last_at

        all_items = self.extract_all(endpoint, params)
        self.save_extraction_state(endpoint, extraction_start, count=len(all_items))

        return all_items
```

## Webhook Ingestion

```python
from fastapi import FastAPI, Request, HTTPException
import hmac, hashlib

app = FastAPI()

WEBHOOK_SECRETS = {
    "github": "github_webhook_secret",
    "stripe": "stripe_webhook_secret",
    "hubspot": "hubspot_webhook_secret",
}

def verify_signature(payload: bytes, signature: str, secret: str,
                      algorithm: str = "sha256") -> bool:
    """Verify webhook HMAC signature."""
    expected = hmac.new(secret.encode(), payload, algorithm).hexdigest()
    header_sig = signature.replace(f"{algorithm}=", "")
    return hmac.compare_digest(expected, header_sig)

@app.post("/webhooks/{source}")
async def receive_webhook(source: str, request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Signature-SHA256", "")
    secret = WEBHOOK_SECRETS.get(source)

    if not secret or not verify_signature(payload, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = json.loads(payload)

    # Idempotency check — webhooks may be delivered multiple times
    event_id = event.get("id") or event.get("event_id")
    if event_id and is_already_processed(event_id):
        return {"status": "already_processed"}

    # Async processing — acknowledge immediately, process in background
    background_tasks.add_task(process_webhook_event, source, event)
    mark_as_processing(event_id)

    return {"status": "accepted"}
```

## Schema Evolution Handling

```python
def safe_extract_fields(record: dict, expected_schema: dict) -> dict:
    """Extract fields defensively — handle missing or renamed fields."""
    extracted = {}
    for field, config in expected_schema.items():
        # Try primary field name
        value = record.get(field)
        if value is None:
            # Try alternative field names (API renaming)
            for alias in config.get("aliases", []):
                value = record.get(alias)
                if value is not None:
                    break
        # Apply default
        if value is None:
            value = config.get("default")
        # Type coercion
        if value is not None and "type" in config:
            try:
                value = config["type"](value)
            except (ValueError, TypeError):
                value = config.get("default")
        extracted[field] = value
    return extracted

# Usage:
SCHEMA = {
    "id": {"type": str, "aliases": ["_id", "external_id"]},
    "email": {"type": str, "default": None},
    "amount": {"type": float, "default": 0.0},
    "created_at": {"type": pd.Timestamp, "aliases": ["createdAt", "created"]}
}
```

## Monitoring and Alerting

```python
API_HEALTH_CHECKS = {
    "rate_limit_headroom": "Remaining API calls / limit > 20%",
    "extraction_lag_hours": "Hours since last successful extraction < SLA",
    "error_rate": "API errors / total requests < 5%",
    "data_volume_vs_expected": "Extracted records within 20% of historical average",
}

def check_api_health(extractor: APIExtractor, endpoint: str) -> dict:
    # Check rate limit headers from last response
    remaining = int(extractor.session.last_response.headers.get("X-RateLimit-Remaining", 999))
    limit = int(extractor.session.last_response.headers.get("X-RateLimit-Limit", 1000))

    return {
        "rate_limit_pct_used": (limit - remaining) / limit * 100,
        "status": "healthy" if remaining > limit * 0.2 else "rate_limited",
        "last_extraction_lag": get_extraction_lag(endpoint)
    }
```
