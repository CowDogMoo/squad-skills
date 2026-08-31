// The Signal half of the week ritual.
//
// The household reads the proposed week and the shopping list on their phones,
// in the thread they already use, so both sends go through the signal-cli REST
// bridge on the Proxmox LXC rather than a second notification channel.
//
// Two environment facts shape this file, and they are the same two that shape
// mealie.mjs:
//
//   1. Node's own sockets are blocked on this host — undici gets EHOSTUNREACH
//      on the LAN while curl is proxied through fine. Every request shells out
//      to curl. Do not "modernize" this to fetch().
//   2. The bridge must run in json-rpc mode. In MODE=normal signal-cli is
//      spawned per request and extracts ~153 MB of libsignal into /tmp every
//      time; about fifty sends fill the 7.8 G rootfs and the API starts
//      answering 400 "No space left on device". In json-rpc mode one daemon
//      extracts it once at startup and every send reuses it.

import { execFileSync } from "node:child_process";

export const SIGNAL_API = (process.env.SIGNAL_API || "http://192.168.20.45:8080").replace(/\/+$/, "");
export const SIGNAL_NUMBER = process.env.SIGNAL_NUMBER || "+15056904961";
export const SIGNAL_RECIPIENTS = (process.env.SIGNAL_RECIPIENTS || SIGNAL_NUMBER)
  .split(",")
  .map((r) => r.trim())
  .filter(Boolean);

const STATUS_SEP = "\n<<<SIGNAL-HTTP-STATUS>>>";

/** One bridge request. Returns { status, ok, text, json }. */
export function request(path, { method = "GET", body, timeoutMs = 60000 } = {}) {
  const args = [
    "-sS",
    "--max-time",
    String(Math.round(timeoutMs / 1000)),
    "-X",
    method,
    "-o",
    "-",
    "-w",
    `${STATUS_SEP}%{http_code}`,
  ];
  if (body !== undefined) {
    args.push("-H", "Content-Type: application/json", "--data-binary", JSON.stringify(body));
  }
  args.push(SIGNAL_API + path);

  let raw = "";
  let transportFailed = false;
  try {
    raw = execFileSync("curl", args, {
      encoding: "utf8",
      timeout: timeoutMs + 15000,
      maxBuffer: 8 * 1024 * 1024,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (err) {
    raw = `${err.stdout || ""}`;
    transportFailed = true;
  }
  const cut = raw.lastIndexOf(STATUS_SEP);
  const text = cut === -1 ? raw : raw.slice(0, cut);
  const status = cut === -1 ? 0 : Number(raw.slice(cut + STATUS_SEP.length).trim()) || 0;
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* the bridge answers plain text on some errors; callers check json for null */
  }
  return { status, ok: !transportFailed && status >= 200 && status < 300, text, json };
}

/** What the bridge says about itself: { mode, version, ... }. */
export function about() {
  const res = request("/v1/about");
  if (!res.ok || !res.json) {
    throw new Error(`signal bridge ${SIGNAL_API}/v1/about -> ${res.status}: ${res.text.slice(0, 200)}`);
  }
  return res.json;
}

/**
 * Send one message to the household thread and return the signal-cli send
 * timestamp, which is the only proof the message actually left the bridge.
 *
 * A bridge still in MODE=normal will send this fine and then leak another
 * 153 MB, so warn rather than fail: a working delivery is worth more than a
 * tidy one, and the operator gets told what to fix.
 */
export function send(message, { recipients = SIGNAL_RECIPIENTS, number = SIGNAL_NUMBER, checkMode = true } = {}) {
  if (!message || !message.trim()) throw new Error("refusing to send an empty Signal message");
  if (!recipients.length) throw new Error("no Signal recipients configured");

  if (checkMode) {
    try {
      const mode = about().mode;
      if (mode !== "json-rpc") {
        process.stderr.write(
          `warning: the Signal bridge is in MODE=${mode}, not json-rpc. Every send leaks ~153 MB into ` +
            `/tmp/libsignal* and will eventually fill the LXC rootfs. Fix MODE in ` +
            `/opt/signal-bridge/docker-compose.yml on LXC 109.\n`,
        );
      }
    } catch (err) {
      process.stderr.write(`warning: could not read the bridge mode (${err.message})\n`);
    }
  }

  const res = request("/v2/send", { method: "POST", body: { message, number, recipients } });
  if (!res.ok) {
    throw new Error(`POST ${SIGNAL_API}/v2/send -> ${res.status}: ${res.text.slice(0, 300)}`);
  }
  const timestamp = res.json && (res.json.timestamp ?? res.json.timestamps);
  if (timestamp === undefined || timestamp === null || timestamp === "") {
    throw new Error(`the bridge accepted the send but returned no timestamp: ${res.text.slice(0, 200)}`);
  }
  return String(Array.isArray(timestamp) ? timestamp[0] : timestamp);
}
