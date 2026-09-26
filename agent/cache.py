import json
import re
import time
from agent.mcp import get_notion_tools

_cached_context: str = ""
_last_fetched: float = 0.0
_TTL = 600  # Cache for 10 minutes


def _extract_id(entry: dict) -> str | None:
    """Extract clean 32-character Notion ID from entry ID or URL."""
    val = entry.get("id") or entry.get("url") or ""
    match = re.search(r"[0-9a-f]{32}", str(val).replace("-", ""), re.I)
    return match.group(0) if match else None


def _parse_results(res) -> list[dict]:
    """Extract page results from tool output (JSON string, list of blocks, or dict)."""
    if isinstance(res, list) and res and isinstance(res[0], dict) and "text" in res[0]:
        res = res[0]["text"]
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            return []
    return res.get("results", []) if isinstance(res, dict) else (res if isinstance(res, list) else [])


async def get_workspace_context(force_refresh: bool = False) -> str:
    """Fetch and pre-cache Notion workspace root pages to avoid search round-trips."""
    global _cached_context, _last_fetched

    if not force_refresh and _cached_context and (time.time() - _last_fetched < _TTL):
        return _cached_context

    try:
        tools = {t.name: t for t in await get_notion_tools()}
        seen = set()
        lines = ["### Known Notion Workspace Locations (Pre-Cached):"]

        for name in ("notion-list-private-pages", "notion-list-shared-pages"):
            if tool := tools.get(name):
                res = await tool.ainvoke({"limit": 50})
                for item in _parse_results(res):
                    if not isinstance(item, dict):
                        continue
                    page_id = _extract_id(item)
                    if page_id and page_id not in seen:
                        seen.add(page_id)
                        title = item.get("title") or "Untitled"
                        tag = "Database" if "database" in str(item.get("type", "")).lower() else "Page"
                        type_str = "database_id" if tag == "Database" else "page_id"
                        lines.append(f'- {tag}: "{title}" (Parent ID: `{page_id}`, type: `{type_str}`)')

        if len(lines) > 1:
            lines.append(
                "\n*When filing notes into any of the above locations, use the corresponding Parent ID directly "
                "in `notion-create-pages` or `notion-update-page` without executing a preliminary search.*"
            )
            _cached_context = "\n".join(lines)
            _last_fetched = time.time()

    except Exception:
        pass

    return _cached_context
