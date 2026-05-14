const taskForm = document.getElementById("taskForm");
const taskInput = document.getElementById("taskInput");
const submitBtn = document.getElementById("submitBtn");
const statusEl = document.getElementById("status");
const resultBox = document.getElementById("resultBox");
const chatStreamEl = document.getElementById("chatStream");
const chatAppEl = document.getElementById("chatApp");

let activeJobId = null;
let cursor = 0;
let pollTimer = null;

function setStatus(text, type) {
  statusEl.textContent = `状态：${text}`;
  statusEl.className = `status ${type}`;
}

function setResult(value) {
  resultBox.textContent = value;
}

function activateConversationMode() {
  if (chatAppEl && chatAppEl.classList.contains("pre-input")) {
    chatAppEl.classList.remove("pre-input");
  }
}

function clearChat() {
  chatStreamEl.innerHTML = "";
}

function shortName(name) {
  const raw = (name || "agent").toLowerCase();
  if (raw.includes("coordinator")) return "CO";
  if (raw.includes("product")) return "PM";
  if (raw.includes("engineer") && !raw.includes("qa")) return "EN";
  if (raw.includes("qa")) return "QA";
  if (raw.includes("user")) return "YOU";
  return "AG";
}

function appendBubble({ sender, text, side = "left", kind = "agent" }) {
  const row = document.createElement("div");
  row.className = `bubble-row ${side}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = shortName(sender);

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (kind === "system") bubble.classList.add("system");
  if (kind === "user") bubble.classList.add("user");

  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent = sender;

  const content = document.createElement("div");
  content.textContent = text;

  bubble.appendChild(meta);
  bubble.appendChild(content);

  if (side === "right") {
    row.appendChild(bubble);
    row.appendChild(avatar);
  } else {
    row.appendChild(avatar);
    row.appendChild(bubble);
  }

  chatStreamEl.appendChild(row);
  chatStreamEl.scrollTop = chatStreamEl.scrollHeight;
}

function renderEvent(event) {
  if (event.type === "status") {
    appendBubble({
      sender: "System",
      text: event.message || "状态更新",
      side: "left",
      kind: "system",
    });
    // 检测 complete 阶段
    if (event.stage === "complete") {
      appendBubble({
        sender: "System",
        text: "🎉 所有处理完成，任务已结束",
        side: "left",
        kind: "system",
      });
    }
    return;
  }

  if (event.type !== "message") return;

  const rawSender = event.sender || "unknown";
  const sender = rawSender === "User_Proxy" ? "System" : rawSender;
  const senderLower = sender.toLowerCase();
  const isUser = senderLower.includes("user");

  appendBubble({
    sender,
    text: event.content || "",
    side: isUser ? "right" : "left",
    kind: isUser ? "user" : "agent",
  });
  
  // 检测消息中的 TERMINATE 并显示提示
  const content = event.content || "";
  if (content.includes("TERMINATE")) {
    appendBubble({
      sender: "System",
      text: "✅ 检测到任务终止信号",
      side: "left",
      kind: "system",
    });
  }
}

async function pollEvents() {
  if (!activeJobId) {
    return;
  }

  try {
    const response = await fetch(`/api/events/${activeJobId}?cursor=${cursor}`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${payload.error || "请求失败"}`);
    }
    
    if (!payload.ok) {
      throw new Error(payload.error || "获取事件失败");
    }

    for (const event of payload.events) {
      renderEvent(event);
    }
    cursor = payload.next_cursor;

    if (payload.status === "success") {
      setStatus("执行完成", "success");
      setResult(JSON.stringify(payload.result, null, 2));
      activeJobId = null;
      return;
    }

    if (payload.status === "error") {
      setStatus("执行失败", "error");
      setResult(`错误：${payload.error || "未知错误"}`);
      activeJobId = null;
      return;
    }
  } catch (error) {
    console.error("轮询错误:", error);
    setStatus("轮询异常，正在重试...", "error");
    setResult(`错误：${error.message}\n(系统将自动重试)`);
    
    if (activeJobId) {
      pollTimer = window.setTimeout(pollEvents, 2000);
    }
    return;
  }

  if (activeJobId) {
    pollTimer = window.setTimeout(pollEvents, 800);
  }
}

taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const task = taskInput.value.trim();
  if (!task) {
    setStatus("任务不能为空", "error");
    return;
  }

  if (activeJobId) {
    setStatus("当前任务执行中，请等待完成后再发送", "running");
    return;
  }

  activateConversationMode();
  setStatus("执行中，请稍候...", "running");
  setResult("正在调用多智能体流程，请稍候...\n");
  clearChat();
  appendBubble({ sender: "User", text: task, side: "right", kind: "user" });
  appendBubble({ sender: "System", text: "任务已提交，正在等待智能体响应...", side: "left", kind: "system" });
  taskInput.value = "";
  cursor = 0;

  if (pollTimer) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task }),
    });

    const payload = await response.json();

    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || "执行失败");
    }

    activeJobId = payload.job_id;
    appendBubble({ sender: "System", text: `任务ID: ${activeJobId}`, side: "left", kind: "system" });
    pollEvents();
  } catch (error) {
    setStatus("执行失败", "error");
    setResult(`错误：${error.message}`);
  }
});
