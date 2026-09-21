"use strict";

const tasks = {
  peg_insert: {name: "Peg insertion", category: "PRECISION WITH CLEARANCE", title: "A little room to get it right.", description: "Insert a 20 mm peg into a 30 mm socket, release, and let it settle. A deliberately loose fit with real contact physics.", specs: [["Peg / socket diameter", "20 / 30 mm"], ["Required insertion", "≥ 30 mm"], ["Released & stable", "0.5 s"]], challenge: true},
  obstacle_pick_place: {name: "Gate pick & place", category: "TRANSPORT THROUGH CONSTRAINTS", title: "Over the bar. Between the posts.", description: "Carry a cube through a narrow gate, clear the low crossbar, then place it in the target. The whole arm must avoid contact.", specs: [["Cube / gate opening", "40 / 70 mm"], ["Crossbar / clearance", "120 / ≥ 5 mm"], ["Contact force limit", "0.05 N"]], challenge: true},
  pick_place: {name: "Pick & place", category: "GRASP & TRANSPORT", title: "Pick it up. Put it down.", description: "Lift a cube from the table, carry it into the marked region, and release. Success requires the whole footprint inside the target.", specs: [["Cube width", "40 mm"], ["Target width", "120 mm"], ["Released & stable", "0.5 s"]]},
  push: {name: "Surface push", category: "CONTROL THROUGH CONTACT", title: "Move it without lifting it.", description: "Close the empty fingers and slide the cube into the target. A grasp or lift invalidates the trial; layouts vary along a straight +X lane.", specs: [["Cube width", "40 mm"], ["Travel distance", "160–200 mm"], ["Surface friction", "0.3"]]},
  stack: {name: "Pedestal stack", category: "PLACEMENT & SUPPORT", title: "Find a stable landing.", description: "Place the cube onto a fixed pedestal. The evaluator checks full containment, physical support, release and stability.", specs: [["Cube width", "40 mm"], ["Fixed pedestal", "80 × 80 × 40 mm"], ["Released & stable", "0.5 s"]]}
};
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
let selectedTask = Object.hasOwn(tasks, params.get("task")) ? params.get("task") : "peg_insert";
let selectedOutcome = params.get("outcome") === "failure" ? "failure" : "success";
let demonstrations = null;
let results = null;
let manifestFailed = false;

async function evidence(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Evidence unavailable: ${path}`);
  return response.json();
}

function textNode(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function selectTask(task, outcome = "success", updateURL = true) {
  selectedTask = task;
  selectedOutcome = outcome;
  const info = tasks[task];
  document.querySelectorAll("[data-task]").forEach(button => {
    const active = button.dataset.task === task;
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
  });
  document.querySelectorAll("[data-outcome]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.outcome === outcome));
  });
  $("task-panel").setAttribute("aria-labelledby", `tab-${task}`);
  $("task-category").textContent = info.category;
  $("task-title").textContent = info.title;
  $("task-description").textContent = info.description;
  $("task-specs").replaceChildren(...info.specs.map(([label, value]) => {
    const pair = document.createElement("div");
    pair.append(textNode("dt", label), textNode("dd", value));
    return pair;
  }));
  const stats = results?.tasks[task]?.jev;
  $("task-rate").textContent = stats ? `${stats.successes}/${stats.episodes}` : "—";
  $("task-provenance").textContent = info.challenge ? "Original formal evaluation trial. Selected by the lowest available seed for each outcome." : "Separate demonstration seed; this video is excluded from formal evaluation counts.";
  renderVideo();
  if (updateURL) {
    const url = new URL(location.href);
    url.searchParams.set("task", task);
    url.searchParams.set("outcome", outcome);
    history.replaceState(null, "", url);
  }
}

function renderVideo() {
  const video = $("experiment-video");
  video.pause();
  const success = selectedOutcome === "success";
  const entry = demonstrations?.find(d => d.task === selectedTask && d.policy === "jev" && d.success === success);
  const available = Boolean(entry && entry.available !== false);
  const pending = demonstrations === null && !manifestFailed;
  video.hidden = !available;
  $("missing-video").hidden = available;
  $("video-download").hidden = !available;
  $("video-label").textContent = tasks[selectedTask].challenge ? "JEV / ORIGINAL EVALUATION" : "JEV / DEMONSTRATION";
  if (available) {
    const src = entry.video || `media/${selectedTask}.mp4`;
    video.poster = src.replace(/\.mp4$/, ".jpg");
    video.setAttribute("aria-label", `${tasks[selectedTask].name} ${selectedOutcome}, seed ${entry.seed}`);
    if (video.getAttribute("src") !== src) {
      video.src = src;
      video.load();
    }
    $("video-download").href = src;
    $("video-timing").textContent = `SEED ${entry.seed} · ${entry.decisions} decisions · ${entry.simulation_time_s.toFixed(1)} s simulation / ${entry.wall_s.toFixed(1)} s wall time`;
    if (entry.collision_analysis) {
      const force = entry.collision_analysis.contacts.reduce((sum, c) => sum + c.normal_force_n, 0);
      $("task-provenance").textContent = `Failure at decision ${entry.decisions}: link5 contacted the gate post at ${force.toFixed(2)} N (limit 0.05 N), while lowering after the cube crossed.`;
    }
  } else {
    // Release the previous video when the selected outcome has no recording.
    video.removeAttribute("src");
    video.querySelectorAll("source").forEach(source => source.remove());
    video.load();
    $("missing-title").textContent = pending ? "Loading trial evidence…" : manifestFailed ? "Video evidence unavailable." : entry?.available === false ? "No natural failure recorded." : "No failure video published.";
    $("missing-description").textContent = pending ? "Retrieving the original demonstration manifest." : manifestFailed ? "The manifest could not be loaded. The reports and MP4 files remain available in the repository." : entry?.available === false ? "All ten JEV insertion trials succeeded. No failure was manufactured for the demonstration." : "The original campaign published success demonstrations. Any evaluation failures remain in the result counts and report.";
    $("video-timing").textContent = pending ? "Loading…" : "No video for this selection";
  }
}

document.querySelectorAll("[data-task]").forEach(button => {
  button.addEventListener("click", () => selectTask(button.dataset.task));
  button.addEventListener("keydown", event => {
    const tabs = [...document.querySelectorAll("[data-task]")];
    const index = tabs.indexOf(button);
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") next = (index + tabs.length - 1) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    if (next === undefined) return;
    event.preventDefault();
    tabs[next].focus();
    tabs[next].click();
  });
});
document.querySelectorAll("[data-outcome]").forEach(button => {
  button.addEventListener("click", () => selectTask(selectedTask, button.dataset.outcome));
});
$("watch-failure").addEventListener("click", () => {
  selectTask("obstacle_pick_place", "failure");
  $("experiments").scrollIntoView();
  $("tab-obstacle_pick_place").focus({preventScroll: true});
});
selectTask(selectedTask, selectedOutcome, false);

evidence("data/demonstrations.json").then(entries => {
  demonstrations = entries;
  selectTask(selectedTask, selectedOutcome, false);
}).catch(() => { manifestFailed = true; renderVideo(); });

evidence("data/results.json").then(report => {
  results = report;
  $("trial-count").textContent = report.episodes;
  $("results-body").replaceChildren();
  $("result-chart").replaceChildren();
  const order = ["pick_place", "push", "stack", "peg_insert", "obstacle_pick_place"];
  for (const task of order) {
    const stats = report.tasks[task];
    if (!stats) continue;
    const row = document.createElement("tr");
    const interval = stats.jev.wilson_95.map(v => `${(100 * v).toFixed(1)}%`).join("–");
    for (const value of [tasks[task].name, `${stats.jev.successes}/${stats.jev.episodes}`, `${stats.rule.successes}/${stats.rule.episodes}`, interval]) row.append(textNode("td", value));
    $("results-body").append(row);
    const chartRow = document.createElement("div");
    chartRow.className = "result-row";
    chartRow.append(textNode("div", tasks[task].name, "result-name"));
    const bars = document.createElement("div"); bars.className = "bars";
    for (const policy of ["jev", "rule"]) {
      const track = document.createElement("div"); track.className = "bar-track";
      track.setAttribute("aria-hidden", "true");
      const bar = document.createElement("div"); bar.className = `bar ${policy}`;
      bar.style.width = `${100 * stats[policy].successes / stats[policy].episodes}%`;
      track.append(bar);
      const value = textNode("span", `${stats[policy].successes}/${stats[policy].episodes}`);
      value.setAttribute("aria-label", `${policy.toUpperCase()}: ${stats[policy].successes} of ${stats[policy].episodes} successful`);
      bars.append(track, value);
    }
    chartRow.append(bars); $("result-chart").append(chartRow);
  }
  const campaigns = report.campaigns.map(c => `${c.episodes} trials: ${c.source_sha256.slice(0, 12)}`).join("; ");
  $("results-note").textContent = `${report.episodes}/${report.expected} episodes complete. Seeds 0–9 per policy and task. Frozen campaigns: ${campaigns}.`;
  const stats = report.tasks[selectedTask].jev;
  $("task-rate").textContent = `${stats.successes}/${stats.episodes}`;
}).catch(() => {
  $("result-chart").textContent = "Evaluation data could not be loaded. See the linked repository report.";
  $("results-note").textContent = "Evaluation data unavailable.";
});

evidence("data/challenge-episodes.json").then(episodes => {
  const body = $("challenge-failures"); body.replaceChildren();
  for (const episode of episodes.filter(e => !e.success)) {
    const failure = episode.failure || {};
    let detail = failure.boundary || episode.end_reason;
    if (episode.collision_analysis) {
      detail += ". During lowering after crossing: " + episode.collision_analysis.contacts.map(c => `${c.bodies.join(" / ")} ${c.normal_force_n.toFixed(2)} N`).join("; ");
    } else if (episode.end_reason === "max_decisions") {
      detail += `. ${episode.rejected} workspace rejections; final requests +Y, measured grasp direction −Y. Object never grasped.`;
    } else if (failure.response_checks) {
      const invalid = failure.response_checks.find(c => c.selected_probability < c.maximum_probability);
      if (invalid) detail += `. ${invalid.head.toUpperCase()} chose ${invalid.choice} (${invalid.selected_probability}) below maximum ${invalid.maximum_probability}; action not executed.`;
    }
    const row = document.createElement("tr");
    for (const value of [`${tasks[episode.task].name} / ${episode.policy.toUpperCase()}`, episode.seed, failure.first_step || episode.decisions, detail]) row.append(textNode("td", value));
    body.append(row);
  }
}).catch(() => {
  const row = document.createElement("tr");
  const cell = textNode("td", "Failure evidence unavailable. See the full failure report.");
  cell.colSpan = 4; row.append(cell); $("challenge-failures").replaceChildren(row);
});
