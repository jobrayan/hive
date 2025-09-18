import { z } from "zod";

/**
 * Schema describing the minimal job payload accepted by the dispatcher.
 */
export const EnqueueSchema = z.object({
  jobId: z.string(),
  task: z.enum(["agent", "script", "custom"]),
  instructions: z.string(),
  repo: z.string().url().optional(),
  branch: z.string().optional(),
  base: z.string().optional(),
  githubToken: z.string().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export type EnqueueBody = z.infer<typeof EnqueueSchema>;

/**
 * The response for a claim attempt:
 * - Either `job: { ... , claimId }` when a job is available
 * - Or `error` string describing why a job was not returned
 */
export type ClaimResponse =
  | { job: (EnqueueBody & { claimId: string }) | null }
  | { error: string };

/**
 * Worker callback payload describing the current status and optional logs/metadata.
 */
export type CallbackPayload = {
  claimId: string;
  workerId: string;
  status: "running" | "succeeded" | "failed";
  logs?: string;
  metadata?: Record<string, unknown>;
};

/**
 * Normalize a base URL by removing a trailing slash so downstream paths
 * can be concatenated with a single slash.
 *
 * @param baseUrl - Raw base URL (may end with '/')
 * @returns Normalized base URL without trailing slash
 */
function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/$/, "");
}

/**
 * Perform an HTTP request and parse JSON with strict error propagation.
 *
 * - Uses global `fetch` (Node ≥ 18 / Next.js runtimes).
 * - Throws on non-2xx with response text included for easier diagnosis.
 *
 * @typeParam T - Expected JSON body type
 * @param url - Absolute or relative URL
 * @param init - Fetch init options
 * @returns Parsed JSON body
 * @throws Error with HTTP status & body snippet when `res.ok` is false
 */
async function requestJson<T>(url: string, init: RequestInit): Promise<T> {
  const res = await fetch(url, init);

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${text}`);
  }

  return (await res.json()) as T;
}

/**
 * Safe environment variable reader that doesn't rely on Node.js types.
 * Works in Node (CJS/ESM), Edge, Workers, and Browser (returns undefined).
 *
 * @param name - Environment variable key to read
 * @returns The value if found, otherwise undefined
 */
function readEnv(name: string): string | undefined {
  try {
    const g = globalThis as any;
    return g?.process?.env?.[name] ?? undefined;
  } catch {
    return undefined;
  }
}

/**
 * Minimal HTTP client to speak with a Hive dispatcher instance.
 */
export class HiveClient {
  private readonly baseUrl: string;
  private readonly internalToken?: string;
  private readonly callbackSecret?: string;

  /**
   * Construct a HiveClient.
   *
   * @param baseUrl - Dispatcher base URL (e.g., "http://localhost:8099")
   * @param options - Optional authorization secrets
   * @param options.internalToken - Bearer token for protected dispatcher endpoints
   * @param options.callbackSecret - Shared secret for `/callback` header ("x-callback-secret")
   */
  constructor(
    baseUrl: string,
    options: { internalToken?: string; callbackSecret?: string } = {},
  ) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    this.internalToken = options.internalToken;
    this.callbackSecret = options.callbackSecret;
  }

  /**
   * Check health of the dispatcher.
   *
   * @typeParam T - Shape of the expected health response
   * @returns Dispatcher health JSON payload
   */
  async health<T = Record<string, unknown>>(): Promise<T> {
    return requestJson<T>(`${this.baseUrl}/health`, { method: "GET" });
  }

  /**
   * Enqueue a job onto the dispatcher.
   *
   * @param job - Job payload matching {@link EnqueueSchema}
   * @returns Acceptance & current queue length
   */
  async enqueue(job: EnqueueBody): Promise<{ accepted: boolean; queueLength: number }> {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (this.internalToken) {
      headers.authorization = `Bearer ${this.internalToken}`;
    }
    return requestJson(`${this.baseUrl}/enqueue`, {
      method: "POST",
      headers,
      body: JSON.stringify(job),
    });
  }

  /**
   * Claim the next available job for a worker.
   *
   * @returns A job with a claimId, or an error message, or `job: null` if empty
   */
  async claim(): Promise<ClaimResponse> {
    return requestJson(`${this.baseUrl}/claim`, { method: "POST" });
  }

  /**
   * Send a worker callback (status/logs/metadata) to the dispatcher.
   *
   * @param payload - Worker status update
   * @returns `{ ok: boolean, error?: string }`
   */
  async callback(payload: CallbackPayload): Promise<{ ok: boolean; error?: string }> {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (this.callbackSecret) {
      headers["x-callback-secret"] = this.callbackSecret;
    }
    return requestJson(`${this.baseUrl}/callback`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
  }
}

/**
 * Create a Next.js App Router handler that proxies POST /claim to the dispatcher.
 *
 * @param client - A configured {@link HiveClient} instance
 * @returns App Router POST handler
 */
export function createNextClaimRoute(client: HiveClient) {
  /**
   * POST handler which claims a job from the dispatcher.
   *
   * @returns A standard `Response` containing the claim result as JSON
   */
  return async function POST(): Promise<Response> {
    const data = await client.claim();
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
}

/**
 * Create a Next.js App Router handler that forwards worker callbacks to the dispatcher.
 *
 * @param client - A configured {@link HiveClient} instance
 * @returns App Router POST handler that validates shared secret (if set)
 */
export function createNextCallbackRoute(client: HiveClient) {
  /**
   * POST handler which forwards worker callback payloads to the dispatcher.
   *
   * @param req - Incoming request containing the {@link CallbackPayload}
   * @returns A standard `Response` with `200` on success, `401` on failure
   */
  return async function POST(req: Request): Promise<Response> {
    const body = await req.json();
    const data = await client.callback(body as CallbackPayload);
    return new Response(JSON.stringify(data), {
      status: data.ok ? 200 : 401,
      headers: { "content-type": "application/json" },
    });
  };
}

/**
 * Helper that reads standard Hive environment variables to build a client instance.
 *
 * Env:
 * - `HIVE_BASE_URL` (default: http://localhost:8099)
 * - `HIVE_INTERNAL_TOKEN` (optional)
 * - `HIVE_CALLBACK_SECRET` (optional)
 *
 * @returns A configured {@link HiveClient}
 */
export function envClient(): HiveClient {
  const baseUrl = readEnv("HIVE_BASE_URL") ?? "http://localhost:8099";
  return new HiveClient(baseUrl, {
    internalToken: readEnv("HIVE_INTERNAL_TOKEN"),
    callbackSecret: readEnv("HIVE_CALLBACK_SECRET"),
  });
}
