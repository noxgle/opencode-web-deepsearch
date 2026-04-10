/**
 * E2E test for opencode-web-deepsearch plugin.
 * Tests that the plugin installs correctly and the tool works.
 */

import { spawn, type ChildProcess } from "node:child_process"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { test, expect, beforeAll, afterAll } from "vitest"

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Test constants
const TEST_PORT = 9876
const TEST_QUERY = " TypeScript 5.x features"
const PLUGIN_NAME = "opencode-web-deepsearch"

interface ServerProcess {
  process: ChildProcess
  port: number
}

async function waitForHealth({
  port,
  maxAttempts = 30,
}: {
  port: number
  maxAttempts?: number
}): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/api/health`)
      if (response.ok) {
        return true
      }
    } catch {
      // ignore
    }
    await new Promise((resolve) => {
      setTimeout(resolve, 1000)
    })
  }
  return false
}

function killServer(server: ServerProcess | null) {
  if (server?.process) {
    server.process.kill()
  }
}

async function chooseLockPort(key: string): Promise<number> {
  // Simple port selection - in real tests would use a locking mechanism
  return TEST_PORT + Math.floor(Math.random() * 1000)
}

test(
  "plugin installs and loads without errors",
  async () => {
    const projectDir = path.resolve(__dirname, "tmp", "plugin-e2e")

    // Clean up any existing test directory
    try {
      fs.rmSync(projectDir, { recursive: true, force: true })
    } catch {
      // ignore
    }

    fs.mkdirSync(projectDir, { recursive: true })

    const port = await chooseLockPort({
      key: "opencode-web-deepsearch-e2e",
    })
    const stderrLines: string[] = []

    // Get opencode command
    const opencodeCommand = process.env.OPENCODE_COMMAND || "opencode"

    const serverProcess: ChildProcess = spawn(opencodeCommand, ["serve", "--port", port.toString(), "--print-logs"], {
      stdio: ["pipe", "pipe", "pipe"],
      cwd: projectDir,
      env: {
        ...process.env,
        OPENCODE_CONFIG_CONTENT: JSON.stringify({
          $schema: "https://opencode.ai/config.json",
          lsp: false,
          formatter: false,
          plugin: [PLUGIN_NAME],
        }),
        OPENCODE_TEST_HOME: projectDir,
      },
    })

    serverProcess.stderr?.on("data", (data) => {
      stderrLines.push(...data.toString().split("\n").filter(Boolean))
    })

    try {
      const healthy = await waitForHealth({ port })
      expect(healthy).toBe(true)

      // Check no plugin-related errors in stderr
      const pluginErrorPatterns = [
        /plugin.*error/i,
        /failed to load plugin/i,
        /cannot find module/i,
        /ERR_MODULE_NOT_FOUND/i,
      ]

      const hasPluginError = stderrLines.some((line) =>
        pluginErrorPatterns.some((pattern) => pattern.test(line))
      )

      expect(hasPluginError).toBe(false)
    } finally {
      killServer({ process: serverProcess, port })
      // Clean up
      try {
        fs.rmSync(projectDir, { recursive: true, force: true })
      } catch {
        // ignore
      }
    }
  },
  120000
)

test(
  "Python script returns valid JSON output",
  async () => {
    const scriptPath = path.join(__dirname, "scripts", "WebSearchAgent.py")

    // Check script exists
    expect(fs.existsSync(scriptPath)).toBe(true)

    // Run the Python script
    const result = await new Promise<string>((resolve, reject) => {
      const proc = spawn("python3", [
        scriptPath,
        "--query",
        "TypeScript 5.x features",
        "--max-sources",
        "1",
        "--deep-search",
        "false",
      ])

      let stdout = ""
      let stderr = ""

      proc.stdout?.on("data", (data) => {
        stdout += data.toString()
      })

      proc.stderr?.on("data", (data) => {
        stderr += data.toString()
      })

      proc.on("close", (code) => {
        if (code === 0) {
          resolve(stdout)
        } else {
          reject(new Error(`Script failed with code ${code}: ${stderr}`))
        }
      })

      proc.on("error", (err) => {
        reject(err)
      })
    })

    // Parse JSON output
    const json = JSON.parse(result)

    // Validate output structure
    expect(json).toHaveProperty("query")
    expect(json).toHaveProperty("sources")
    expect(json).toHaveProperty("iterations_used")
    expect(json).toHaveProperty("source_count")
    expect(Array.isArray(json.sources)).toBe(true)

    // Check source structure if present
    if (json.sources.length > 0) {
      const source = json.sources[0]
      expect(source).toHaveProperty("title")
      expect(source).toHaveProperty("url")
      expect(source).toHaveProperty("snippet")
      expect(source).toHaveProperty("content")
      expect(source).toHaveProperty("domain")
    }
  },
  60000
)