"use strict";
fetch("data/results.json").then(response => {
  if (!response.ok) throw new Error("Evaluation unavailable");
  return response.json();
}).then(report => {
  const body = document.getElementById("results-body");
  body.replaceChildren();
  const titles = {pick_place: "Pick & place", push: "Surface push", stack: "Stack on a pedestal"};
  for (const [task, title] of Object.entries(titles)) {
    const row = document.createElement("tr");
    const stats = report.tasks[task];
    const interval = stats.jev.wilson_95;
    const cells = [title, `${stats.jev.successes} / ${stats.jev.episodes}`, `${stats.rule.successes} / ${stats.rule.episodes}`,
      interval[0] === null ? "Not evaluated" : `${(100 * interval[0]).toFixed(1)}–${(100 * interval[1]).toFixed(1)}%`];
    for (const value of cells) {const td = document.createElement("td"); td.textContent = value; row.append(td);}
    body.append(row);
  }
  document.getElementById("results-note").textContent = `${report.complete ? "Complete" : "Incomplete"} evaluation · ${report.episodes} / ${report.expected} episodes · Seeds ${report.seeds.join(", ")} · Frozen source ${report.source_sha256.slice(0, 12)}. Small sample; these results do not establish general-purpose manipulation ability.`;
}).catch(() => {
  document.getElementById("results-body").textContent = "Evaluation data could not be loaded. See the repository report.";
});
