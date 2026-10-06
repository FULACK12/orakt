"use strict";

const state = {
  language: localStorage.getItem("news-task-language") || "zh",
  filter: "active",
  tasks: [],
  pendingCancel: null,
  timer: null,
  controllerTimer: null,
  loading: false,
  controlling: false,
  checkpoints: {},
  expandedCheckpoints: new Set(),
};

const elements = {
  notice: document.querySelector("#notice"),
  list: document.querySelector("#task-list"),
  visibleCount: document.querySelector("#visible-count"),
  snapshotTime: document.querySelector("#snapshot-time"),
  refreshState: document.querySelector("#refresh-state"),
  liveState: document.querySelector("#live-state"),
  runtimeTitle: document.querySelector("#runtime-title"),
  runtimeCopy: document.querySelector("#runtime-copy"),
  dialog: document.querySelector("#cancel-dialog"),
  cancelName: document.querySelector("#cancel-task-name"),
  cancelConfirm: document.querySelector("#cancel-confirm"),
  controllerState: document.querySelector("#controller-state"),
  serviceCount: document.querySelector("#service-count"),
  serviceOperation: document.querySelector("#service-operation"),
  startAll: document.querySelector("#start-all"),
  stopAll: document.querySelector("#stop-all"),
};

const labels = {
  zh: {
    connected: "本地实时连接",
    refresh: "每 2 秒自动刷新",
    paused: "页面在后台，已降低刷新频率",
    busy: "本地模型正在执行任务",
    busyCopy: "任务按单模型串行运行；排队任务不会同时占用显存。",
    idle: "当前没有运行中的模型任务",
    idleCopy: "队列仍会保留，后台工作器将在资源可用时自动接管。",
    visible: count => `显示 ${count} 个任务`,
    empty: "当前筛选条件下没有任务。",
    report: "公司报告",
    cluster: "新闻聚类",
    stop: "安全停止",
    queue: position => `队列第 ${position} 位`,
    elapsed: "耗时",
    heartbeat: "心跳",
    noProgress: "距上次进展",
    stalled: "可能卡住，防卡死计时中",
    details: "查看任务细节",
    checkpoints: "查看阶段检查点",
    checkpointsLoading: "正在读取检查点…",
    checkpointsEmpty: "尚未保存阶段检查点。",
    resumable: "可从最近安全检查点恢复",
    notResumable: "当前没有可恢复快照",
    retry: (attempt, maximum) => `尝试 ${attempt}/${maximum}`,
    attempt: count => `第 ${count} 次尝试`,
    states: { queued: "排队", running: "运行中", cancelling: "正在停止", cancelled: "已安全停止", skipped: "已跳过重复", completed: "已完成", failed: "失败" },
    stages: { queued: "等待资源", acquiring_model: "申请本地模型", waiting_for_model: "等待本地模型", retrying_same_snapshot: "复用原快照重试", recovered_after_restart: "重启后恢复排队", checkpoint_restored: "从检查点恢复", watchdog_requeued: "防卡死自动重排", watchdog_failed: "防卡死已停止", yielded_to_report: "已保存进度并主动让出模型（非取消）", analyzing_documents: "逐篇理解新闻", embedding_events: "生成事件向量", global_clustering: "全局事件聚类", signing_preview: "整理聚类结果", persisting_cluster_result: "保存聚类索引", building_event_chain: "构建事件链", generating_logic_chain: "生成并验证逻辑链", cancellation_watchdog: "停止超时恢复", preparing_evidence: "整理证据", evidence_company: "公司财报与供应链", evidence_history: "历史研究时间窗", evidence_news: "新闻全文与公告", evidence_events: "事件与地理证据", evidence_macro: "宏观与能源数据", evidence_market: "行情与流动性", evidence_financials: "季度财报与可比公司", evidence_context: "周期、冲突与覆盖率", evidence_snapshot_ready: "证据快照", targeted_retrieval: "定向检索", targeted_retrieval_complete: "定向证据已保存", question_planning: "选择研究问题", local_draft: "模型初稿", local_draft_complete: "初稿完成", local_episode_repair: "历史区间证据修复", bridge_evidence_completion: "补全传导证据", evidence_gap_search: "反查证据缺口", local_evidence_revision: "证据修订", local_evidence_revision_complete: "证据修订完成", factor_mining: "因子检验", factor_mining_complete: "因子检验已保存", deterministic_audit: "确定性报告审计", deterministic_audit_complete: "最终审计已保存", local_report_audit: "报告审计", clustering: "文档分析与聚类", cancelling: "等待安全检查点", completed: "已完成", failed: "失败", cancelled: "已停止", duplicate_suppressed: "重复任务已跳过" },
    cancelSent: "停止请求已记录；任务会在安全检查点结束。",
    cancelledNow: "排队任务已安全停止。",
    cancelFailed: "停止请求失败",
    fetchFailed: "无法读取实时任务状态；保留最后一次快照。",
    controllerOnline: "本机控制器在线",
    controllerOffline: "本机控制器离线，请从桌面快捷方式启动一次 NEWS Map",
    servicesRunning: (running, total, ai) => `${running}/${total} 个容器正在运行 · 本地 AI ${ai === "online" ? "在线" : "离线"}`,
    serviceIdle: "当前没有启停操作",
    startConfirm: "确认启动 NEWS Map 所需的全部服务？",
    stopConfirm: "确认安全关闭全部 NEWS Map 容器？运行任务会收到停止信号，数据库、报告和模型不会删除。",
    operationAccepted: "操作已接收，可在此查看实时状态。",
    operationFailed: "本机启停操作失败",
  },
  en: {
    connected: "Local live connection",
    refresh: "Refreshes every 2 seconds",
    paused: "Background tab; refresh rate reduced",
    busy: "The local model is processing a task",
    busyCopy: "Tasks run serially on one model; queued work does not consume VRAM concurrently.",
    idle: "No model task is currently running",
    idleCopy: "Queued work is retained and will resume when the runtime is available.",
    visible: count => `${count} tasks shown`,
    empty: "No tasks match this filter.",
    report: "Company report",
    cluster: "News clustering",
    stop: "Safe stop",
    queue: position => `Queue position ${position}`,
    elapsed: "Elapsed",
    heartbeat: "Heartbeat",
    noProgress: "No progress for",
    stalled: "Possibly stalled; watchdog is active",
    details: "Inspect task details",
    checkpoints: "Inspect stage checkpoints",
    checkpointsLoading: "Loading checkpoints…",
    checkpointsEmpty: "No stage checkpoint has been saved yet.",
    resumable: "Resumable from the latest safe checkpoint",
    notResumable: "No resumable snapshot is available",
    retry: (attempt, maximum) => `Attempt ${attempt}/${maximum}`,
    attempt: count => `Attempt ${count}`,
    states: { queued: "Queued", running: "Running", cancelling: "Stopping", cancelled: "Cancelled", skipped: "Duplicate skipped", completed: "Completed", failed: "Failed" },
    stages: { queued: "Waiting", acquiring_model: "Acquiring local model", waiting_for_model: "Waiting for local model", retrying_same_snapshot: "Reusing the original snapshot", recovered_after_restart: "Recovered after restart", checkpoint_restored: "Restored from checkpoint", watchdog_requeued: "Watchdog requeued", watchdog_failed: "Watchdog stopped task", yielded_to_report: "Progress saved; yielding to a report (not cancelled)", analyzing_documents: "Understanding documents", embedding_events: "Embedding events", global_clustering: "Global clustering", signing_preview: "Preparing cluster result", persisting_cluster_result: "Persisting cluster index", building_event_chain: "Building event chain", generating_logic_chain: "Generating and validating logic", cancellation_watchdog: "Cancellation recovery", preparing_evidence: "Preparing evidence", evidence_company: "Company filings and supply chain", evidence_history: "Historical research window", evidence_news: "News full text and filings", evidence_events: "Events and geography", evidence_macro: "Macro and energy data", evidence_market: "Markets and liquidity", evidence_financials: "Quarterly and peer financials", evidence_context: "Cycles, conflicts and coverage", evidence_snapshot_ready: "Evidence snapshot", targeted_retrieval: "Targeted retrieval", targeted_retrieval_complete: "Targeted evidence saved", question_planning: "Planning question", local_draft: "Local draft", local_draft_complete: "Draft complete", local_episode_repair: "Historical-window evidence repair", bridge_evidence_completion: "Completing bridge evidence", evidence_gap_search: "Searching evidence gaps", local_evidence_revision: "Evidence revision", local_evidence_revision_complete: "Revision complete", factor_mining: "Factor tests", factor_mining_complete: "Factor tests saved", deterministic_audit: "Deterministic audit", deterministic_audit_complete: "Final audit saved", local_report_audit: "Report audit", clustering: "Analysis and clustering", cancelling: "Waiting for safe checkpoint", completed: "Completed", failed: "Failed", cancelled: "Cancelled", duplicate_suppressed: "Duplicate skipped" },
    cancelSent: "Cancellation was recorded and will complete at a safe checkpoint.",
    cancelledNow: "The queued task was safely cancelled.",
    cancelFailed: "Cancellation failed",
    fetchFailed: "Live task status is unavailable; showing the last snapshot.",
    controllerOnline: "Local controller online",
    controllerOffline: "Local controller offline. Start NEWS Map once from the desktop shortcut.",
    servicesRunning: (running, total, ai) => `${running}/${total} containers running · local AI ${ai === "online" ? "online" : "offline"}`,
    serviceIdle: "No service operation is active",
    startConfirm: "Start every service required by NEWS Map?",
    stopConfirm: "Safely stop all NEWS Map containers? Running work will receive a stop signal; databases, reports and models are preserved.",
    operationAccepted: "Operation accepted. Progress is shown here.",
    operationFailed: "Local service operation failed",
  },
};

function t() { return labels[state.language]; }

function applyLanguage() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-zh]").forEach(node => {
    node.textContent = node.dataset[state.language];
  });
  document.querySelector("#language-toggle").textContent = state.language === "zh" ? "EN" : "中";
  localStorage.setItem("news-task-language", state.language);
  renderTasks();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDuration(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const secs = value % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

function formatTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(state.language === "zh" ? "zh-CN" : "en-CA", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(new Date(value));
}

function filteredTasks() {
  if (state.filter === "active") {
    return state.tasks.filter(task => ["queued", "running", "cancelling"].includes(task.state));
  }
  if (state.filter === "research") return state.tasks.filter(task => task.kind === "research_batch_item");
  if (state.filter === "cluster") return state.tasks.filter(task => task.kind === "cluster_job");
  return state.tasks;
}

function checkpointMarkup(task) {
  if (task.kind !== "research_batch_item") return "";
  const expanded = state.expandedCheckpoints.has(task.key);
  const payload = state.checkpoints[task.task_id];
  let body = "";
  if (expanded && payload === "loading") {
    body = `<p class="checkpoint-empty">${escapeHtml(t().checkpointsLoading)}</p>`;
  } else if (expanded && payload) {
    const entries = payload.entries || [];
    body = entries.length
      ? `<div class="checkpoint-list">${entries.map(entry => `
          <article>
            <header><strong>${escapeHtml(t().stages[entry.stage] || entry.stage)}</strong><span>${Number(entry.percent).toFixed(0)}%</span></header>
            <small>${escapeHtml(formatTime(entry.saved_at))} · ${escapeHtml(t().attempt(entry.attempt_count))}</small>
            <pre>${escapeHtml(JSON.stringify(entry.summary || {}, null, 2))}</pre>
          </article>`).join("")}</div>`
      : `<p class="checkpoint-empty">${escapeHtml(t().checkpointsEmpty)}</p>`;
    body = `<p class="checkpoint-resume ${payload.resumable ? "ready" : ""}">${escapeHtml(payload.resumable ? t().resumable : t().notResumable)}</p>${body}`;
  }
  return `
    <div class="checkpoint-panel ${expanded ? "expanded" : ""}">
      <button class="checkpoint-toggle" type="button" data-task-id="${task.task_id}" data-task-key="${escapeHtml(task.key)}">${escapeHtml(t().checkpoints)}</button>
      ${expanded ? body : ""}
    </div>`;
}

function renderTasks() {
  if (!elements.list) return;
  const visible = filteredTasks();
  elements.visibleCount.textContent = t().visible(visible.length);
  if (!visible.length) {
    elements.list.innerHTML = `<div class="empty-state">${escapeHtml(t().empty)}</div>`;
    return;
  }
  elements.list.innerHTML = visible.map(task => {
    const detail = task.details || {};
    const stalled = ["running", "cancelling"].includes(task.state)
      && Number(task.stale_seconds || 0) > Number(task.watchdog_threshold_seconds || 900);
    const queue = task.queue_position ? `<span>${escapeHtml(t().queue(task.queue_position))}</span>` : "";
    const attempt = task.kind === "research_batch_item" ? `<span>${escapeHtml(t().attempt(detail.attempt_count || 0))}</span>` : "";
    const heartbeat = task.heartbeat_at ? `<span>${escapeHtml(t().heartbeat)} ${escapeHtml(formatTime(task.heartbeat_at))}</span>` : "";
    const noProgress = task.stale_seconds == null ? "" : `<span class="${stalled ? "stalled" : ""}">${escapeHtml(t().noProgress)} ${escapeHtml(formatDuration(task.stale_seconds))}</span>`;
    const retry = detail.max_attempts
      ? `<span>${escapeHtml(t().retry(detail.attempt_count || 0, detail.max_attempts))}</span>`
      : "";
    const detailRows = Object.entries(detail)
      .filter(([, value]) => value !== null && value !== undefined && value !== "")
      .map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(typeof value === "object" ? JSON.stringify(value) : value)}</dd></div>`)
      .join("");
    const action = task.can_cancel
      ? `<button class="button danger task-cancel" type="button" data-task-key="${escapeHtml(task.key)}">${escapeHtml(t().stop)}</button>`
      : `<span class="state-badge">${escapeHtml(t().states[task.state] || task.state)}</span>`;
    return `
      <article class="task-card" data-state="${escapeHtml(task.state)}">
        <div class="task-identity">
          <div class="task-title-line">
            <span class="kind-badge">${escapeHtml(task.kind === "research_batch_item" ? t().report : t().cluster)}</span>
            <h3>${escapeHtml(task.title)}</h3>
          </div>
          <p>${escapeHtml(task.subtitle)}</p>
          <div class="task-meta">
            <span>${escapeHtml(t().states[task.state] || task.state)}</span>
            ${queue}${attempt}${retry}<span>${escapeHtml(t().elapsed)} ${escapeHtml(formatDuration(task.elapsed_seconds))}</span>${heartbeat}${noProgress}
          </div>
        </div>
        <div class="task-progress">
          <div class="progress-head">
            <strong>${escapeHtml(t().stages[task.stage] || task.stage)}</strong>
            <span>${Number(task.progress_percent).toFixed(0)}%</span>
          </div>
          <div class="progress-track"><i style="width:${Math.max(0, Math.min(100, Number(task.progress_percent)))}%"></i></div>
          <p class="task-message">${escapeHtml(task.message || "—")}</p>
          ${stalled ? `<p class="stall-warning">${escapeHtml(t().stalled)}</p>` : ""}
          <details class="task-detail"><summary>${escapeHtml(t().details)}</summary><dl>${detailRows}</dl></details>
          ${checkpointMarkup(task)}
        </div>
        <div class="task-actions">
          <small>${escapeHtml(task.key)}</small>
          ${action}
        </div>
      </article>`;
  }).join("");
  elements.list.querySelectorAll(".task-cancel").forEach(button => {
    button.addEventListener("click", () => openCancelDialog(button.dataset.taskKey));
  });
  elements.list.querySelectorAll(".checkpoint-toggle").forEach(button => {
    button.addEventListener("click", () => toggleCheckpoints(button.dataset.taskKey, Number(button.dataset.taskId)));
  });
}

async function toggleCheckpoints(taskKey, taskId) {
  if (state.expandedCheckpoints.has(taskKey)) {
    state.expandedCheckpoints.delete(taskKey);
    renderTasks();
    return;
  }
  state.expandedCheckpoints.add(taskKey);
  if (!state.checkpoints[taskId]) {
    state.checkpoints[taskId] = "loading";
    renderTasks();
    try {
      const response = await fetch(`/operations/tasks/research_batch_item/${taskId}/checkpoints`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.checkpoints[taskId] = await response.json();
    } catch (error) {
      state.checkpoints[taskId] = { resumable: false, entries: [], error: error.message };
    }
  }
  renderTasks();
}

function renderSnapshot(payload) {
  state.tasks = payload.tasks || [];
  const summary = payload.summary;
  ["running", "queued", "cancelling", "cancelled", "skipped", "completed", "failed"].forEach(key => {
    document.querySelector(`#count-${key}`).textContent = summary[key] ?? 0;
  });
  elements.snapshotTime.textContent = formatTime(payload.generated_at);
  elements.refreshState.textContent = document.hidden ? t().paused : t().refresh;
  elements.liveState.className = "system-state live";
  elements.liveState.querySelector("span").textContent = t().connected;
  const copy = document.querySelector(".control-copy");
  copy.classList.toggle("is-busy", Boolean(summary.model_busy));
  elements.runtimeTitle.textContent = summary.model_busy ? t().busy : t().idle;
  elements.runtimeCopy.textContent = summary.model_busy ? t().busyCopy : t().idleCopy;
  renderTasks();
}

async function refreshTasks() {
  if (state.loading) return;
  state.loading = true;
  try {
    const response = await fetch("/operations/tasks?limit=160", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderSnapshot(await response.json());
    elements.notice.hidden = true;
  } catch (error) {
    elements.liveState.className = "system-state error";
    elements.liveState.querySelector("span").textContent = "Offline";
    elements.notice.textContent = `${t().fetchFailed} ${error.message}`;
    elements.notice.hidden = false;
  } finally {
    state.loading = false;
    clearTimeout(state.timer);
    state.timer = setTimeout(refreshTasks, document.hidden ? 8000 : 2000);
  }
}

function renderController(payload) {
  const operation = payload.operation || {};
  const busy = ["accepted", "running"].includes(operation.state);
  elements.controllerState.className = "controller-state online";
  elements.controllerState.querySelector("span").textContent = t().controllerOnline;
  elements.serviceCount.textContent = t().servicesRunning(
    payload.running_services || 0,
    payload.known_services || 0,
    payload.local_ai?.state || "unknown",
  );
  elements.serviceOperation.textContent = operation.message || t().serviceIdle;
  elements.startAll.disabled = busy;
  elements.stopAll.disabled = busy;
}

async function refreshController() {
  try {
    const response = await fetch("http://127.0.0.1:8765/status", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderController(await response.json());
  } catch (error) {
    elements.controllerState.className = "controller-state offline";
    elements.controllerState.querySelector("span").textContent = t().controllerOffline;
    elements.serviceCount.textContent = "—";
    elements.serviceOperation.textContent = error.message;
    elements.startAll.disabled = true;
    elements.stopAll.disabled = true;
  } finally {
    clearTimeout(state.controllerTimer);
    state.controllerTimer = setTimeout(refreshController, 2000);
  }
}

async function controlServices(action) {
  if (state.controlling) return;
  const confirmationText = action === "start" ? t().startConfirm : t().stopConfirm;
  if (!window.confirm(confirmationText)) return;
  state.controlling = true;
  elements.startAll.disabled = true;
  elements.stopAll.disabled = true;
  try {
    const response = await fetch(`http://127.0.0.1:8765/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation: action === "start" ? "START NEWS MAP" : "STOP NEWS MAP" }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    elements.notice.textContent = t().operationAccepted;
    elements.notice.hidden = false;
    await refreshController();
  } catch (error) {
    elements.notice.textContent = `${t().operationFailed}: ${error.message}`;
    elements.notice.hidden = false;
  } finally {
    state.controlling = false;
  }
}

function openCancelDialog(key) {
  const task = state.tasks.find(item => item.key === key);
  if (!task) return;
  state.pendingCancel = task;
  elements.cancelName.textContent = `${task.title} · ${task.key}`;
  elements.dialog.showModal();
}

async function confirmCancel() {
  const task = state.pendingCancel;
  if (!task) return;
  elements.cancelConfirm.disabled = true;
  try {
    const response = await fetch(`/operations/tasks/${task.kind}/${task.task_id}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation: task.key }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    elements.dialog.close();
    elements.notice.textContent = payload.safe_checkpoint ? t().cancelledNow : t().cancelSent;
    elements.notice.hidden = false;
    await refreshTasks();
  } catch (error) {
    elements.notice.textContent = `${t().cancelFailed}: ${error.message}`;
    elements.notice.hidden = false;
    elements.dialog.close();
  } finally {
    elements.cancelConfirm.disabled = false;
    state.pendingCancel = null;
  }
}

document.querySelector("#language-toggle").addEventListener("click", () => {
  state.language = state.language === "zh" ? "en" : "zh";
  applyLanguage();
});
document.querySelectorAll("[data-filter]").forEach(button => {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach(item => item.classList.toggle("active", item === button));
    renderTasks();
  });
});
elements.cancelConfirm.addEventListener("click", confirmCancel);
elements.startAll.addEventListener("click", () => controlServices("start"));
elements.stopAll.addEventListener("click", () => controlServices("stop"));
elements.dialog.addEventListener("close", () => { state.pendingCancel = null; });
document.addEventListener("visibilitychange", () => {
  elements.refreshState.textContent = document.hidden ? t().paused : t().refresh;
  clearTimeout(state.timer);
  state.timer = setTimeout(refreshTasks, document.hidden ? 8000 : 250);
});

applyLanguage();
refreshTasks();
refreshController();
