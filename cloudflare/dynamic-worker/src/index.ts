type WorkerCode = {
  compatibilityDate: string;
  mainModule: string;
  modules: Record<string, string>;
  globalOutbound: null;
};

type Loader = {
  load(code: WorkerCode): { getEntrypoint(): { fetch(request: Request): Promise<Response> } };
};

type Env = { LOADER: Loader };

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/healthz") return Response.json({status: "ok", backend: "dynamic-workers"});
    if (url.pathname !== "/v1/execute" || request.method !== "POST") {
      return new Response("not found", {status: 404});
    }

    const body = await request.json<{code: string; input?: unknown}>();
    if (typeof body.code !== "string" || body.code.length > 200_000) {
      return Response.json({error: "invalid code"}, {status: 400});
    }

    const started = Date.now();
    const worker = env.LOADER.load({
      compatibilityDate: "2026-08-09",
      mainModule: "index.js",
      modules: {"index.js": body.code},
      globalOutbound: null,
    });
    const entrypoint = worker.getEntrypoint();
    const childRequest = new Request("https://dynamic.local/", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify(body.input ?? null),
    });
    const response = await entrypoint.fetch(childRequest);
    return Response.json({
      status: response.status,
      body: await response.text(),
      durationMs: Date.now() - started,
      network: "blocked",
      coldStart: true,
    });
  },
};
