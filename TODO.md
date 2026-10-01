# Project: Safe web_deepsearch output sizing

## Goal

Ensure `web-deepsearch` never returns an oversized or malformed JSON response. Preserve useful source metadata and make full content recoverable when the response must be compacted.

## Context

`scripts/WebSearchAgent.py` truncates each extracted page to 8,000 characters, but the combined response can still become much larger because iterative search may collect up to roughly `max_sources * 2` sources. The TypeScript tool currently returns the raw JSON string without a total-output budget. The OpenCode host may therefore truncate the tool result after serialization, potentially cutting JSON in the middle.

There is no repository-root `TODO.md` currently. This plan addresses the output-truncation problem described during web-deepsearch usage.

## Scope

### In Scope

- Add a deterministic total response-size budget before JSON serialization.
- Add an explicit compact response mode with truncation metadata.
- Preserve URLs, snippets, titles, domains, and original content lengths for all sources.
- Preserve full content for as many high-priority sources as fit within the budget.
- Update tool guidance so an agent can retrieve omitted content using an available page-fetching tool.
- Add tests for valid JSON, size boundaries, compact mode, and backward-compatible full mode.

### Non-Goals

- Changing DuckDuckGo search ranking or crawling behavior.
- Guaranteeing that every remote page can be fetched successfully.
- Removing the existing per-source 8,000-character extraction cap.
- Modifying OpenCode host truncation behavior.
- Implementing a stateful pagination service in this iteration.

## Assumptions

- A response budget of approximately 10,000 characters provides headroom below the observed host-side truncation threshold.
- URLs returned in compact mode are sufficient for a follow-up page-fetching tool to recover omitted content.
- Existing consumers accept additive response fields such as `mode`, `truncated`, and content-length metadata.
- Full mode should retain the current response shape and source fields.

## Open Questions

- Confirm the exact truncation threshold for every supported OpenCode runtime; keep the internal budget configurable rather than depending on one host version.
- Confirm which follow-up fetch tool name should be referenced in the tool description for all supported environments.
- Decide whether the response budget should be exposed as a user argument or remain an internal safety limit. The recommended first version keeps it internal with a future configuration option.

## Tech Stack

- **TypeScript/Bun:** OpenCode tool wrapper in `src/index.ts`.
- **Python 3.8+:** Search, extraction, response construction, and JSON serialization in `scripts/WebSearchAgent.py`.
- **Vitest/TypeScript tests:** Existing plugin and script integration coverage in `e2e/test_plugin.ts`.

## Constraints

- The tool must continue to run when installed from the npm package, where `dist/index.js` resolves the bundled Python script relative to the package root.
- The Python process must emit valid JSON on stdout.
- The output must degrade explicitly rather than silently losing content.
- No implementation should rely on the host preserving oversized tool output.

## Architecture

The Python response builder remains the single source of truth for output sizing. Search and extraction continue to collect source content as they do now, including the existing per-source cap. Immediately before returning the response, the builder will construct the normal full payload and measure its serialized size using the same JSON serialization settings used by `main()`.

If the full payload fits the configured safety budget, it is returned in the existing format with an additive mode marker. If it does not fit, the builder returns a compact payload: every source retains title, URL, snippet, domain, and original content length; full content is retained only for sources selected by a deterministic priority order while the serialized response remains under budget. The compact payload includes explicit truncation status, counts, total content size, and a recovery hint.

The TypeScript wrapper will update the tool description to explain the compact response contract and instruct the calling agent to fetch selected URLs separately when `mode` is `compact` or `truncated` is true. The wrapper will not attempt to parse or reserialize the Python JSON.

## Architecture Decisions

### ADR-001: Enforce a total serialized-response budget in the Python response builder

**Decision:** Add a configurable internal budget, targeting approximately 10,000 serialized characters, and enforce it in `_build_raw_response()` before stdout serialization.

**Alternatives:**

- Only advise callers to use smaller `max_sources` values.
- Expose `max_content_length` and rely on callers to configure it correctly.
- Return all content and rely on OpenCode externalization/truncation behavior.
- Implement stateful pagination for all source content.

**Rationale:** Caller-specific limits are unreliable, and host-side truncation can produce invalid JSON. A local budget gives the plugin deterministic behavior while preserving the current stateless API.

**Trade-offs:** Large searches may return snippets instead of full content in one call. A lower budget also reduces the amount of content available to the model immediately.

**Consequences:** The tool must expose explicit compact-mode metadata and tests must verify that output remains parseable and within the budget.

### ADR-002: Use adaptive compact mode rather than always returning snippets

**Decision:** Keep the current full response for payloads that fit; switch to compact mode only when necessary.

**Alternatives:**

- Always return metadata and snippets only.
- Always return only one source with full content.
- Require callers to paginate manually.

**Rationale:** This preserves backward compatibility and current usefulness for small searches while preventing oversized responses for broad searches.

**Trade-offs:** Consumers must handle two explicit modes. The compact mode may require a second fetch for important sources.

**Consequences:** `mode`, `truncated`, source content-length fields, and a recovery hint become part of the documented response contract.

### ADR-003: Prefer deterministic source priority for retained full content

**Decision:** Rank sources deterministically using available relevance signals (for example snippet quality/order, then content availability/length) and retain full content while the budget allows.

**Alternatives:**

- Retain the first sources only.
- Retain the longest pages only.
- Randomly sample sources.

**Rationale:** Determinism makes results reproducible and avoids silently favoring arbitrary fetch completion order.

**Trade-offs:** Search relevance is inferred from existing metadata rather than a separate ranking model.

**Consequences:** Tests should assert deterministic ordering and at least one retained full-content source when content is available.

## Phases

### Phase 1: Define and implement bounded response construction

**Objective:** Make the Python script produce a valid response that stays within the configured serialized-size budget.

**Prerequisites:** ADR-001 through ADR-003 approved.

**Expected outcome:** Full responses remain compatible when small; oversized responses become explicit compact responses instead of being host-truncated.

**Estimated effort:** 0.5–1 day.

**Confidence:** High

- [x] **Task:** Add response-budget configuration and serialization-aware sizing

  - **Description:** Add a documented safety budget to `DEFAULT_CONFIG`. Refactor response construction so it measures the actual JSON representation, not only an approximate character count. Avoid recursive or inconsistent serialization settings between measurement and final stdout output.

  - **Files:** `scripts/WebSearchAgent.py`

  - **Dependencies:** None.

  - **Acceptance Criteria:**
    - The budget is applied before the final `print(json.dumps(...))` call.
    - The size calculation uses UTF-8/JSON behavior consistent with final output.
    - Existing full-mode source fields remain present for responses that fit.

  - **Verification:**
    - Run the script with a small query and parse stdout using `python3 -m json.tool`.
    - Add a deterministic unit-level test or helper assertion that serialized output is at or below the configured budget for synthetic large sources.

- [x] **Task:** Implement explicit compact response mode

  - **Description:** When the full payload exceeds the budget, retain title, URL, snippet, domain, and original content length for every source. Retain full content only for prioritized sources that fit. Add `mode`, `truncated`, retained/omitted source counts, total content length, and a recovery hint. Ensure compact mode itself is budget-checked so metadata cannot overflow the response.

  - **Files:** `scripts/WebSearchAgent.py`

  - **Dependencies:** Response-budget configuration task.

  - **Acceptance Criteria:**
    - Compact output is valid JSON and never contains a raw host-truncation marker.
    - `truncated` is true whenever any source content is omitted.
    - Every compact source retains a usable URL and metadata sufficient for follow-up retrieval.
    - The selection of full-content sources is deterministic.

  - **Verification:**
    - Test synthetic payloads with 1, 3, and 10 large sources.
    - Assert `json.loads()` succeeds and serialized output remains within the configured budget.

### Phase 2: Update tool contract and automated coverage

**Objective:** Make callers aware of compact mode and protect the behavior with regression tests.

**Prerequisites:** Phase 1.

**Expected outcome:** OpenCode receives actionable metadata instead of silently truncated JSON, and future changes cannot remove the safety guarantee unnoticed.

**Estimated effort:** 0.5–1 day.

**Confidence:** High

- [x] **Task:** Document compact-mode handling in the OpenCode tool description

  - **Description:** Update the tool description to explain `mode: "compact"`, `truncated: true`, and the need to fetch selected URLs separately with the environment’s page-fetching tool. Keep the existing raw-JSON contract description accurate.

  - **Files:** `src/index.ts`

  - **Dependencies:** Compact response schema finalized in Phase 1.

  - **Acceptance Criteria:**
    - The description tells the model how to recognize omitted content.
    - It does not claim that every source contains full content.
    - No change is made to script path resolution or argument behavior.

  - **Verification:**
    - Inspect the registered tool metadata and confirm the compact-mode guidance is present.
    - Run the existing TypeScript build.

- [x] **Task:** Add regression tests for full, compact, and boundary responses

  - **Description:** Extend `e2e/test_plugin.ts` and, if needed, add focused test helpers that validate normal small responses, oversized synthetic responses, deep-search responses, empty-content responses, and exact budget boundaries. Verify both JSON validity and required compact metadata.

  - **Files:** `e2e/test_plugin.ts`, `scripts/WebSearchAgent.py` (only if test seams are needed)

  - **Dependencies:** Phase 1 response schema.

  - **Acceptance Criteria:**
    - Small responses remain in full mode and retain `content`.
    - Oversized responses use compact mode and remain parseable.
    - `deep_search: false` is covered.
    - Large `max_sources` values are covered without producing oversized stdout.
    - Tests do not depend on one live website’s exact content or ordering.

  - **Verification:**
    - `npm test`
    - `npm run build`
    - Direct script output piped through `python3 -m json.tool` for representative queries.

### Phase 3: Documentation and release validation

**Objective:** Document the behavior for users and validate the package artifact before release.

**Prerequisites:** Phase 2 passes.

**Expected outcome:** Users understand why some source content is omitted and how to recover it; the published package contains the fix.

**Estimated effort:** 0.25–0.5 day.

**Confidence:** Medium

- [x] **Task:** Document output limits and compact-mode recovery

  - **Description:** Add a README section describing per-source extraction limits, the total response budget, compact-mode fields, and the recommended follow-up retrieval workflow. Clarify that smaller `max_sources` can reduce compaction but is only an optional workaround.

  - **Files:** `README.md`

  - **Dependencies:** Final response schema from Phase 1.

  - **Acceptance Criteria:**
    - Documentation distinguishes source-content truncation from host-level tool-output truncation.
    - Compact-mode fields and recovery behavior are shown with a valid example.

  - **Verification:**
    - Review the README example against the actual serialized response schema.

- [ ] **Task:** Validate package contents and release readiness

  - **Description:** Build and test the package, inspect the generated artifact, and confirm that the Python script and compiled TypeScript contain the response-budget implementation. Do not publish until the output-size and JSON-validity checks pass.

  - **Files:** `dist/index.js`, `dist/index.d.ts`, package artifact generated by the release process (generated files only)

  - **Dependencies:** All prior tasks.

  - **Acceptance Criteria:**
    - Build succeeds.
    - Tests pass.
    - Representative broad-search output remains valid JSON and within the configured budget.
    - The npm package includes the updated runtime files and README.

  - **Verification:**
    - `npm run build`
    - `npm test`
    - Inspect the package tarball contents before publishing.

## Rollout & Rollback

Release as a patch version because the change is intended to be backward-compatible in full mode and additive in compact mode. If downstream consumers reject the new fields or compact behavior, roll back to the previous package version while preserving the regression tests and revisiting the response contract.

## Observability

Expose compact-mode indicators in every compact response: `mode`, `truncated`, retained-content count, omitted-content count, total content length, and existing fetch statistics. These fields allow callers to distinguish failed fetches from deliberate output compaction.

## Security Considerations

- Continue using existing URL validation and redirect controls.
- Do not include fetched content in recovery hints; expose only already-returned URLs.
- Ensure size accounting occurs after JSON escaping so special characters cannot bypass the budget.

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Host truncates before the plugin budget is reached | High | Medium | Keep the internal budget below the observed host threshold and verify actual serialized byte size. |
| Compact mode silently loses important details | Medium | Medium | Add explicit flags, content lengths, counts, URLs, and recovery guidance. |
| Full/compact schema differences break consumers | Medium | Low | Keep existing fields, make new fields additive, document both modes, and test both. |
| JSON escaping makes estimates inaccurate | High | Low | Measure the exact serialized representation with the production serializer. |
| Live-site tests are flaky | Medium | Medium | Use synthetic payload tests for size boundaries and keep live queries limited to smoke tests. |
| Follow-up page fetching is unavailable in some hosts | Medium | Medium | Preserve snippets and URLs; document the dependency as an environment assumption. |

## Project Acceptance Criteria

- [x] The tool never intentionally emits a response larger than its configured safety budget.
- [x] Oversized searches return valid JSON with explicit compact-mode metadata.
- [x] Full mode remains compatible for responses that fit the budget.
- [x] Every returned source in compact mode retains a URL, title, snippet, domain, and original content length. (If source metadata itself exceeds budget, lower-priority sources may be omitted.)
- [x] Tests cover normal, oversized, boundary, empty-content, and deep-search cases.
- [x] README documents the distinction between per-source extraction limits and total response limits.

## Estimated Timeline

Approximately 1.25–2.5 engineering days: one day for bounded response construction and tests, up to one day for documentation and release validation. The main uncertainty is confirming the effective host threshold across OpenCode versions; the internal budget should remain configurable to accommodate that variation.
