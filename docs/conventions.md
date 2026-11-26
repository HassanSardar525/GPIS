# Conventions

Use Python 3.11, typed Pydantic models at API boundaries, and repository methods for storage access. Keep scoring and temporal comparisons in pure functions. See [architecture](architecture.md) for the structured and document retrieval paths.

Use snake_case for Python, camelCase for browser JavaScript and kebab-case for district slugs. Escape source-derived text in HTML and validate outbound URLs. Guard asynchronous renders against stale responses after a selection changes.

Every new observation needs a publisher, document title, period, official URL and page, table or cell locator. Check at least one raw value manually. Version formula changes and add a hand-calculated example. Document direction, normalization, weights, missing-data behavior and scope.

Reproduce a failure at the narrowest useful level. Record whether it comes from extraction, retrieval, generation or presentation, fix that layer and retain the regression. Follow the branch and commit rules in [AGENTS.md](../AGENTS.md).
