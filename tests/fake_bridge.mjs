// Bridge giả cho test: nói đúng giao thức của node/bridge.mjs nhưng không đụng tới Zalo.
import readline from "node:readline";

const mode = process.argv[2];
const out = (payload) => process.stdout.write(`${JSON.stringify(payload)}\n`);

if (mode === "die") {
  out({ t: "fatal", code: 3000, error: "bị đá khỏi phiên" });
  process.stdout.write("", () => process.exit(1));
} else {
  console.log("dòng log không phải JSON phải được bỏ qua");
  out({ t: "ready", self: "bot-1" });
  let sent = 0;
  readline.createInterface({ input: process.stdin }).on("line", (line) => {
    const request = JSON.parse(line);
    if (request.op === "send") {
      sent += 1;
      out({ t: "reply", id: request.id, ok: true, msgId: `sent-${sent}` });
    } else if (request.op === "poke") {
      out({ t: "reply", id: request.id, ok: true });
      out({ t: "message", threadId: "u1", kind: "user", senderId: "u1", msgId: "in-1", text: request.text, self: false, mentions: [] });
    } else if (request.op === "crash") {
      out({ t: "fatal", code: 1006, error: "rớt mạng" });
      process.stdout.write("", () => process.exit(1));
    } else {
      out({ t: "reply", id: request.id, ok: false, error: "không hỗ trợ" });
    }
  });
}
