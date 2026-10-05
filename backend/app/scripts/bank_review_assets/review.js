const KEY = "bank-review:" + document.body.dataset.spec;
const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; } };
const save = (data) => { try { localStorage.setItem(KEY, JSON.stringify(data)); } catch {} };
const notes = load();
document.querySelectorAll("[data-id]").forEach((card) => {
  const id = card.dataset.id, area = card.querySelector("textarea");
  const state = notes[id] || {};
  area.value = state.note || "";
  card.querySelectorAll("input[type=radio]").forEach((radio) => {
    radio.checked = radio.value === state.verdict;
    radio.addEventListener("change", () => { notes[id] = { ...notes[id], verdict: radio.value }; save(notes); count(); });
  });
  area.addEventListener("input", () => { notes[id] = { ...notes[id], note: area.value }; save(notes); });
});
const count = () => {
  const done = Object.values(notes).filter((n) => n.verdict).length;
  document.getElementById("progress").textContent = done + " / " + document.querySelectorAll("[data-id]").length;
};
count();
document.getElementById("filter").addEventListener("change", (event) => {
  const topic = event.target.value;
  document.querySelectorAll("[data-id]").forEach((card) => {
    card.style.display = !topic || card.dataset.topic === topic ? "" : "none";
  });
});
document.getElementById("export").addEventListener("click", () => {
  const rows = [["template_id", "verdict", "note"]];
  document.querySelectorAll("[data-id]").forEach((card) => {
    const n = notes[card.dataset.id];
    if (n && (n.verdict || n.note)) rows.push([card.dataset.id, n.verdict || "", (n.note || "").replace(/\n/g, " ")]);
  });
  const csv = rows.map((r) => r.map((v) => '"' + String(v).replace(/"/g, '""') + '"').join(",")).join("\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv" }));
  link.download = "bank-review-" + document.body.dataset.spec + ".csv";
  link.click();
});
