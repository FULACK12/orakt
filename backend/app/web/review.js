"use strict";

const i18n = window.NewsI18n;
i18n.register({
  zh: {
    "review.eyebrow": "HUMAN-IN-THE-LOOP · 事件去重",
    "review.titleLine1": "把相似报道，",
    "review.titleLine2": "核成同一个事实。",
    "review.description": "对模型无法自动判断的近似事件进行人工复核。每个决定都会留下审计记录，任何操作都不会删除 F 盘冷数据。",
    "review.currentJob": "当前聚类任务",
    "review.readingJob": "正在读取任务…",
    "review.pending": "待复核",
    "review.pendingHelp": "需要你的判断",
    "review.allComparisons": "全部对比",
    "review.allHelp": "被规则阻断的近似组",
    "review.merged": "确认合并",
    "review.mergedHelp": "作为同一事件入库",
    "review.independent": "保持独立",
    "review.independentHelp": "作为不同事件入库",
    "review.ignored": "已忽略",
    "review.ignoredHelp": "仅保留审计记录",
    "review.comparisons": "相似事件对比",
    "review.all": "全部",
    "review.decided": "已处理",
    "review.loading": "正在整理复核证据…",
    "review.emptyTitle": "这个视图里没有待处理项",
    "review.emptyBody": "可以切换到“全部”查看已经完成的复核记录。",
    "review.close": "关闭",
    "review.confirmDecision": "确认复核决定",
    "review.note": "复核备注",
    "review.optional": "可选",
    "review.notePlaceholder": "记录判断依据，便于以后审计…",
    "review.safety": "安全边界",
    "review.safetyBody": "本操作不会删除原始新闻文件或 F 盘冷数据。",
    "review.cancel": "取消",
    "review.confirm": "确认",
    "review.decision.merge": "已确认合并",
    "review.decision.independent": "已保持独立",
    "review.decision.ignored": "已忽略",
    "review.blocker.event_time_too_far_apart": "事件发生时间相距过远",
    "review.blocker.earthquake_magnitude_mismatch": "地震震级不一致",
    "review.blocker.earthquake_location_too_far_apart": "地震坐标相距过远",
    "review.blocker.event_type_mismatch": "事件类型不一致",
    "review.blocker.location_too_far_apart": "地点相距过远",
    "review.blocker.country_mismatch": "发生国家不一致",
    "review.blocker.default": "模型建议人工确认",
    "review.dialog.merge.title": "确认合并为同一事件？",
    "review.dialog.merge.description": "两侧报道会被关联到同一个正式事件。此决定会写入事件库，之后不能在本页面撤销。",
    "review.dialog.merge.button": "确认合并并入库",
    "review.dialog.independent.title": "确认它们是不同事件？",
    "review.dialog.independent.description": "两侧候选会分别作为独立事件写入正式事件库，并保留本次人工判断记录。",
    "review.dialog.independent.button": "保持独立并入库",
    "review.dialog.ignored.title": "忽略这组对比？",
    "review.dialog.ignored.description": "只保存审计记录，不会创建正式事件，也不会改变或删除任何原始新闻。",
    "review.dialog.ignored.button": "确认忽略",
    "review.noJobs": "尚无已完成的聚类任务，请先运行一次全量聚类。",
    "review.jobOption": "任务",
    "review.articles": "篇",
    "review.completedAt": "完成于",
    "review.candidates": "个事件候选",
    "review.similarity": "综合相似度 · 人工复核",
    "review.awaiting": "等待决定",
    "review.savedNote": "备注",
    "review.modelNote": "模型相似度较高，但硬性规则阻止了自动合并。",
    "review.action.ignore": "忽略",
    "review.action.independent": "保持独立",
    "review.action.merge": "确认合并",
    "review.reportA": "报道 A",
    "review.reportB": "报道 B",
    "review.source": "来源",
    "review.eventType": "事件类型",
    "review.publishedAt": "发布时间",
    "review.occurredAt": "事件时间",
    "review.location": "地点",
    "review.confidence": "模型置信度",
    "review.unknown": "未识别",
    "review.notProvided": "未提供",
    "review.openSource": "打开原文 ↗",
    "review.signal.embedding": "语义",
    "review.signal.title": "标题",
    "review.signal.entities": "实体",
    "review.signal.time": "时间",
    "review.signal.location": "地点",
    "review.saving": "正在保存…",
    "review.requestFailed": "请求失败",
  },
  en: {
    "review.eyebrow": "HUMAN-IN-THE-LOOP · EVENT DEDUPLICATION",
    "review.titleLine1": "Similar reports.",
    "review.titleLine2": "One verified fact.",
    "review.description": "Review near-matching events the model could not decide safely. Every decision is audited, and no action deletes cold data from drive F.",
    "review.currentJob": "Clustering job",
    "review.readingJob": "Loading jobs…",
    "review.pending": "Pending",
    "review.pendingHelp": "Waiting for your decision",
    "review.allComparisons": "Comparisons",
    "review.allHelp": "Near matches stopped by rules",
    "review.merged": "Merged",
    "review.mergedHelp": "Published as one event",
    "review.independent": "Independent",
    "review.independentHelp": "Published as separate events",
    "review.ignored": "Ignored",
    "review.ignoredHelp": "Audit record only",
    "review.comparisons": "Near-match comparisons",
    "review.all": "All",
    "review.decided": "Decided",
    "review.loading": "Assembling review evidence…",
    "review.emptyTitle": "Nothing to review in this view",
    "review.emptyBody": "Switch to All to inspect completed review records.",
    "review.close": "Close",
    "review.confirmDecision": "Confirm review decision",
    "review.note": "Review note",
    "review.optional": "optional",
    "review.notePlaceholder": "Record the rationale for future audits…",
    "review.safety": "SAFETY",
    "review.safetyBody": "This action never deletes source articles or cold data on drive F.",
    "review.cancel": "Cancel",
    "review.confirm": "Confirm",
    "review.decision.merge": "Merged",
    "review.decision.independent": "Kept independent",
    "review.decision.ignored": "Ignored",
    "review.blocker.event_time_too_far_apart": "Event times are too far apart",
    "review.blocker.earthquake_magnitude_mismatch": "Earthquake magnitudes differ",
    "review.blocker.earthquake_location_too_far_apart": "Earthquake coordinates are too far apart",
    "review.blocker.event_type_mismatch": "Event types differ",
    "review.blocker.location_too_far_apart": "Locations are too far apart",
    "review.blocker.country_mismatch": "Event countries differ",
    "review.blocker.default": "Human confirmation recommended",
    "review.dialog.merge.title": "Merge as one event?",
    "review.dialog.merge.description": "Both reports will be linked to one canonical event. This writes to the event database and cannot be undone from this screen.",
    "review.dialog.merge.button": "Merge and publish",
    "review.dialog.independent.title": "Confirm separate events?",
    "review.dialog.independent.description": "Both candidates will be persisted as separate canonical events with this decision in the audit log.",
    "review.dialog.independent.button": "Keep separate and publish",
    "review.dialog.ignored.title": "Ignore this comparison?",
    "review.dialog.ignored.description": "Only an audit record is saved. No event is published and no source article is modified or deleted.",
    "review.dialog.ignored.button": "Ignore comparison",
    "review.noJobs": "No completed clustering job is available yet.",
    "review.jobOption": "Job",
    "review.articles": "articles",
    "review.completedAt": "Completed",
    "review.candidates": "event candidates",
    "review.similarity": "COMBINED SIMILARITY · HUMAN REVIEW",
    "review.awaiting": "Awaiting decision",
    "review.savedNote": "Note",
    "review.modelNote": "Similarity is high, but a factual safety rule blocked automatic merging.",
    "review.action.ignore": "Ignore",
    "review.action.independent": "Keep independent",
    "review.action.merge": "Merge",
    "review.reportA": "REPORT A",
    "review.reportB": "REPORT B",
    "review.source": "Source",
    "review.eventType": "Event type",
    "review.publishedAt": "Published",
    "review.occurredAt": "Event time",
    "review.location": "Location",
    "review.confidence": "Model confidence",
    "review.unknown": "Unknown",
    "review.notProvided": "Not provided",
    "review.openSource": "Open source ↗",
    "review.signal.embedding": "Semantic",
    "review.signal.title": "Title",
    "review.signal.entities": "Entities",
    "review.signal.time": "Time",
    "review.signal.location": "Location",
    "review.saving": "Saving…",
    "review.requestFailed": "Request failed",
  },
});

const state = {
  jobs: [],
  queue: null,
  filter: "pending",
  pendingDecision: null,
};

const elements = {
  jobSelect: document.querySelector("#job-select"),
  jobMeta: document.querySelector("#job-meta"),
  list: document.querySelector("#review-list"),
  loading: document.querySelector("#loading"),
  empty: document.querySelector("#empty-state"),
  notice: document.querySelector("#notice"),
  dialog: document.querySelector("#decision-dialog"),
  dialogForm: document.querySelector("#decision-form"),
  dialogTitle: document.querySelector("#dialog-title"),
  dialogDescription: document.querySelector("#dialog-description"),
  dialogConfirm: document.querySelector("#dialog-confirm"),
  dialogClose: document.querySelector("#dialog-close"),
  dialogCancel: document.querySelector("#dialog-cancel"),
  note: document.querySelector("#decision-note"),
};

document.addEventListener("DOMContentLoaded", initialize);
window.addEventListener("news:languagechange", () => {
  renderJobOptions();
  renderJobMeta();
  renderItems();
  if (state.pendingDecision) {
    setDecisionDialogCopy(state.pendingDecision.decision);
  }
});

async function initialize() {
  bindEvents();
  try {
    const payload = await api("/cluster-jobs?limit=100");
    state.jobs = payload.jobs.filter(
      (job) => job.status === "completed" && job.result,
    );
    if (!state.jobs.length) {
      throw new Error(i18n.t("review.noJobs"));
    }
    renderJobOptions();
    const params = new URLSearchParams(window.location.search);
    const requestedJob = Number(params.get("job"));
    const selected = state.jobs.find((job) => job.id === requestedJob)
      || state.jobs[0];
    elements.jobSelect.value = String(selected.id);
    await loadQueue(selected.id);
  } catch (error) {
    showError(error.message);
    elements.loading.hidden = true;
  }
}

function bindEvents() {
  elements.jobSelect.addEventListener("change", async (event) => {
    const jobId = Number(event.target.value);
    const url = new URL(window.location);
    url.searchParams.set("job", String(jobId));
    window.history.replaceState({}, "", url);
    await loadQueue(jobId);
  });

  document.querySelectorAll(".filter").forEach((button) => {
    button.addEventListener("click", () => {
      state.filter = button.dataset.filter;
      document.querySelectorAll(".filter").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      renderItems();
    });
  });

  elements.list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-decision]");
    if (!button) return;
    openDecisionDialog(
      button.dataset.reviewKey,
      button.dataset.decision,
    );
  });

  elements.dialogClose.addEventListener("click", closeDialog);
  elements.dialogCancel.addEventListener("click", closeDialog);
  elements.dialogForm.addEventListener("submit", submitDecision);
}

function renderJobOptions() {
  const selectedValue = elements.jobSelect.value;
  elements.jobSelect.innerHTML = state.jobs.map((job) => {
    const date = formatDate(job.completed_at);
    return `<option value="${job.id}">${i18n.t("review.jobOption")} #${job.id} · ${date} · ${job.total_documents} ${i18n.t("review.articles")}</option>`;
  }).join("");
  if (selectedValue) elements.jobSelect.value = selectedValue;
}

async function loadQueue(jobId) {
  elements.loading.hidden = false;
  elements.empty.hidden = true;
  elements.list.innerHTML = "";
  hideError();
  try {
    state.queue = await api(`/cluster-jobs/${jobId}/review`);
    renderJobMeta();
    updateSummary();
    renderItems();
  } catch (error) {
    showError(error.message);
  } finally {
    elements.loading.hidden = true;
  }
}

function renderJobMeta() {
  if (!state.queue) return;
  const job = state.jobs.find((item) => item.id === state.queue.job_id);
  elements.jobMeta.textContent = job
    ? `${i18n.t("review.completedAt")} ${formatDate(job.completed_at)} · ${job.result.preview.candidate_count} ${i18n.t("review.candidates")}`
    : `${i18n.t("review.jobOption")} #${state.queue.job_id}`;
}

function updateSummary() {
  const summary = state.queue.summary;
  setText("stat-pending", summary.pending);
  setText("stat-total", summary.total);
  setText("stat-merged", summary.merged);
  setText("stat-independent", summary.independent);
  setText("stat-ignored", summary.ignored);
}

function renderItems() {
  if (!state.queue) return;
  const items = state.queue.items.filter((item) => {
    if (state.filter === "pending") return !item.decision;
    if (state.filter === "decided") return Boolean(item.decision);
    return true;
  });
  elements.list.innerHTML = items.map(renderCard).join("");
  elements.empty.hidden = items.length > 0;
}

function renderCard(item) {
  const decision = item.decision?.decision;
  const blocker = i18n.t(
    `review.blocker.${item.blocker}`,
    i18n.t("review.blocker.default"),
  );
  const score = Math.round(item.score * 100);
  const note = item.decision?.note
    ? `<span class="decision-note">${i18n.t("review.savedNote")}：${escapeHtml(item.decision.note)}</span>`
    : `<span class="decision-note">${i18n.t("review.modelNote")}</span>`;
  return `
    <article class="review-card ${decision ? "decided" : ""}">
      <header class="review-head">
        <div class="score-ring" style="--score:${score}%">${score}%</div>
        <div>
          <p class="review-label">${i18n.t("review.similarity")}</p>
          <p class="blocker">
            ${escapeHtml(blocker)}
            <small class="blocker-code">${escapeHtml(item.blocker || "no_hard_blocker")}</small>
          </p>
        </div>
        <span class="decision-badge ${decision || ""}">
          ${decision ? i18n.t(`review.decision.${decision}`) : i18n.t("review.awaiting")}
        </span>
      </header>
      <div class="comparison">
        ${renderCandidate(item.left, i18n.t("review.reportA"))}
        <div class="divider"></div>
        ${renderCandidate(item.right, i18n.t("review.reportB"))}
      </div>
      <div class="signals">
        ${renderSignal(i18n.t("review.signal.embedding"), item.signals.embedding)}
        ${renderSignal(i18n.t("review.signal.title"), item.signals.title)}
        ${renderSignal(i18n.t("review.signal.entities"), item.signals.entities)}
        ${renderSignal(i18n.t("review.signal.time"), item.signals.time)}
        ${renderSignal(i18n.t("review.signal.location"), item.signals.location)}
      </div>
      <footer class="review-actions">
        ${note}
        ${decision ? "" : `
          <button class="action-button ignore" data-review-key="${item.review_key}" data-decision="ignored">
            ${i18n.t("review.action.ignore")}
          </button>
          <button class="action-button independent" data-review-key="${item.review_key}" data-decision="independent">
            ${i18n.t("review.action.independent")}
          </button>
          <button class="action-button merge" data-review-key="${item.review_key}" data-decision="merge">
            ${i18n.t("review.action.merge")}
          </button>
        `}
      </footer>
    </article>
  `;
}

function renderCandidate(side, label) {
  const candidate = side.candidate;
  const event = candidate.event;
  const document = side.document;
  const location = event.location?.name || i18n.t("review.unknown");
  return `
    <section class="candidate">
      <div class="candidate-side">
        <span>${label}</span>
        <small>DOC ${document.document_id} · CLUSTER ${side.cluster_id}</small>
      </div>
      <h3>${escapeHtml(document.title)}</h3>
      <p class="candidate-summary">${escapeHtml(event.summary)}</p>
      <dl class="metadata">
        <div>
          <dt>${i18n.t("review.source")}</dt>
          <dd title="${escapeHtml(document.source_name)}">${escapeHtml(document.source_name)}</dd>
        </div>
        <div>
          <dt>${i18n.t("review.eventType")}</dt>
          <dd>${escapeHtml(event.event_type)}</dd>
        </div>
        <div>
          <dt>${i18n.t("review.publishedAt")}</dt>
          <dd>${formatDate(document.published_at)}</dd>
        </div>
        <div>
          <dt>${i18n.t("review.occurredAt")}</dt>
          <dd>${formatDate(event.occurred_at)}</dd>
        </div>
        <div>
          <dt>${i18n.t("review.location")}</dt>
          <dd title="${escapeHtml(location)}">${escapeHtml(location)}</dd>
        </div>
        <div>
          <dt>${i18n.t("review.confidence")}</dt>
          <dd>${Math.round(event.confidence * 100)}%</dd>
        </div>
      </dl>
      <a class="source-link" href="${escapeAttribute(document.url)}" target="_blank" rel="noreferrer">
        ${i18n.t("review.openSource")}
      </a>
    </section>
  `;
}

function renderSignal(label, value) {
  const normalized = value == null ? null : Math.round(value * 100);
  return `
    <div class="signal">
      <div class="signal-label">
        <span>${label}</span>
        <strong>${normalized == null ? "—" : `${normalized}%`}</strong>
      </div>
      <div class="signal-track">
        <div class="signal-value" style="width:${normalized || 0}%"></div>
      </div>
    </div>
  `;
}

function openDecisionDialog(reviewKey, decision) {
  state.pendingDecision = { reviewKey, decision };
  setDecisionDialogCopy(decision);
  elements.note.value = "";
  elements.dialog.showModal();
  elements.note.focus();
}

function setDecisionDialogCopy(decision) {
  elements.dialogTitle.textContent = i18n.t(`review.dialog.${decision}.title`);
  elements.dialogDescription.textContent = i18n.t(
    `review.dialog.${decision}.description`,
  );
  elements.dialogConfirm.textContent = i18n.t(
    `review.dialog.${decision}.button`,
  );
  elements.dialogConfirm.className = `button ${decision}`;
}

function closeDialog() {
  state.pendingDecision = null;
  elements.dialog.close();
}

async function submitDecision(event) {
  event.preventDefault();
  if (!state.pendingDecision || !state.queue) return;
  const { reviewKey, decision } = state.pendingDecision;
  elements.dialogConfirm.disabled = true;
  elements.dialogConfirm.textContent = i18n.t("review.saving");
  hideError();
  try {
    await api(
      `/cluster-jobs/${state.queue.job_id}/review/${reviewKey}`,
      {
        method: "POST",
        body: JSON.stringify({
          decision,
          note: elements.note.value.trim() || null,
          confirm_merge: decision === "merge",
        }),
      },
    );
    closeDialog();
    await loadQueue(state.queue.job_id);
  } catch (error) {
    showError(error.message);
  } finally {
    elements.dialogConfirm.disabled = false;
    if (state.pendingDecision) setDecisionDialogCopy(decision);
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = `${i18n.t("review.requestFailed")} (${response.status})`;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string"
        ? payload.detail
        : JSON.stringify(payload.detail);
    } catch {
      // Keep the status-based message.
    }
    throw new Error(detail);
  }
  return response.json();
}

function formatDate(value) {
  if (!value) return i18n.t("review.notProvided");
  return new Intl.DateTimeFormat(
    i18n.language === "zh" ? "zh-CN" : "en-CA",
    {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    },
  ).format(new Date(value));
}

function setText(id, value) {
  document.querySelector(`#${id}`).textContent = String(value);
}

function showError(message) {
  elements.notice.textContent = message;
  elements.notice.hidden = false;
}

function hideError() {
  elements.notice.hidden = true;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  const text = String(value ?? "");
  if (!/^https?:\/\//i.test(text)) return "#";
  return escapeHtml(text);
}
