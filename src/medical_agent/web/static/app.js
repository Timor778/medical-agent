const mermaidReady = import("https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs")
  .then((module) => {
    const mermaid = module.default;
    mermaid.initialize({
      startOnLoad: false,
      theme: "default",
      securityLevel: "loose",
      flowchart: { useMaxWidth: true, htmlLabels: true }
    });
    return mermaid;
  });

const submitBtn = document.getElementById("submitBtn");
const refreshSessionsBtn = document.getElementById("refreshSessionsBtn");
const statusBox = document.getElementById("status");
const answerBox = document.getElementById("answerBox");
const answerText = document.getElementById("answerText");
const metaBox = document.getElementById("meta");
const traceList = document.getElementById("traceList");
const sourceList = document.getElementById("sourceList");
const runtimeMermaid = document.getElementById("runtimeMermaid");
const staticMermaid = document.getElementById("staticMermaid");
const threadInput = document.getElementById("threadId");
const questionInput = document.getElementById("question");
const sessionsStatus = document.getElementById("sessionsStatus");
const sessionsList = document.getElementById("sessionsList");
const sessionTimeline = document.getElementById("sessionTimeline");

const zoomState = { runtime: 1, static: 1 };
let timerHandle = null;
let requestStartedAt = 0;
let currentMetaState = {};
let activeThreadId = threadInput.value.trim() || "web-demo";

function formatElapsed(ms) {
  if (!Number.isFinite(ms) || ms < 0) return "-";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} 秒`;
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalizeMeta(data = {}) {
  return {
    triage_level: data.triage_level || "-",
    intent_summary: data.intent_summary || "-",
    route: data.route || "-",
    rewritten_query: data.rewritten_query || "-",
    search_attempts: Number.isFinite(data.search_attempts) ? data.search_attempts : "-",
    source_count: Array.isArray(data.sources) ? data.sources.length : 0,
    elapsed_ms: Number.isFinite(data.elapsed_ms) ? data.elapsed_ms : null,
    retrieval_mode: data.retrieval_mode || "-",
    llm_provider: data.llm_provider || "-",
    llm_model_id: data.llm_model_id || "-",
  };
}

function renderMeta(data = {}) {
  currentMetaState = { ...currentMetaState, ...data };
  const meta = normalizeMeta(currentMetaState);
  metaBox.innerHTML = `
    <div class="meta-item"><strong>风险等级</strong>${escapeHtml(meta.triage_level)}</div>
    <div class="meta-item"><strong>意图总结</strong>${escapeHtml(meta.intent_summary)}</div>
    <div class="meta-item"><strong>最终路径</strong>${escapeHtml(meta.route)}</div>
    <div class="meta-item"><strong>检索模式</strong>${escapeHtml(meta.retrieval_mode)}</div>
    <div class="meta-item"><strong>模型提供方</strong>${escapeHtml(meta.llm_provider)}</div>
    <div class="meta-item"><strong>搜索词</strong>${escapeHtml(meta.rewritten_query)}</div>
    <div class="meta-item"><strong>当前模型</strong>${escapeHtml(meta.llm_model_id)}</div>
    <div class="meta-item"><strong>搜索次数</strong>${escapeHtml(meta.search_attempts)}</div>
    <div class="meta-item"><strong>来源数量</strong>${escapeHtml(meta.source_count)}</div>
    <div class="meta-item"><strong>推理耗时</strong>${escapeHtml(formatElapsed(meta.elapsed_ms))}</div>
    <div class="meta-item"><strong>会话线程</strong>${escapeHtml(threadInput.value.trim() || "web-demo")}</div>
  `;
}

function renderTrace(steps = []) {
  if (!steps.length) {
    traceList.innerHTML = "<div class='trace-item'>暂无执行轨迹。</div>";
    return;
  }

  traceList.innerHTML = steps.map((step) => `
    <div class="trace-item">
      <div><strong>步骤</strong>${escapeHtml(step.index)}</div>
      <div><strong>当前节点</strong>${escapeHtml(step.node)}</div>
      <div><strong>节点动作</strong>${escapeHtml(step.summary)}</div>
      <div><strong>选择边</strong>${escapeHtml(step.edge)}</div>
      <div><strong>下一节点</strong>${escapeHtml(step.next_node)}</div>
    </div>
  `).join("");
}

function renderSources(sources = []) {
  if (!sources.length) {
    sourceList.innerHTML = "<li>暂无可用来源</li>";
    return;
  }

  sourceList.innerHTML = sources
    .map((url) => `<li><a href="${url}" target="_blank" rel="noreferrer">${escapeHtml(url)}</a></li>`)
    .join("");
}

function renderSessionTimeline(messages = []) {
  if (!messages.length) {
    sessionTimeline.innerHTML = "<div class='timeline-item'>暂无历史消息。</div>";
    return;
  }

  sessionTimeline.innerHTML = messages.map((message) => `
    <div class="timeline-item">
      <div class="timeline-role">${message.role === "human" ? "用户" : "助手"}</div>
      <div>${escapeHtml(message.content)}</div>
      <div class="timeline-time">${escapeHtml(formatDate(message.created_at))}</div>
    </div>
  `).join("");
}

function renderSessionList(threads = []) {
  if (!threads.length) {
    sessionsList.innerHTML = "<div class='session-item'>暂无历史会话。</div>";
    return;
  }

  sessionsList.innerHTML = threads.map((thread) => `
    <div class="session-item ${thread.thread_id === activeThreadId ? "active" : ""}" data-thread-id="${escapeHtml(thread.thread_id)}">
      <div class="session-item-title">${escapeHtml(thread.thread_id)}</div>
      <div class="session-item-meta">最近更新：${escapeHtml(formatDate(thread.updated_at))}</div>
      <div class="session-item-meta">消息数：${escapeHtml(thread.message_count ?? 0)}</div>
    </div>
  `).join("");

  for (const item of sessionsList.querySelectorAll(".session-item[data-thread-id]")) {
    item.addEventListener("click", async () => {
      const threadId = item.getAttribute("data-thread-id");
      if (!threadId) return;
      activeThreadId = threadId;
      threadInput.value = threadId;
      renderSessionList(threads);
      await loadSessionHistory(threadId);
    });
  }
}

function applyZoom(element, value) {
  element.style.transform = `scale(${value})`;
}

function bindZoom(prefix, element, key) {
  document.getElementById(`${prefix}ZoomIn`).addEventListener("click", () => {
    zoomState[key] = Math.min(zoomState[key] + 0.15, 2.5);
    applyZoom(element, zoomState[key]);
  });

  document.getElementById(`${prefix}ZoomOut`).addEventListener("click", () => {
    zoomState[key] = Math.max(zoomState[key] - 0.15, 0.5);
    applyZoom(element, zoomState[key]);
  });

  document.getElementById(`${prefix}ZoomReset`).addEventListener("click", () => {
    zoomState[key] = 1;
    applyZoom(element, zoomState[key]);
  });
}

async function renderMermaid(element, chart) {
  const mermaid = await mermaidReady;
  const id = "m" + Math.random().toString(36).slice(2);
  const { svg } = await mermaid.render(id, chart);
  element.innerHTML = svg;
  applyZoom(element, element === runtimeMermaid ? zoomState.runtime : zoomState.static);
}

async function loadStaticGraph() {
  try {
    const response = await fetch("/api/graph");
    const chart = await response.text();
    await renderMermaid(staticMermaid, chart);
  } catch (error) {
    staticMermaid.textContent = `静态图加载失败：${error}`;
  }
}

async function loadSessions() {
  sessionsStatus.textContent = "正在加载历史会话...";
  try {
    const response = await fetch("/api/sessions");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const threads = await response.json();
    sessionsStatus.textContent = threads.length ? "点击任意会话可查看历史消息。" : "暂无历史会话。";
    renderSessionList(threads);
    if (activeThreadId) {
      await loadSessionHistory(activeThreadId);
    }
  } catch (error) {
    sessionsStatus.innerHTML = `<span class="warning">历史会话加载失败：${escapeHtml(error)}</span>`;
    renderSessionList([]);
    renderSessionTimeline([]);
  }
}

async function loadSessionHistory(threadId) {
  sessionTimeline.innerHTML = "<div class='timeline-item'>正在加载会话消息...</div>";
  try {
    const response = await fetch(`/api/sessions/${encodeURIComponent(threadId)}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    renderSessionTimeline(payload.messages || []);
  } catch (error) {
    sessionTimeline.innerHTML = `<div class='timeline-item warning'>历史消息加载失败：${escapeHtml(error)}</div>`;
  }
}

function startElapsedTimer() {
  stopElapsedTimer();
  requestStartedAt = Date.now();
  timerHandle = window.setInterval(() => {
    renderMeta({ elapsed_ms: Date.now() - requestStartedAt });
  }, 120);
}

function stopElapsedTimer(finalElapsedMs = null) {
  if (timerHandle) {
    window.clearInterval(timerHandle);
    timerHandle = null;
  }
  if (finalElapsedMs !== null) {
    renderMeta({ elapsed_ms: finalElapsedMs });
  }
}

function resetResultArea() {
  statusBox.textContent = "正在执行医疗问诊流程...";
  answerText.textContent = "";
  currentMetaState = {};
  renderMeta({ elapsed_ms: 0 });
  renderTrace([]);
  renderSources([]);
  answerBox.scrollTop = 0;
}

async function readSseStream(response, handlers) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      handleSseBlock(block, handlers);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) {
    handleSseBlock(buffer, handlers);
  }
}

function handleSseBlock(block, handlers) {
  const lines = block.split("\n");
  let eventName = "message";
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!dataLines.length) return;
  const payload = JSON.parse(dataLines.join("\n"));
  const handler = handlers[eventName];
  if (handler) handler(payload);
}

submitBtn.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  const threadId = threadInput.value.trim() || "web-demo";

  if (!question) {
    statusBox.innerHTML = "<span class='warning'>请先输入医疗问题。</span>";
    return;
  }

  activeThreadId = threadId;
  submitBtn.disabled = true;
  resetResultArea();
  startElapsedTimer();

  try {
    const response = await fetch("/api/consult/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, thread_id: threadId }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}`);
    }

    let finalPayload = null;

    await readSseStream(response, {
      status: (payload) => {
        statusBox.textContent = payload.message || "正在处理中...";
      },
      answer_chunk: (payload) => {
        answerText.textContent += payload.chunk || "";
        answerBox.scrollTop = answerBox.scrollHeight;
      },
      error: (payload) => {
        stopElapsedTimer();
        statusBox.innerHTML = `<span class="warning">${escapeHtml(payload.message || "问诊过程出现异常。")}</span>`;
      },
      done: async (payload) => {
        finalPayload = payload;
        answerText.textContent = payload.answer || answerText.textContent || "暂无回答";
        answerBox.scrollTop = answerBox.scrollHeight;
        statusBox.textContent = "执行完成。";
        renderMeta(payload);
        renderTrace(payload.debug_steps || []);
        renderSources(payload.sources || []);
        await renderMermaid(runtimeMermaid, payload.debug_mermaid || "flowchart LR\nstart_node([无数据]) --> finish_node([结束])");
      },
    });

    if (finalPayload) {
      stopElapsedTimer(finalPayload.elapsed_ms);
      await loadSessions();
      await loadSessionHistory(threadId);
      return;
    }
  } catch (error) {
    stopElapsedTimer();
    statusBox.innerHTML = `<span class="warning">调用失败：${escapeHtml(error)}</span>`;
  } finally {
    submitBtn.disabled = false;
  }
});

refreshSessionsBtn.addEventListener("click", () => {
  loadSessions();
});

threadInput.addEventListener("change", async () => {
  activeThreadId = threadInput.value.trim() || "web-demo";
  await loadSessionHistory(activeThreadId);
});

bindZoom("runtime", runtimeMermaid, "runtime");
bindZoom("static", staticMermaid, "static");
renderMeta();
renderTrace([]);
renderSources([]);
renderSessionTimeline([]);
loadStaticGraph();
loadSessions();
