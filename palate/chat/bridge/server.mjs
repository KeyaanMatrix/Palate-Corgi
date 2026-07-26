/**
 * Spectrum send bridge. Photon has no public HTTP send API — this process
 * holds a spectrum-ts connection and exposes loopback POST /send for Python.
 *
 * Env: SPECTRUM_PROJECT_ID, SPECTRUM_PROJECT_SECRET (or PHOTON_API_KEY=id:secret)
 *      PHOTON_BRIDGE_PORT (default 8787)
 */
import http from "node:http";
import { Spectrum } from "@spectrum-ts/core";
import { imessage } from "@spectrum-ts/imessage";

const PORT = Number(process.env.PHOTON_BRIDGE_PORT || 8787);
const BIND = "127.0.0.1";

function credentials() {
  let projectId = process.env.SPECTRUM_PROJECT_ID || "";
  let projectSecret = process.env.SPECTRUM_PROJECT_SECRET || "";
  if (!projectId || !projectSecret) {
    const key = process.env.PHOTON_API_KEY || "";
    const i = key.indexOf(":");
    if (i > 0) {
      projectId = key.slice(0, i);
      projectSecret = key.slice(i + 1);
    }
  }
  if (!projectId || !projectSecret) {
    throw new Error(
      "Set SPECTRUM_PROJECT_ID + SPECTRUM_PROJECT_SECRET (or PHOTON_API_KEY=id:secret)",
    );
  }
  return { projectId, projectSecret };
}

const { projectId, projectSecret } = credentials();

const app = await Spectrum({
  projectId,
  projectSecret,
  providers: [imessage.config()],
});
const im = imessage(app);

async function sendText(to, text) {
  const user = await im.user(to);
  // space.create resolves-or-creates a DM from the E.164 user.
  const space = await im.space.create(user);
  const message = await space.send(text);
  if (!message?.id) {
    throw new Error("space.send returned no message id");
  }
  return message.id;
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${BIND}:${PORT}`);

  if (req.method === "GET" && url.pathname === "/health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  if (req.method === "POST" && url.pathname === "/send") {
    try {
      const raw = await readBody(req);
      const body = JSON.parse(raw || "{}");
      const to = String(body.to || "").trim();
      const text = String(body.text ?? "");
      if (!to) {
        res.writeHead(400, { "content-type": "application/json" });
        res.end(JSON.stringify({ ok: false, error: "missing to" }));
        return;
      }
      const id = await sendText(to, text);
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ ok: true, id }));
    } catch (err) {
      console.error("[bridge] send failed:", err);
      res.writeHead(500, { "content-type": "application/json" });
      res.end(JSON.stringify({ ok: false, error: String(err?.message || err) }));
    }
    return;
  }

  res.writeHead(404, { "content-type": "application/json" });
  res.end(JSON.stringify({ ok: false, error: "not found" }));
});

server.listen(PORT, BIND, () => {
  console.log(`[bridge] spectrum send listening on http://${BIND}:${PORT}`);
});

async function shutdown() {
  try {
    await app.stop();
  } catch (_) {
    /* ignore */
  }
  server.close();
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
