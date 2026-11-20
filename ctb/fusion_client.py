"""Pulls Oracle Fusion Cloud SCM-shaped resources through mock_fusion_api by
following its offset/limit, `hasMore` pagination.
"""
import json
import urllib.request


def fetch_all(base_url, resource, page_size=100):
    rows = []
    offset = 0
    while True:
        url = f"{base_url}/{resource}?offset={offset}&limit={page_size}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode())
        rows.extend(payload["items"])
        if not payload["hasMore"]:
            break
        offset += page_size
    return rows
