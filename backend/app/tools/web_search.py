from typing import Any, Dict, List

from .base import Tool, ToolContext


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web for information. Returns top results (mock in demo mode)."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return.",
                "default": 3,
            },
        },
        "required": ["query"],
    }

    def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        query = params.get("query", "").strip()
        if not query:
            raise ValueError("Missing query for web_search.")
        top_k = int(params.get("top_k", 3))
        results = []
        for idx in range(top_k):
            results.append(
                {
                    "title": f"Result {idx + 1} for '{query}'",
                    "url": f"https://example.com/search/{idx + 1}",
                    "snippet": f"Relevant information about {query} from source {idx + 1}.",
                }
            )
        return {"query": query, "results": results, "source": "mock"}
