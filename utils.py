def parse_json_safe(value: str | dict) -> dict:
    """Safely parse a JSON string or return a dict as-is."""
    if isinstance(value, dict):
        return value
    try:
        import json

        return json.loads(value or "{}")
    except Exception:
        return {}
