"use strict";
// Screen 1: language → Screen 2: profile names (click = install) → progress.

const token = new URLSearchParams(location.search).get("token") || "";
const headers = token ? { "X-Token": token } : {};
let lang = null;
let texts = {};
let current = null;          // profile chosen in this browser
let lastProfiles = "";

const $ = (id) => document.getElementById(id);

function t(key, params = {}) {
  let s = texts[key] || key;
  for (const [k, v] of Object.entries(params)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

function show(screen) {
  for (const id of ["screen-language", "screen-profiles", "screen-progress"]) $(id).hidden = id !== screen;
}

async function setLanguage(code) {
  texts = await (await fetch(`/i18n/${code}.json`)).json();
  lang = code;
  document.documentElement.lang = code;
  document.querySelectorAll("[data-t]").forEach((el) => (el.textContent = t(el.dataset.t)));
  $("title").textContent = t("title");
  lastProfiles = "";
  show("screen-profiles");
  poll();
}

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { ...headers, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

function renderProfiles(profiles) {
  const key = JSON.stringify(profiles);
  if (key === lastProfiles) return;
  lastProfiles = key;
  const box = $("profiles");
  box.replaceChildren();
  for (const p of profiles) {
    const b = document.createElement("button");
    b.textContent = p.name;
    b.onclick = async () => {
      current = p.name;
      const r = await api("/api/install", { profile: p.id, lang });
      if (r.ok) show("screen-progress");
      poll();
    };
    box.appendChild(b);
  }
}

function renderError(err, detail, textEl, detailEl, box) {
  box.hidden = !err;
  if (err) {
    textEl.textContent = t(err.key, err.params);
    detailEl.textContent = detail || "";
  }
}

async function poll() {
  let s;
  try {
    s = await api("/api/state");
  } catch {
    return;
  }
  if (s.remote) {
    const ip = s.remote.ips[0] || "<ip>";
    $("remote").textContent = lang ? t("remote", { ip, port: s.remote.port, token: s.remote.token })
                                   : `Remote: http://${ip}:${s.remote.port}/?token=${s.remote.token}`;
  }
  if (!lang) return;

  if (["installing", "done", "failed"].includes(s.phase)) {
    show("screen-progress");
    $("installing").textContent = s.phase === "done" ? t("done") : t("installing", { profile: current || "" });
    $("bar-fill").style.width = `${s.progress}%`;
    $("step").textContent = s.step ? `${t(s.step)} – ${s.progress}%` : "";
    $("log").textContent = (s.log || []).join("\n");
    $("failed").hidden = s.phase !== "failed";
    if (s.phase === "failed") $("failed-detail").textContent = s.detail || "";
    return;
  }
  show("screen-profiles");
  $("loading").hidden = s.phase !== "loading";
  renderProfiles(s.phase === "ready" ? s.profiles : []);
  renderError(s.error, s.detail, $("error-text"), $("error-detail"), $("error"));
  $("retry").hidden = s.phase !== "error";
}

document.querySelectorAll("[data-lang]").forEach((b) => (b.onclick = () => setLanguage(b.dataset.lang)));
$("back").onclick = () => { lang = null; show("screen-language"); };
$("retry").onclick = () => api("/api/retry", {}).then(poll);
$("failed-retry").onclick = () => api("/api/retry", {}).then(() => { current = null; poll(); });
setInterval(poll, 1000);
poll();
