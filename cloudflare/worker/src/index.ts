import { ContainerProxy, getSandbox, Sandbox } from "@cloudflare/sandbox";

export { ContainerProxy };

type Env = {
  Sandbox: DurableObjectNamespace<SkillSandbox>;
  Telemetry: DurableObjectNamespace;
  PROVIDER_API_KEY?: string;
};

type OutboundContext = {
  containerId: string;
  params: unknown;
};

type EgressEvent = {
  ts: string;
  containerId: string;
  method: string;
  url: string;
  decision: "allow" | "deny";
  reason: string;
};

async function recordEgress(env: Env, ctx: OutboundContext, event: EgressEvent) {
  const stub = env.Telemetry.get(env.Telemetry.idFromName(ctx.containerId));
  await stub.fetch("https://telemetry.local/event", {
    method: "POST",
    body: JSON.stringify(event),
    headers: {"content-type": "application/json"},
  });
}

export class SkillSandbox extends Sandbox {
  enableInternet = false;
  allowedHosts = ["api.groq.com", "generativelanguage.googleapis.com", "api.cloudflare.com"];
}

SkillSandbox.outbound = async (request: Request, env: Env, ctx: OutboundContext) => {
  const url = new URL(request.url);
  if (!["GET", "HEAD", "OPTIONS", "POST"].includes(request.method)) {
    await recordEgress(env, ctx, {
      ts: new Date().toISOString(), containerId: ctx.containerId,
      method: request.method, url: request.url, decision: "deny", reason: "method",
    });
    return new Response("Method Not Allowed", {status: 405});
  }
  await recordEgress(env, ctx, {
    ts: new Date().toISOString(), containerId: ctx.containerId,
    method: request.method, url: request.url, decision: "allow", reason: `host:${url.hostname}`,
  });
  return fetch(request);
};

SkillSandbox.outboundByHost = {
  "api.groq.com": async (request: Request, env: Env, ctx: OutboundContext) => {
    const forwarded = new Request(request);
    if (env.PROVIDER_API_KEY) forwarded.headers.set("authorization", `Bearer ${env.PROVIDER_API_KEY}`);
    await recordEgress(env, ctx, {
      ts: new Date().toISOString(), containerId: ctx.containerId,
      method: request.method, url: request.url, decision: "allow", reason: "brokered-credential",
    });
    return fetch(forwarded);
  },
};

export class Telemetry {
  constructor(private state: DurableObjectState, private env: Env) {}

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/event" && request.method === "POST") {
      const events = (await this.state.storage.get<EgressEvent[]>("events")) ?? [];
      events.push(await request.json<EgressEvent>());
      await this.state.storage.put("events", events.slice(-1000));
      return Response.json({ok: true});
    }
    if (url.pathname === "/events") {
      return Response.json({events: (await this.state.storage.get<EgressEvent[]>("events")) ?? []});
    }
    if (url.pathname === "/seen") {
      const seen = (await this.state.storage.get<boolean>("seen")) ?? false;
      await this.state.storage.put("seen", true);
      return Response.json({reused: seen});
    }
    if (request.method === "DELETE") {
      await this.state.storage.deleteAll();
      return Response.json({ok: true});
    }
    return new Response("not found", {status: 404});
  }
}

function idFromPath(pathname: string): string | null {
  const parts = pathname.split("/").filter(Boolean);
  return parts[0] === "v1" && parts[1] === "sandboxes" ? parts[2] ?? null : null;
}

async function manifest(sandbox: ReturnType<typeof getSandbox>) {
  const result = await sandbox.exec("find /workspace -xdev -type f -exec sha256sum -- {} + 2>/dev/null | sort || true");
  const files: Record<string, string> = {};
  for (const line of result.stdout.split("\n")) {
    const match = line.trim().match(/^([a-f0-9]{64})\s+\*?(.*)$/);
    if (match) files[match[2]] = match[1];
  }
  return files;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/healthz") return Response.json({status: "ok", backend: "cloudflare-sandbox"});
    const id = idFromPath(url.pathname);
    if (!id || !/^[a-zA-Z0-9._-]{1,96}$/.test(id)) return new Response("not found", {status: 404});

    const sandbox = getSandbox(env.Sandbox, id, {enableDefaultSession: false});
    const telemetry = env.Telemetry.get(env.Telemetry.idFromName(id));
    const suffix = url.pathname.split("/").filter(Boolean)[3] ?? "";

    if (request.method === "GET" && suffix === "") {
      const seen = await telemetry.fetch("https://telemetry.local/seen");
      const state = await seen.json<{reused: boolean}>();
      return Response.json({id, reused: state.reused, runtime: "cloudflare-sandbox"});
    }
    if (request.method === "POST" && suffix === "exec") {
      const body = await request.json<{command: string; timeoutMs?: number}>();
      const started = Date.now();
      const result = await sandbox.exec(body.command);
      return Response.json({
        stdout: result.stdout,
        stderr: result.stderr,
        exitCode: result.exitCode,
        success: result.success,
        metadata: {durationMs: Date.now() - started, timeoutMs: body.timeoutMs ?? null},
      });
    }
    if (request.method === "GET" && suffix === "manifest") {
      return Response.json({files: await manifest(sandbox)});
    }
    if (request.method === "GET" && suffix === "events") {
      return telemetry.fetch("https://telemetry.local/events");
    }
    if (request.method === "DELETE" && suffix === "") {
      await sandbox.destroy();
      await telemetry.fetch("https://telemetry.local", {method: "DELETE"});
      return Response.json({ok: true});
    }
    return new Response("not found", {status: 404});
  },
};
