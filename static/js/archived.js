// static/js/archived.js

// ── CSRF TOKEN ──────────────────────────────────────
// Grab the CSRF token from your <meta> tag (if CSRFProtect is enabled)
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

// ── DATA FETCHING ────────────────────────────────────
/**
 * Fetch archived orders from the server
 */
function fetchArchived() {
  fetch("/archived/data")
    .then((r) => r.json())
    .then(renderArchived)
    .catch(console.error);
}

// ── RENDER ARCHIVED ORDERS ───────────────────────────
/**
 * Render the archived orders table with optional filtering
 */
function renderArchived(orders) {
  const filter = document.getElementById("status-filter-archived").value;
  const tbody = document.querySelector("#archived-table tbody");
  tbody.innerHTML = "";

  const data =
    filter === "All" ? orders : orders.filter((o) => o[4] === filter);

  data.forEach((o) => {
    const [id, table, orderDate, items, status, notes] = o;

    // ── SUMMARIZE ITEMS ──────────────────────────────
    let arr;
    try {
      // replace single quotes with double to safely JSON.parse
      arr = JSON.parse(items.replace(/'/g, '"'));
    } catch {
      arr = [];
    }
    const counts = {};
    arr.forEach((it) => {
      if (it && it.name && it.qty) {
        counts[it.name] = (counts[it.name] || 0) + it.qty;
      } else {
        counts[it] = (counts[it] || 0) + 1;
      }
    });
    const summary = Object.entries(counts)
      .map(([n, q]) => `${q}× ${n}`)
      .join(", ");

    // ── BUILD TABLE ROW ──────────────────────────────
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${id}</td>
      <td>${table}</td>
      <td>${summary}</td>
      <td>${notes}</td>
      <td>${status}</td>
      <td>${orderDate}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ── WIRE UP CONTROLS ─────────────────────────────────
/**
 * Attach event listeners to filter, refresh, and export buttons
 */
document
  .getElementById("status-filter-archived")
  .addEventListener("change", fetchArchived);

document
  .getElementById("refresh-archived")
  .addEventListener("click", fetchArchived);

document.getElementById("export-archived").addEventListener("click", () => {
  window.location = "/archived/export";
});

// ── INITIAL LOAD ────────────────────────────────────
// Fetch and render archived orders when the DOM is ready
document.addEventListener("DOMContentLoaded", fetchArchived);
