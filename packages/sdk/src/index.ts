import { request } from "undici";
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
  metadata: z.record(z.unknown()).optional(),
});

export type EnqueueBody = z.infer<typeof EnqueueSchema>;

export type ClaimResponse =
  | { job: (EnqueueBody & { claimId: string }) | null }
  | { error: string };

export type CallbackPayload = {
  claimId: string;
  workerId: string;
  status: "running" | "succeeded" | "failed";
  logs?: string;
  metadata?: Record<string, unknown>;
};

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/$/, "");
}

async function requestJson<T>(url: string, init: RequestInit): Promise<T> {
  const response = await request(url, init);
  const body = await response.body.json();
  return body as T;
}

/**
 * Minimal HTTP client to speak with a Hive dispatcher instance.
 */
export class HiveClient {
  private readonly baseUrl: string;
  private readonly internalToken?: string;
  private readonly callbackSecret?: string;

  constructor(
    baseUrl: string,
    options: { internalToken?: string; callbackSecret?: string } = {},
  ) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    this.internalToken = options.internalToken;
    this.callbackSecret = options.callbackSecret;
  }

  async health<T = Record<string, unknown>>(): Promise<T> {
    return requestJson<T>(`${this.baseUrl}/health`, { method: "GET" });
  }

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

  async claim(): Promise<ClaimResponse> {
    return requestJson(`${this.baseUrl}/claim`, { method: "POST" });
  }

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
 */
export function createNextClaimRoute(client: HiveClient) {
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
 */
export function createNextCallbackRoute(client: HiveClient) {
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
 */
export function envClient(): HiveClient {
  const baseUrl = process.env.HIVE_BASE_URL ?? "http://localhost:8099";
  return new HiveClient(baseUrl, {
    internalToken: process.env.HIVE_INTERNAL_TOKEN,
    callbackSecret: process.env.HIVE_CALLBACK_SECRET,
  });
}
