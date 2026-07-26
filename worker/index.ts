import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS?: Fetcher;
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

const worker = {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/") {
      url.pathname = "/submission.html";
      if (env?.ASSETS) {
        return env.ASSETS.fetch(new Request(url, request));
      }
      // `vinext start` runs the Worker without Cloudflare bindings. Redirect
      // through its built-in public-file handler for a faithful local preview.
      return Response.redirect(url, 302);
    }
    return handler.fetch(request, env, ctx);
  },
};

export default worker;
