# Hive Developer Notes

This repository is now a pnpm workspace with two primary deliverables:

- `packages/sdk` – the published npm module `hive`
- `apps/dispatcher` – the NestJS worker dispatcher service (work-in-progress)

## Workspace Commands

From the repository root (`hive/`):

```bash
pnpm install        # installs workspace deps
pnpm build          # runs build in all packages
pnpm -r lint        # runs lint in all packages (when configs exist)
```

### Building the SDK only

```bash
pnpm --filter hive build
```

## Publishing Workflow

Semantic-release publishes the SDK package automatically whenever commits land on `main` with conventional commit messages.

- Workflow file: `.github/workflows/release.yml`
- Release configuration: `.releaserc.json`
- Tags follow the format `hive-vX.Y.Z`

To trigger a release locally:

```bash
pnpm install
pnpm --filter hive build
# push a commit with "feat:" / "fix:" etc. onto main and let the action run
```

Ensure the repository has `NPM_TOKEN` configured under Settings → Secrets → Actions.

## SDK API Surface

```ts
import { HiveClient, envClient, createNextClaimRoute, createNextCallbackRoute, EnqueueSchema } from "hive";
```

- `HiveClient` – HTTP client targeting a dispatcher instance
- `envClient()` – convenience constructor that reads `HIVE_*` environment variables
- `createNextClaimRoute()` / `createNextCallbackRoute()` – App Router helpers for Next.js
- `EnqueueSchema` – `zod` schema exported for validation in client apps

## Dispatcher (Upcoming)

The NestJS dispatcher will live in `apps/dispatcher`. It will expose
`/health`, `/enqueue`, `/claim`, and `/callback` routes and is meant to be
containerised for Fly.io/Render deployments. Redis integration is planned next.

## Roadmap

- [ ] Flesh out `apps/dispatcher` service and Dockerfile
- [ ] Add Redis-backed queue implementation
- [ ] Provide example Next.js app in `apps/demo-next` consuming the SDK
- [ ] Document worker container expectations and callback payloads
