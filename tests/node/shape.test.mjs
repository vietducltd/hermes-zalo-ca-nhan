import test from "node:test";
import assert from "node:assert/strict";
import { shapeMessage, shapeGroup, shapeFriend, SentLog } from "../../node/shape.mjs";

test("tin nhắn chữ gửi riêng", () => {
  const message = shapeMessage({ type: 0, threadId: "u1", isSelf: false, data: { uidFrom: "u1", msgId: "m1", content: "xin chào", dName: "Khách" } });
  assert.equal(message.kind, "user");
  assert.equal(message.text, "xin chào");
  assert.equal(message.senderName, "Khách");
  assert.equal(message.self, false);
});

test("ảnh trong nhóm kèm mention", () => {
  const message = shapeMessage({ type: 1, threadId: "g1", isSelf: false, data: { uidFrom: "u2", msgId: "m2", content: { href: "x" }, mentions: [{ uid: "bot" }] } });
  assert.equal(message.kind, "group");
  assert.equal(message.text, null);
  assert.deepEqual(message.mentions, ["bot"]);
});

test("dữ liệu thiếu không làm sập", () => {
  const message = shapeMessage(undefined);
  assert.equal(message.threadId, "");
  assert.deepEqual(message.mentions, []);
});

test("nhóm và bạn bè chỉ giữ ID, tên, số thành viên", () => {
  assert.deepEqual(shapeGroup("g1", { name: "Nhóm thử", totalMember: 12, adminIds: ["a"] }), { id: "g1", name: "Nhóm thử", members: 12 });
  assert.deepEqual(shapeFriend({ userId: "u1", displayName: "", zaloName: "An", phoneNumber: "09" }), { id: "u1", name: "An" });
});

test("phân biệt tin bot gửi với tin chủ tài khoản gõ tay", () => {
  const log = new SentLog(60_000);
  log.noteText("u1", "Dạ em chào anh ", 1_000);
  // Bản sao tin của bot về trước khi có msgId: nhận ra nhờ nội dung.
  assert.equal(log.isOurs({ threadId: "u1", msgId: "m1", text: "Dạ em chào anh" }, 2_000), true);
  log.noteId("m1");
  assert.equal(log.isOurs({ threadId: "u1", msgId: "m1", text: "khác" }, 2_000), true);
  assert.equal(log.isOurs({ threadId: "u1", msgId: "m2", text: "Để anh tư vấn trực tiếp nhé" }, 2_000), false);
  assert.equal(log.isOurs({ threadId: "u2", msgId: "m3", text: "Dạ em chào anh" }, 2_000), false);
  assert.equal(log.isOurs({ threadId: "u1", msgId: "m4", text: "Dạ em chào anh" }, 120_000), false);
});
