(() => {
  "use strict";

  const state = {
    data: null,
    view: "jobs",
    search: "",
    source: "all",
    status: "all",
    appSearch: "",
    appTier: "all",
    appStatus: "all",
  };
  let browserRequest = 0;
  let hlsPlayer = null;
  let hlsPromise = null;
  const $ = (id) => document.getElementById(id);

  $("wordmark").addEventListener("click", (event) => {
    event.preventDefault();
    setView("jobs");
  });
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });
  $("refresh").addEventListener("click", load);
  $("filters").addEventListener("submit", (event) => event.preventDefault());
  $("search").addEventListener("input", (event) => {
    state.search = event.target.value.toLowerCase().trim();
    renderJobs();
  });
  $("source").addEventListener("change", (event) => {
    state.source = event.target.value;
    renderJobs();
  });
  $("status").addEventListener("change", (event) => {
    state.status = event.target.value;
    renderJobs();
  });
  $("clear").addEventListener("click", () => {
    state.search = "";
    state.source = "all";
    state.status = "all";
    $("search").value = "";
    $("source").value = "all";
    $("status").value = "all";
    renderJobs();
  });
  $("app-filters").addEventListener("submit", (event) => event.preventDefault());
  $("app-search").addEventListener("input", (event) => {
    state.appSearch = event.target.value.toLowerCase().trim();
    renderApps();
  });
  $("app-tier").addEventListener("change", (event) => {
    state.appTier = event.target.value;
    renderApps();
  });
  $("app-status").addEventListener("change", (event) => {
    state.appStatus = event.target.value;
    renderApps();
  });
  $("app-clear").addEventListener("click", () => {
    state.appSearch = "";
    state.appTier = "all";
    state.appStatus = "all";
    $("app-search").value = "";
    $("app-tier").value = "all";
    $("app-status").value = "all";
    renderApps();
  });
  $("close-dialog").addEventListener("click", () => $("job-dialog").close());
  $("job-dialog").addEventListener("click", (event) => {
    if (event.target === $("job-dialog")) $("job-dialog").close();
  });
  window.addEventListener("hashchange", () => {
    const next = window.location.hash.slice(1);
    if (next === "jobs" || next === "apps") setView(next, false);
  });

  const initialView = window.location.hash.slice(1);
  setView(initialView === "apps" ? "apps" : "jobs", false);
  load();

  async function load() {
    setConnection("syncing", "");
    try {
      const response = await fetch("/api/dashboard?limit=100", { cache: "no-store" });
      if (!response.ok) throw new Error("request failed: " + response.status);
      state.data = await response.json();
      render();
      setConnection("live", "live");
    } catch (error) {
      setConnection("offline", "error");
      $("jobs-list").replaceChildren(emptyMessage("start with job-agent web"));
      $("apps-list").replaceChildren(emptyMessage("no applications"));
      console.error(error);
    }
  }

  function render() {
    const { stats } = state.data;
    setText("jobs-total", stats.jobs_total);
    setText("jobs-evaluated", stats.evaluated_jobs);
    setText("apps-needs-user", stats.needs_user);
    setText("apps-total", stats.applications_total);
    setText("synced", formatDateTime(state.data.generated_at));
    renderSources();
    renderAppStatuses();
    renderJobs();
    renderApps();
  }

  function renderSources() {
    const select = $("source");
    const current = state.source;
    select.replaceChildren(option("all", "all sources"));
    Object.keys(state.data.sources).sort().forEach((source) => {
      select.appendChild(option(source, displaySource(source)));
    });
    select.value = Object.prototype.hasOwnProperty.call(state.data.sources, current) ? current : "all";
    state.source = select.value;
  }

  function renderJobs() {
    if (!state.data) return;
    const jobs = state.data.jobs.filter((job) => {
      const text = [job.company, job.title, job.location, job.source].join(" ").toLowerCase();
      const sourceOk = state.source === "all" || job.source === state.source;
      const statusOk =
        state.status === "all" ||
        job.status === state.status ||
        (state.status === "evaluated" && job.fit_score !== null);
      return sourceOk && statusOk && (!state.search || text.includes(state.search));
    });

    setText("result-count", jobs.length + " / " + state.data.stats.jobs_total);
    const list = $("jobs-list");
    list.replaceChildren();
    if (!jobs.length) {
      list.appendChild(emptyMessage("no jobs"));
      return;
    }
    jobs.forEach((job) => list.appendChild(jobEntry(job)));
  }

  function renderApps() {
    if (!state.data) return;
    const applications = state.data.applications.filter((application) => {
      const text = [application.company, application.title].join(" ").toLowerCase();
      const searchOk = !state.appSearch || text.includes(state.appSearch);
      const tierOk = state.appTier === "all" || application.tier === state.appTier;
      const statusOk = state.appStatus === "all" || application.status === state.appStatus;
      return searchOk && tierOk && statusOk;
    });

    setText("apps-result-count", applications.length + " / " + state.data.stats.applications_total);
    const list = $("apps-list");
    list.replaceChildren();
    if (!applications.length) {
      list.appendChild(emptyMessage("no applications"));
      return;
    }
    applications.forEach((application) => {
      list.appendChild(applicationEntry(application));
    });
  }

  function renderAppStatuses() {
    const select = $("app-status");
    const current = state.appStatus;
    const statuses = [...new Set(state.data.applications.map((application) => application.status).filter(Boolean))].sort();
    select.replaceChildren(option("all", "all states"));
    statuses.forEach((status) => select.appendChild(option(status, formatState(status))));
    select.value = statuses.includes(current) ? current : "all";
    state.appStatus = select.value;
  }

  function jobEntry(job) {
    const entry = document.createElement("article");
    entry.className = "entry";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "entry-button";
    button.setAttribute("aria-label", job.company + ": " + job.title);
    button.append(
      entryText("entry-company", job.company || "—", displaySource(job.source)),
      entryText("entry-title", job.title || "—"),
      entryText("entry-location", job.location || "—"),
      entryText("entry-meta", jobMeta(job))
    );
    button.addEventListener("click", () => openJob(job.id));
    entry.appendChild(button);
    return entry;
  }

  function applicationEntry(application) {
    const entry = document.createElement("article");
    entry.className = "entry";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "entry-button";
    button.append(
      entryText("entry-company", application.company || "—"),
      entryText("entry-title", application.title || "—"),
      entryText("entry-location", formatTier(application.tier)),
      entryText(
        "entry-meta",
        [formatState(application.status), application.resume_id || "no resume", formatDate(application.last_updated_at)].join(" · ")
      )
    );
    button.addEventListener("click", () => openJob(application.job_id));
    entry.appendChild(button);
    return entry;
  }

  async function openJob(id) {
    const dialog = $("job-dialog");
    setText("dialog-title", "loading…");
    setText("dialog-company", "");
    $("dialog-meta").replaceChildren();
    $("assessment-list").replaceChildren();
    $("description-content").replaceChildren(emptyMessage("loading…"));
    resetBrowserPanel();
    if (dialog.showModal) dialog.showModal();
    try {
      const response = await fetch("/api/jobs/" + encodeURIComponent(id), { cache: "no-store" });
      if (!response.ok) throw new Error("request failed: " + response.status);
      showJob(await response.json());
    } catch (error) {
      setText("dialog-title", "unavailable");
      setText("dialog-summary", error.message);
    }
  }

  function showJob(payload) {
    const job = payload.job;
    const evaluation = payload.evaluation;
    setText("dialog-title", job.title);
    setText("dialog-company", job.company);
    $("dialog-meta").replaceChildren(
      detail("source", displaySource(job.source)),
      detail("location", job.location || "—"),
      detail("fit", evaluation ? number(evaluation.fit_score) : "—"),
      detail("tier", evaluation ? formatTier(evaluation.tier) : "—"),
      detail("state", evaluation ? formatState(evaluation.eligibility_status) : "—"),
      detail("posted", formatDate(job.posted_at))
    );
    renderAssessment(evaluation);
    $("description-content").replaceChildren(
      ...renderOpportunity(job.opportunity)
    );
    setLink("source-link", job.url);
    $("apply-link").hidden = !job.apply_url;
    if (job.apply_url) setLink("apply-link", job.apply_url);
    loadBrowserLinks(job.application);
  }

  function renderAssessment(evaluation) {
    const list = $("assessment-list");
    list.replaceChildren();
    if (!evaluation) {
      list.appendChild(detail("state", "not scored"));
      return;
    }
    list.append(
      detail("eligibility", formatState(evaluation.eligibility_status)),
      detail("fit", number(evaluation.fit_score)),
      detail("importance", number(evaluation.importance_score)),
      detail("tier", formatTier(evaluation.tier)),
      detail("gaps", assessmentGaps(evaluation.summary))
    );
  }

  function renderOpportunity(opportunity) {
    if (!opportunity || !Array.isArray(opportunity.sections)) {
      return [emptyMessage("not extracted")];
    }
    return opportunity.sections.map((section) => {
      const block = document.createElement("section");
      block.className = "description-block";
      const heading = document.createElement("h3");
      heading.textContent = section.label;
      block.appendChild(heading);
      if (section.kind === "list") {
        const list = document.createElement("ul");
        list.className = "description-list";
        section.items.forEach((unit) => {
          const item = document.createElement("li");
          item.textContent = unit;
          list.appendChild(item);
        });
        block.appendChild(list);
      } else {
        section.items.forEach((unit) => {
          const paragraph = document.createElement("p");
          paragraph.textContent = unit;
          block.appendChild(paragraph);
        });
      }
      return block;
    });
  }

  function assessmentGaps(summary) {
    const match = String(summary || "").match(/gaps:\s*(.*?)(?:\.$|$)/i);
    if (!match || !match[1]) return "—";
    return /no extracted evidence gaps/i.test(match[1]) ? "none" : match[1];
  }

  function loadBrowserLinks(application) {
    const request = ++browserRequest;
    resetBrowserPanel();
    if (!application) {
      setText("browser-message", "no application");
      return;
    }
    setText("browser-message", "checking…");
    fetch(
      "/api/applications/" + encodeURIComponent(application.id) + "/browser-links",
      { cache: "no-store" }
    )
      .then((response) => {
        if (!response.ok) throw new Error("browser links unavailable");
        return response.json();
      })
      .then((payload) => {
        if (request !== browserRequest) return;
        showBrowserLinks(payload);
      })
      .catch(() => {
        if (request === browserRequest) setText("browser-message", "no replay");
      });
  }

  function showBrowserLinks(payload) {
    const live = payload.live_view;
    const replays = payload.replays || [];
    const actions = $("browser-actions");
    actions.replaceChildren();

    if (payload.live_view_status === "active" && live) {
      setText("browser-message", replays.length ? "live · replay" : "live");
      $("live-view-wrap").hidden = false;
      $("live-view").src = live.debugger_fullscreen_url;
      if (live.debugger_fullscreen_url) {
        actions.appendChild(actionLink("live ↗", live.debugger_fullscreen_url));
      }
    }

    replays.forEach((replay, index) => {
      const label = replays.length === 1 ? "replay" : "replay " + (index + 1);
      actions.appendChild(actionButton(label, () => playReplay(replay)));
    });

    if (payload.live_view_status !== "active" && replays.length) {
      setText("browser-message", "replay");
    }
    if (payload.live_view_status !== "active" && !replays.length) {
      setText("browser-message", "no replay");
    }
  }

  function playReplay(replay) {
    const video = $("replay-video");
    $("replay-wrap").hidden = false;
    setText("replay-label", "tab " + replay.page_id);
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = replay.playlist_url;
      video.play().catch(() => {});
      return;
    }
    loadHls()
      .then(() => {
        if (hlsPlayer) hlsPlayer.destroy();
        hlsPlayer = new window.Hls();
        hlsPlayer.loadSource(replay.playlist_url);
        hlsPlayer.attachMedia(video);
        hlsPlayer.on(window.Hls.Events.MANIFEST_PARSED, () => {
          video.play().catch(() => {});
        });
      })
      .catch(() => setText("browser-message", "replay unavailable"));
  }

  function loadHls() {
    if (window.Hls) return Promise.resolve();
    if (hlsPromise) return hlsPromise;
    hlsPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/hls.js@1";
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
    return hlsPromise;
  }

  function resetBrowserPanel() {
    const video = $("replay-video");
    video.pause();
    if (hlsPlayer) {
      hlsPlayer.destroy();
      hlsPlayer = null;
    }
    video.removeAttribute("src");
    video.load();
    $("browser-actions").replaceChildren();
    $("browser-message").textContent = "no replay";
    $("live-view-wrap").hidden = true;
    $("live-view").src = "about:blank";
    $("replay-wrap").hidden = true;
    $("replay-label").textContent = "";
  }

  function actionButton(label, handler) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "link-button browser-action";
    button.textContent = label;
    button.addEventListener("click", handler);
    return button;
  }

  function actionLink(label, href) {
    const link = document.createElement("a");
    link.className = "browser-action";
    link.href = href;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = label;
    return link;
  }

  function setView(view, writeHash = true) {
    state.view = view;
    document.querySelectorAll("[data-view]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.view === view);
    });
    document.querySelectorAll("[data-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== view;
    });
    if (writeHash && window.location.hash !== "#" + view) window.location.hash = view;
  }

  function setConnection(label, status) {
    setText("connection-state", label);
    $("signal").className = "signal" + (status ? " is-" + status : "");
  }

  function entryText(className, primary, secondary) {
    const wrapper = document.createElement("span");
    wrapper.className = className;
    wrapper.textContent = primary;
    if (secondary) {
      const detail = document.createElement("span");
      detail.className = "entry-source";
      detail.textContent = secondary;
      wrapper.appendChild(detail);
    }
    return wrapper;
  }

  function jobMeta(job) {
    return [
      job.fit_score === null ? null : "fit " + number(job.fit_score),
      job.tier ? formatTier(job.tier) : null,
      job.eligibility_status ? formatState(job.eligibility_status) : null,
      formatDate(job.posted_at || job.first_seen_at),
    ].filter(Boolean).join(" · ");
  }

  function detail(label, value) {
    const row = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value;
    row.append(dt, dd);
    return row;
  }

  function emptyMessage(message) {
    const paragraph = document.createElement("p");
    paragraph.className = "empty";
    paragraph.textContent = message;
    return paragraph;
  }

  function option(value, label) {
    const item = document.createElement("option");
    item.value = value;
    item.textContent = label;
    return item;
  }

  function displaySource(source) {
    return source === "swelist" ? "simplifyjobs" : source;
  }

  function formatTier(value) {
    return value ? String(value).replaceAll("_", " ") : "—";
  }

  function formatState(value) {
    return value ? String(value).replaceAll("_", " ") : "—";
  }

  function setText(id, value) {
    $(id).textContent = value === null || value === undefined ? "—" : value;
  }

  function setLink(id, value) {
    $(id).href = value || "#";
  }

  function number(value) {
    return value === null || value === undefined
      ? "—"
      : new Intl.NumberFormat("en-CA", { maximumFractionDigits: 2 }).format(value);
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value).slice(0, 10) : date.toISOString().slice(0, 10);
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? String(value).slice(0, 16).replace("T", " ")
      : date.toLocaleString("en-CA", { dateStyle: "short", timeStyle: "short", hour12: false });
  }
})();
