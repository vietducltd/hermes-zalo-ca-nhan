// Chuyển dữ liệu thô của zca-js thành gói tin gọn gửi sang Python.
// Không import zca-js để test chạy được mà không cần cài thư viện.

export function shapeMessage(message) {
  const data = message?.data ?? {};
  const isGroup = message?.type === 1 || String(message?.type).toLowerCase() === "group";
  const text = typeof data.content === "string" ? data.content : null;
  return {
    t: "message",
    threadId: String(message?.threadId ?? ""),
    kind: isGroup ? "group" : "user",
    senderId: String(data.uidFrom ?? ""),
    senderName: String(data.dName ?? ""),
    msgId: String(data.msgId ?? data.cliMsgId ?? ""),
    text,
    self: Boolean(message?.isSelf),
    mentions: Array.isArray(data.mentions) ? data.mentions.map((item) => String(item?.uid ?? "")) : [],
  };
}

export function shapeGroup(groupId, info = {}) {
  return {
    id: String(groupId ?? ""),
    name: String(info?.name ?? "(không rõ tên)"),
    members: Number(info?.totalMember ?? 0),
  };
}

export function shapeFriend(user = {}) {
  return {
    id: String(user?.userId ?? ""),
    name: String(user?.displayName || user?.zaloName || "(không rõ tên)"),
  };
}

// Nhớ các tin bot vừa gửi để phân biệt với tin chủ tài khoản tự gõ tay.
export class SentLog {
  constructor(windowMs = 60_000) {
    this.windowMs = windowMs;
    this.ids = new Set();
    this.texts = [];
  }

  noteText(threadId, text, now = Date.now()) {
    this.texts = this.texts.filter((item) => now - item.at < this.windowMs);
    this.texts.push({ threadId: String(threadId), text: String(text).trim(), at: now });
  }

  noteId(msgId) {
    if (msgId) this.ids.add(String(msgId));
  }

  isOurs(message, now = Date.now()) {
    if (message.msgId && this.ids.has(message.msgId)) return true;
    const text = String(message.text ?? "").trim();
    return this.texts.some(
      (item) => item.threadId === message.threadId && item.text === text && now - item.at < this.windowMs,
    );
  }
}
