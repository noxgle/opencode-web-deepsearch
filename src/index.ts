import { tool, type Plugin } from "@opencode-ai/plugin"
import os from "os"
import path from "path"

const WebDeepSearchTool = tool({
  description:
    "Search the web using DuckDuckGo and extract full page content from sources. Returns raw JSON data with sources array containing title, url, snippet, content, and domain. Use this tool to gather web research data. The output is raw data - you must analyze it and synthesize a final answer.",
  args: {
    query: tool.schema.string().describe("Search query"),
    max_sources: tool.schema
      .number()
      .optional()
      .default(3)
      .describe("Maximum sources to extract (default: 3)"),
    deep_search: tool.schema
      .boolean()
      .optional()
      .default(true)
      .describe("Enable iterative search refinement (default: true)"),
  },
  async execute(args) {
    // Get the directory where the plugin is installed
    const pluginDir = path.dirname(require.main?.filename || __filename)
    const scriptPath = path.join(pluginDir, "scripts", "WebSearchAgent.py")

    const maxSources = args.max_sources ?? 3
    const deepSearch = args.deep_search !== false

    const result = await Bun.$`python3 ${scriptPath} --query ${args.query} --max-sources ${maxSources} --deep-search ${deepSearch}`.text()
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
      web_deepsearch: WebDeepSearchTool,
    },
  }
}