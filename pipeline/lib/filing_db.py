"""
Local index of fetched filings. Avoids re-downloading the same document
and maps filings to their local staging paths.

Schema per record:
    {
        "source": "sec_edgar",
        "cik": "0000320193",
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "filing_type": "10-K",
        "filing_date": "2025-10-31",
        "accession": "0000320193-25-000123",
        "doc_url": "https://...",
        "local_path": "staging/sec/AAPL_10K_2025.pdf",
        "fetched_at": "2026-04-26T15:30:00",
        "status": "downloaded"
    }
"""

import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "filing_index.json")


class FilingDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._records: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, "r") as f:
                self._records = json.load(f)

    def _save(self):
        with open(self.db_path, "w") as f:
            json.dump(self._records, f, indent=2, ensure_ascii=False)

    def exists(self, source: str, ticker: str, filing_type: str, filing_date: str) -> bool:
        """Check if a filing has already been downloaded."""
        for r in self._records:
            if (r["source"] == source and r["ticker"] == ticker
                    and r["filing_type"] == filing_type and r["filing_date"] == filing_date):
                return True
        return False

    def add(self, record: dict):
        record["fetched_at"] = datetime.now().isoformat()
        self._records.append(record)
        self._save()

    def list_by_ticker(self, ticker: str) -> list[dict]:
        return [r for r in self._records if r["ticker"].upper() == ticker.upper()]

    def list_by_source(self, source: str) -> list[dict]:
        return [r for r in self._records if r["source"] == source]

    def all(self) -> list[dict]:
        return list(self._records)
