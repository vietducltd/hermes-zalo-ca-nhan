// Cầu nối giữa Hermes (Python) và Zalo cá nhân (zca-js).
// Mỗi dòng stdout là một JSON; ở chế độ serve, mỗi dòng stdin là một yêu cầu JSON.
import fs from "node:fs/promises";
import path from "node:path";
import readline from "node:readline";
import { Zalo, ThreadType, LoginQRCallbackEventType } from "zca-js";
import { shapeMessage, shapeGroup, shapeFriend, SentLog } from "./shape.mjs";

const [, , command, ...argv] = process.argv;

function flag(name) {
  const index = argv.indexOf(name);
  return index >= 0 ? argv[index + 1] : null;
}

function out(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

// Chờ stdout ghi xong rồi mới thoát; trên Windows thoát ngay có thể làm mất dòng cuối.
function finish(code) {
  process.stdout.write("", () => process.exit(code));
}

function describe(error) {
  return String(error?.message ?? error);
}

const zaloOptions = { selfListen: true, checkUpdate: false, logging: false };

async function saveSession(file, session) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const draft = `${file}.${process.pid}.tmp`;
  await fs.writeFile(draft, JSON.stringify(session), { encoding: "utf8", mode: 0o600 });
  await fs.rename(draft, file);
}

async function connect() {
  const file = flag("--session");
  if (!file) throw new Error("thiếu --session");
  const session = JSON.parse(await fs.readFile(file, "utf8"));
  return new Zalo(zaloOptions).login(session);
}

async function login() {
  const sessionPath = flag("--session");
  const qrPath = flag("--qr");
  if (!sessionPath || !qrPath) throw new Error("thiếu --session hoặc --qr");
  const api = await new Zalo(zaloOptions).loginQR({ qrPath }, async (event) => {
    switch (event.type) {
      case LoginQRCallbackEventType.QRCodeGenerated:
        await event.actions.saveToFile(qrPath);
        out({ t: "qr", file: qrPath });
        break;
      case LoginQRCallbackEventType.QRCodeScanned:
        out({ t: "scanned", name: String(event.data?.display_name ?? "") });
        break;
      case LoginQRCallbackEventType.QRCodeExpired:
        out({ t: "expired" });
        event.actions.retry();
        break;
      case LoginQRCallbackEventType.QRCodeDeclined:
        out({ t: "declined" });
        event.actions.abort();
        break;
      case LoginQRCallbackEventType.GotLoginInfo:
        await saveSession(sessionPath, event.data);
        break;
    }
  });
  out({ t: "logged_in", self: String(api.getOwnId()) });
}

async function groups() {
  const api = await connect();
  const ids = Object.keys((await api.getAllGroups())?.gridVerMap ?? {});
  const details = ids.length ? (await api.getGroupInfo(ids))?.gridInfoMap ?? {} : {};
  const items = ids.map((id) => shapeGroup(id, details[id])).sort((a, b) => a.name.localeCompare(b.name, "vi"));
  out({ t: "groups", items });
}

async function group() {
  const link = flag("--link");
  if (!link) throw new Error("thiếu --link");
  const api = await connect();
  const info = await api.getGroupLinkInfo({ link });
  out({ t: "group", item: shapeGroup(info.groupId, info) });
}

async function friends() {
  const api = await connect();
  const items = (await api.getAllFriends()).map(shapeFriend).sort((a, b) => a.name.localeCompare(b.name, "vi"));
  out({ t: "friends", self: String(api.getOwnId()), items });
}

async function serve() {
  const api = await connect();
  const sent = new SentLog();

  api.listener.on("message", (raw) => {
    const message = shapeMessage(raw);
    if (message.self) message.byBot = sent.isOurs(message);
    out(message);
  });
  api.listener.on("connected", () => out({ t: "status", state: "connected" }));
  api.listener.on("error", (error) => out({ t: "status", state: "error", error: describe(error) }));
  // zca-js chỉ phát "closed" khi đã hết lượt tự nối lại, nên coi như mất kết nối hẳn.
  api.listener.on("closed", (code, reason) => {
    out({ t: "fatal", code: Number(code), error: `Zalo đóng kết nối (${code}) ${reason ?? ""}`.trim() });
    finish(1);
  });
  api.listener.start({ retryOnClose: true });
  out({ t: "ready", self: String(api.getOwnId()) });

  const requests = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  requests.on("line", async (line) => {
    let request;
    try {
      request = JSON.parse(line);
    } catch {
      return;
    }
    try {
      if (request.op === "send") {
        const threadId = String(request.threadId);
        const text = String(request.text ?? "");
        // Ghi nhớ nội dung trước khi gửi: bản sao tin của chính mình có thể về trước cả kết quả gửi.
        sent.noteText(threadId, text);
        const type = request.kind === "group" ? ThreadType.Group : ThreadType.User;
        const result = await api.sendMessage({ msg: text }, threadId, type);
        const msgId = String(result?.message?.msgId ?? "");
        sent.noteId(msgId);
        out({ t: "reply", id: request.id, ok: true, msgId });
      } else if (request.op === "stop") {
        out({ t: "reply", id: request.id, ok: true });
        api.listener.stop();
        finish(0);
      } else {
        out({ t: "reply", id: request.id, ok: false, error: `không hỗ trợ lệnh ${request.op}` });
      }
    } catch (error) {
      out({ t: "reply", id: request.id, ok: false, error: describe(error) });
    }
  });
  // Hermes tắt thì stdin đóng; thoát theo để không còn tiến trình mồ côi giữ kết nối Zalo.
  requests.on("close", () => process.exit(0));
}

const commands = { login, groups, group, friends, serve };

try {
  if (!commands[command]) throw new Error("cách dùng: bridge.mjs login|groups|group|friends|serve");
  await commands[command]();
  if (command !== "serve") finish(0);
} catch (error) {
  out({ t: "fatal", error: describe(error) });
  finish(1);
}
