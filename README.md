# opencode-web-deepsearch

DuckDuckGo web search tool for OpenCode with deep search capabilities.

## Features

- **DuckDuckGo Search**: Uses DuckDuckGo for web searching (no API key required)
- **Deep Search**: Iterative search refinement that finds more relevant results
- **Content Extraction**: Extracts clean text content from web pages
- **Source Deduplication**: Automatically deduplicates sources by domain
- **Raw JSON Output**: Returns structured data for AI evaluation

## Installation

### 1. Install Python dependencies

```bash
pip install ddgs beautifulsoup4 requests aiohttp
```

Or install all dependencies at once:

```bash
pip install ddgs beautifulsoup4 requests aiohttp lxml
```

### 2. Add plugin to OpenCode

Add to your `opencode.json`:

```json
{
  "plugin": ["opencode-web-deepsearch"]
}
```

Or use npm package (recommended):

```json
{
  "plugin": ["opencode-web-deepsearch"]
}
```

OpenCode will automatically install the plugin from npm.

## Usage

The tool is available as `web-deepsearch` in OpenCode.

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `query` | string | required | Search query |
| `max_sources` | number | 3 | Maximum sources to extract |
| `deep_search` | boolean | true | Enable iterative search refinement |

### Example

```json
{
  "query": "TypeScript 5.x new features",
  "max_sources": 5,
  "deep_search": true
}
```

## Output Format

```json
{
  "query": "TypeScript 5.x new features",
  "sources": [
    {
      "title": "TypeScript 5.0 - Major Changes",
      "url": "https://example.com/typescript-5",
      "snippet": "TypeScript 5.0 brings...",
      "content": "Full extracted content...",
      "domain": "example.com"
    }
  ],
  "iterations_used": 3,
  "source_count": 5,
  "domain_count": 3
}
```

## Requirements

- Python 3.8+
- `ddgs` or `duckduckgo_search`
- `beautifulsoup4`
- `requests`
- `aiohttp` (optional, for async fetching)

## Comparison with OpenCode's Built-in Search (Exa)

| Aspect | web-deepsearch | Standard OpenCode (Exa) |
|--------|---------------|-------------------------|
| **API Key** | Not required | Optional (for higher limits) |
| **Cost** | Free | Limited free tier |
| **Code search** | Not included | Via `get_code_context_exa` |
| **Deep search** | Iterative refinement | Not available |
| **Content extraction** | Full page extraction | Via `web_fetch_exa` |
| **Latency** | Slower (DuckDuckGo) | Faster (Exa API) |
| **Reliability** | Depends on DuckDuckGo | More stable (Exa) |

### When web-deepsearch is better:
- You don't have an Exa API key
- You need iterative deep search
- You want a free solution without limits

### When Exa is better:
- You need code search (GitHub code search)
- You need faster results
- You have an API key and need higher limits

---

## License

MIT