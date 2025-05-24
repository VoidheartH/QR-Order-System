// static/js/script.js

// ── 1) Read Table ID ──────────────────────────────────
// Grab the table ID from the body’s data attribute
const tableId = parseInt(document.body.dataset.tableid, 10);

// ── 2) Turkish Status Mapping ─────────────────────────
/// Map English statuses to Turkish labels
const statusMap = {
  Pending: "Beklemede",
  Preparing: "Hazırlanıyor",
  Ready: "Hazır",
  Completed: "Tamamlandı",
};

// ── 3) Fetch & Render Menu Items ──────────────────────
/**
 * Load menu items from the server and render cards with quantity controls
 */
fetch("/menu")
  .then((res) => res.json())
  .then((menuItems) => {
    const menuContainer = document.getElementById("menu-container");
    menuContainer.innerHTML = "";

    // Build each menu-item card
    menuItems.forEach(([id, name, price, imageUrl, description]) => {
      const card = document.createElement("div");
      card.classList.add("menu-item");
      card.innerHTML = `
        <img src="${imageUrl}" alt="${name}">
        <h4>${name} — ₺${price.toFixed(2)}</h4>
        <p>${description}</p>
        <div class="quantity-selector">
          <button class="qty-btn decrement" data-id="${id}">−</button>
          <span
            id="quantity-${id}"
            class="qty-value"
            data-item-name="${name}"
            data-item-price="${price}"
          >0</span>
          <button class="qty-btn increment" data-id="${id}">+</button>
        </div>
      `;
      menuContainer.appendChild(card);
    });

    // Bind +/- buttons
    document.querySelectorAll(".qty-btn").forEach((btn) =>
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        const span = document.getElementById(`quantity-${id}`);
        let current = parseInt(span.textContent, 10) || 0;
        current = btn.classList.contains("increment")
          ? current + 1
          : Math.max(0, current - 1);
        span.textContent = current;
        updateCart();
      })
    );

    // Bind textarea auto-expand
    const notes = document.getElementById("special-notes");
    notes.addEventListener("input", () => {
      notes.style.height = "auto";
      notes.style.height = notes.scrollHeight + "px";
    });

    updateCart();
  })
  .catch((err) => console.error("Error fetching menu:", err));

// ── 4) Update Cart ────────────────────────────────────
/**
 * Read quantities, render cart items list and total
 */
function updateCart() {
  const cartPanel = document.getElementById("cart-panel");
  const itemsUl = document.getElementById("cart-items");
  const totalP = document.getElementById("cart-total");

  // Collect items with qty > 0
  const cart = [];
  document.querySelectorAll(".qty-value").forEach((span) => {
    const qty = parseInt(span.textContent, 10) || 0;
    if (qty > 0) {
      cart.push({
        name: span.dataset.itemName,
        price: parseFloat(span.dataset.itemPrice),
        qty,
      });
    }
  });

  // Show or hide the cart panel
  cartPanel.style.display = cart.length ? "block" : "none";

  // Render each item and calculate total
  let total = 0;
  itemsUl.innerHTML = "";
  cart.forEach((it) => {
    const li = document.createElement("li");
    li.textContent = `${it.qty}× ${it.name} — ₺${(it.price * it.qty).toFixed(
      2
    )}`;
    itemsUl.appendChild(li);
    total += it.price * it.qty;
  });
  totalP.textContent = `Toplam: ₺${total.toFixed(2)}`;
}

// ── 5) Clear Cart ─────────────────────────────────────
/**
 * Handle "İptal" button to reset quantities
 */
document.getElementById("cart-clear").addEventListener("click", (e) => {
  e.preventDefault();
  document
    .querySelectorAll(".qty-value")
    .forEach((span) => (span.textContent = "0"));
  updateCart();
});

// ── 6) Submit Cart ────────────────────────────────────
/**
 * Handle "Siparişi Gönder" button to POST order
 */
document.getElementById("cart-submit").addEventListener("click", (e) => {
  e.preventDefault();
  const selectedItems = [];
  document.querySelectorAll(".qty-value").forEach((span) => {
    const qty = parseInt(span.textContent, 10) || 0;
    const name = span.dataset.itemName;
    if (qty > 0) selectedItems.push({ name, qty });
  });
  if (!selectedItems.length) return;

  const specialNotes = document.getElementById("special-notes").value;
  const orderData = {
    table_id: tableId,
    items: selectedItems,
    special_notes: specialNotes,
  };

  const csrf = document
    .querySelector('meta[name="csrf-token"]')
    ?.getAttribute("content");
  fetch("/order", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRFToken": csrf } : {}),
    },
    body: JSON.stringify(orderData),
  })
    .then((res) => {
      if (!res.ok) throw new Error();
      return res.json();
    })
    .then((data) => {
      // Show success message
      const successDiv = document.getElementById("order-success");
      successDiv.textContent =
        "✅ Siparişiniz alınmıştır, teşekkür ederiz! Aşağıdaki “Siparişleriniz” kısmından durumunuzu takip edebilirsiniz.";
      successDiv.style.display = "block";

      // Reset quantities and notes
      document
        .querySelectorAll(".qty-value")
        .forEach((span) => (span.textContent = "0"));
      document.getElementById("special-notes").value = "";
      updateCart();
      fetchOrders();
    })
    .catch((err) => console.error("Error placing order:", err));
});

// ── 7) Fetch & Render Past Orders ─────────────────────
/**
 * Fetch past orders for this table and update status list
 */
function fetchOrders() {
  fetch(`/orders/table/${tableId}`)
    .then((res) => res.json())
    .then((orders) => {
      const list = document.getElementById("order-status-list");
      const stamp = document.getElementById("last-updated");
      list.innerHTML = "";
      stamp.textContent = `Son güncelleme: ${new Date().toLocaleTimeString()}`;

      if (!orders.length) {
        list.innerHTML = "<li>Henüz sipariş yok.</li>";
        return;
      }
      orders.forEach((o) => {
        let arr;
        try {
          arr = JSON.parse(o[3].replace(/'/g, '"'));
        } catch {
          arr = [];
        }
        const counts = {};
        arr.forEach((item) => {
          if (
            item &&
            typeof item === "object" &&
            "name" in item &&
            "qty" in item
          ) {
            counts[item.name] = (counts[item.name] || 0) + item.qty;
          } else {
            counts[item] = (counts[item] || 0) + 1;
          }
        });
        const summary = Object.entries(counts)
          .map(([n, q]) => `${q}× ${n}`)
          .join(", ");
        const turStatus = statusMap[o[4]] || o[4];
        const li = document.createElement("li");
        li.textContent = `${summary} — Durum: ${turStatus}`;
        list.appendChild(li);
      });
    })
    .catch((err) => console.error("Error fetching orders:", err));
}

// ── 8) Initial Load & Auto-Poll ──────────────────────
/**
 * On page load, fetch past orders and then poll every 10 seconds
 */
document.addEventListener("DOMContentLoaded", () => {
  fetchOrders();
  setInterval(fetchOrders, 10000);
});
