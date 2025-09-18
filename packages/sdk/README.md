# hive

Hive SDK for Next.js and custom worker orchestrations.

## Installation

```bash
pnpm add hive
```

## Environment variables

Set these in your app (server-side only):

- `HIVE_BASE_URL` – Dispatcher base URL, e.g. `https://hive.example.com`
- `HIVE_INTERNAL_TOKEN` – (optional) Bearer token for POST `/enqueue`
- `HIVE_CALLBACK_SECRET` – (optional) Secret for POST `/callback`

## Usage

### Server actions / API routes

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

### Enqueue from a server action

```ts
import { envClient, EnqueueBody } from "hive";

export async function enqueueJob(body: EnqueueBody) {
  const client = envClient();
  return client.enqueue(body);
}
```

### Worker callback helper

```ts
import { HiveClient } from "hive";

const client = new HiveClient(process.env.HIVE_BASE_URL!, {
  callbackSecret: process.env.HIVE_CALLBACK_SECRET,
});

await client.callback({
  claimId: "123",
  workerId: "worker-1",
  status: "succeeded",
  logs: "done",
});
```

## License

MIT
