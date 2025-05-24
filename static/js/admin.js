// static/js/admin.js

// ── CSRF TOKEN ──────────────────────────────────────
// Grab the CSRF token from your <meta> tag (if CSRFProtect is enabled)
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

// ── DOM REFERENCES ──────────────────────────────────
const statusFilter = document.getElementById("status-filter");
const exportBtn = document.getElementById("export-csv");
const bulkUpdateBtn = document.getElementById("bulk-update-btn");
const tbody = document.querySelector("#orders-table tbody");

// ── HELPER FUNCTIONS ────────────────────────────────
/**
 * PATCH request to update an order's status
 */
function patchStatus(id, status) {
  return fetch(`/order/update/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
    },
    body: JSON.stringify({ status }),
  });
}

/**
 * PATCH request to archive an order
 */
function archiveOrder(id) {
  return fetch(`/order/archive/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
    },
  });
}

// ── DATA FETCHING ───────────────────────────────────
/**
 * Fetch all non-archived orders and render them
 */
function fetchOrders() {
  fetch("/orders")
    .then((r) => r.json())
    .then(renderOrders)
    .catch(console.error);
}

// ── RENDER ORDERS ───────────────────────────────────
/**
 * Build the orders table, apply filter, and wire up buttons
 */
function renderOrders(orders) {
  const filter = statusFilter.value;
  const data =
    filter === "All" ? orders : orders.filter((o) => o[4] === filter);

  tbody.innerHTML = "";
  data.forEach((o) => {
    const [id, table, orderDate, items, status, notes] = o;

    // parse & summarize JSON items array
    let summary = items;
    try {
      const arr = JSON.parse(items);
      const counts = {};
      arr.forEach((it) => {
        if (it && typeof it === "object" && it.name) {
          counts[it.name] = (counts[it.name] || 0) + (it.qty || 1);
        } else {
          counts[it] = (counts[it] || 0) + 1;
        }
      });
      summary = Object.entries(counts)
        .map(([name, qty]) => `${qty}× ${name}`)
        .join(", ");
    } catch {
      // leave summary as raw items string on parse error
    }

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${id}</td>
      <td>${table}</td>
      <td>${summary}</td>
      <td>${notes}</td>
      <td>
        <select class="status-select" data-id="${id}">
          <option value="Pending"${
            status === "Pending" ? " selected" : ""
          }>Beklemede</option>
          <option value="Preparing"${
            status === "Preparing" ? " selected" : ""
          }>Hazırlanıyor</option>
          <option value="Ready"${
            status === "Ready" ? " selected" : ""
          }>Hazır</option>
          <option value="Completed"${
            status === "Completed" ? " selected" : ""
          }>Tamamlandı</option>
        </select>
      </td>
      <td>${orderDate}</td>
      <td>
        <div class="action-buttons">
          <button class="btn-update" data-id="${id}">Güncelle</button>
          <button class="btn-archive" data-id="${id}">Arşivle</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // ── ROW ACTIONS ───────────────────────────────────
  // per-row "Güncelle" button  (auto-archive if Completed)
  document.querySelectorAll(".btn-update").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const sel = btn.closest("tr").querySelector(".status-select");

      patchStatus(id, sel.value)
        .then(() => {
          // if the new status is "Completed", archive it immediately
          if (sel.value === "Completed") {
            return archiveOrder(id);
          }
        })
        .then(fetchOrders) // refresh the table after status and (if Completed) archive it
        .catch(console.error);
    });
  });

  // per-row "Arşivle" button
  document.querySelectorAll(".btn-archive").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      archiveOrder(id).then(fetchOrders).catch(console.error);
    });
  });
}

// ── EVENT LISTENERS ────────────────────────────────
// Filter dropdown reloads
statusFilter.addEventListener("change", fetchOrders);

// CSV export button
exportBtn.addEventListener("click", () => {
  window.location = "/orders/export";
});

// Bulk update button
if (bulkUpdateBtn) {
  bulkUpdateBtn.addEventListener("click", () => {
    const promises = Array.from(
      document.querySelectorAll(".status-select")
    ).map((sel) => patchStatus(sel.dataset.id, sel.value));
    Promise.all(promises).then(fetchOrders).catch(console.error);
  });
}

// ── INITIAL LOAD ────────────────────────────────────
fetchOrders();
