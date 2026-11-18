// The Gameplay tool inside the teacher's Pi container: registers the tools in tools.json and
// forwards every call to the host's play server at the address in play.json.
import * as net from "node:net";
import { readFileSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const ADDRESS = JSON.parse(readFileSync("/opt/play/play.json", "utf8"));  // {path} or, on Docker Desktop, {host, port}

function play(args: any): Promise<any> {
  return new Promise((resolve) => {
    let buf = "";
    const s = net.createConnection(ADDRESS, () => s.write(JSON.stringify(args) + "\n"));
    s.on("data", (d) => { buf += d.toString(); });
    s.on("error", (e) => resolve({ error: `play bridge error: ${e}` }));
    s.on("close", () => resolve(buf.trim() ? JSON.parse(buf) : { error: "the play server closed the connection" }));
  });
}

export default function (pi: ExtensionAPI) {
  for (const tool of JSON.parse(readFileSync("/opt/play/tools.json", "utf8"))) {
    pi.registerTool({
      name: tool.name, label: tool.name, description: tool.description, parameters: tool.inputSchema,
      async execute(_id: string, params: any) {
        const reply = await play(Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v != null)));
        const text = JSON.stringify(reply, null, 2);
        if ("error" in reply) throw new Error(text);
        return { content: [{ type: "text", text }], details: {} };
      },
    });
  }
}
