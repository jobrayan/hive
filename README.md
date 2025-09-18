# 🐝 Hive — Distributed AI Worker Queue

<p align="center">
  <img src="public/hive.gif" alt="Hive Banner" width="256" style="border-radius: 50%;"/>
</p>


## Overview
Hive is a distributed system that manages **task execution across multiple worker containers**.  
Think of it as a *swarm of AI bees* (workers) organized by a **dispatcher** (queen bee),  
each handling tickets one at a time. Extra tasks are queued and executed as soon as workers free up.

### Key Features
- **Queue-based Scheduling**: Enqueue tasks, workers pick them up when available.
- **Scalable Workers**: Run up to 10 workers on a local gaming PC (or more in the cloud).
- **Ticket Runner**: Tasks can be auto-generated, CRON-triggered, or created manually via API/UI.
- **Analytics Integration**: Read logs, metrics, or external feeds → generate tickets automatically.
- **Execution in Containers**: Workers run inside Docker containers for isolation & reproducibility.
- **Callback System**: Tasks report progress + final status to your backend.
- **Authentication**: Internal API token (for CRON/agents) + planned OAuth/JWT integration for UI.
- **Future Scaling**: Deploy to [Fly.io](https://fly.io) for horizontal scaling across regions.

---

## 🏗 Architecture
- **Dispatcher**: Manages the task queue, assigns jobs to free workers.
- **Workers**: Docker containers running AI agents or automation scripts.
- **Queue**: FIFO job buffer (in-memory, Redis planned).
- **Callback**: Workers notify Dispatcher → Dispatcher notifies the Hive backend/UI.
- **Roles**: Workers may specialize (builder, tester, analyzer) to form layered workflows.

See [ARCHITECTURE.md](./docs/ARCHITECTURE.md) for full details.

---

## 📦 Monorepo Layout

```
hive/
├─ apps/
│  └─ dispatcher/      # NestJS dispatcher (queue + claim endpoints)
├─ packages/
│  └─ sdk/             # Published npm package `hive`
├─ .github/workflows/  # Release automation (semantic-release)
├─ CHANGELOG.md
├─ package.json        # pnpm workspace root
└─ pnpm-workspace.yaml
```

### SDK (`packages/sdk`)
- Exports `HiveClient`, `createNextClaimRoute`, `createNextCallbackRoute`, and `envClient()`.
- Installable via `pnpm add hive` inside any Next.js (App Router) project.
- Built with `tsup`, published automatically via semantic-release.

### Dispatcher (`apps/dispatcher`)
- NestJS service that exposes `/health`, `/enqueue`, `/claim`, `/callback`.
- Designed for container deployments (Fly.io, Render, bare Docker).
- Future roadmap: Redis-backed queue, multi-tenant auth, Web dashboard.

## 🚀 Quick Start (SDK)
Install inside your Next.js project:

```bash
pnpm add hive
```

Create route handlers:

```ts
// app/api/hive/claim/route.ts
import { envClient, createNextClaimRoute } from "hive";

const client = envClient();
export const POST = createNextClaimRoute(client);
```

```ts
// app/api/hive/callback/route.ts
import { envClient, createNextCallbackRoute } from "hive";

const client = envClient();
export const POST = createNextCallbackRoute(client);
```

Enqueue from a server action:

```ts
import { envClient, EnqueueBody } from "hive";

export async function enqueueJob(body: EnqueueBody) {
  const client = envClient();
  return client.enqueue(body);
}
```

Environment variables:

```
HIVE_BASE_URL=https://hive.yourdomain.com
HIVE_INTERNAL_TOKEN=... # optional, for enqueue
HIVE_CALLBACK_SECRET=... # optional, for callback forwarding
```

For local development you can run the dispatcher (see `apps/dispatcher`) or
point to an existing cluster.

---

## 🔒 Authentication
- **Dispatcher**: requires `INTERNAL_API_TOKEN` for all `/enqueue` requests.
- **Workers**: trust Dispatcher via shared `CALLBACK_SECRET`.
- **Future**: OAuth/JWT for user-facing UI.

See [AUTH.md](./docs/AUTH.md) for a deeper dive.

---

## 🌐 Roadmap
- [ ] Redis-backed persistent queue  
- [ ] Worker specialization (roles: builder, tester, analyzer)  
- [ ] Auto-ticket generation from analytics/logs  
- [ ] Fly.io integration for elastic scaling  
- [ ] Web UI for monitoring + control  

---

## 📜 License
MIT © Jobrayan, Inc.
