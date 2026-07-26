import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS: Fetcher;
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
      return env.ASSETS.fetch(new Request(url, request));
    }
    return handler.fetch(request, env, ctx);
  },
};

export default worker;
