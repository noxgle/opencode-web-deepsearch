import { tool, type Plugin } from "@opencode-ai/plugin"
import { fileURLToPath } from "url"
import path from "path"

// Get the directory where the plugin is installed
// __filename points to dist/index.js, so we need to go up one level to the package root
const __filename = fileURLToPath(import.meta.url)
const pluginDir = path.resolve(path.dirname(__filename), "..")
const scriptPath = path.join(pluginDir, "scripts", "WebSearchAgent.py")

const WebDeepSearchTool = tool({
  description:
    "Search the web using DuckDuckGo and extract page content. Tune refinement rounds, per-page content length, per-request timeout, and total search time within their documented limits. Returns raw JSON with source metadata and content; when the total response exceeds its 10,000-byte budget, mode is 'compact', truncated is true, and omitted content is identified by content_length. In compact mode, use an available page-fetching tool to retrieve important source URLs separately. Analyze the returned data and synthesize a final answer.",
  args: {
    query: tool.schema.string().describe("Search query"),
    max_sources: tool.schema
      .number()
      .int()
      .min(1)
      .max(50)
      .optional()
      .default(3)
      .describe("Maximum sources to extract (default: 3)"),
    deep_search: tool.schema
      .boolean()
      .optional()
      .default(true)
      .describe("Enable iterative search refinement (default: true)"),
    max_iterations: tool.schema
      .number()
      .int()
      .min(1)
      .max(10)
      .optional()
      .default(5)
      .describe("Maximum refinement rounds, 1–10 (default: 5)"),
    max_content_length: tool.schema
      .number()
      .int()
      .min(500)
      .max(8000)
      .optional()
      .default(8000)
      .describe("Maximum extracted characters per page, 500–8000 (default: 8000)"),
    timeout: tool.schema
      .number()
      .int()
      .min(5)
      .max(60)
      .optional()
      .default(30)
      .describe("Per-request timeout in seconds, 5–60 (default: 30)"),
    max_total_time: tool.schema
      .number()
      .int()
      .min(10)
      .max(120)
      .optional()
      .default(60)
      .describe("Maximum total search time in seconds, 10–120 (default: 60)"),
  },
  async execute(args) {
    const query = (args.query ?? "").toString().trim()
    if (!query) {
      throw new Error("query is required")
    }
    const safeQuery = query.length > 500 ? query.slice(0, 500) : query
    const maxSources = args.max_sources ?? 3
    const deepSearch = args.deep_search !== false
    const maxIterations = args.max_iterations ?? 5
    const maxContentLength = args.max_content_length ?? 8000
    const timeout = args.timeout ?? 30
    const maxTotalTime = args.max_total_time ?? 60

    const result = await Bun.$`python3 ${scriptPath} --query ${safeQuery} --max-sources ${maxSources} --deep-search ${deepSearch} --max-iterations ${maxIterations} --max-content-length ${maxContentLength} --timeout ${timeout} --max-total-time ${maxTotalTime}`.text()
    return result.trim()
  },
})

export default async function webDeepSearchPlugin(): Promise<ReturnType<typeof tool>> {
  return WebDeepSearchTool
}

// Export as Plugin for OpenCode
export const WebDeepSearchPlugin: Plugin = async () => {
  return {
    tool: {
      "web-deepsearch": WebDeepSearchTool,
    },
  }
}