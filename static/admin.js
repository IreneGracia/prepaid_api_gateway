/*
  Admin Dashboard UI logic.
  Handles: stats, developers, endpoints, customers, escrows.
*/

const els = {
  output: document.getElementById("output"),
  devsList: document.getElementById("devsList"),
  endpointsList: document.getElementById("endpointsList"),
  customersList: document.getElementById("customersList"),
  escrowsList: document.getElementById("escrowsList"),
  callsList: document.getElementById("callsList"),
};

const out = (data) => renderOutput(els.output, data);

// ── Stats ──
async function loadStats() {
  const data = await getJSON("/api/admin/stats");
  out(data);
  document.getElementById("statCustomers").textContent = data.totalCustomers ?? "-";
  document.getElementById("statDevs").textContent = data.totalDevelopers ?? "-";
  document.getElementById("statEndpoints").textContent = data.totalEndpoints ?? "-";
  document.getElementById("statCalls").textContent = data.totalApiCalls ?? "-";
  document.getElementById("statRevenue").textContent = data.totalRevenue ?? "-";
  document.getElementById("statCredits").textContent = data.totalCreditsIssued ?? "-";
}

document.getElementById("refreshStatsBtn").addEventListener("click", loadStats);
loadStats();

// ── Developers ──
document.getElementById("loadDevsBtn").addEventListener("click", async () => {
  const data = await getJSON("/api/admin/developers");
  out(data);

  if (!data.developers || data.developers.length === 0) {
    els.devsList.innerHTML = "<p class='muted'>No developers yet.</p>";
    return;
  }

  const rows = data.developers.map(d => `
    <tr>
      <td>${d.name}</td>
      <td>${d.email}</td>
      <td><code style="font-size:11px;">${d.developer_key.slice(0,12)}...</code></td>
      <td>${d.created_at.slice(0,10)}</td>
    </tr>
  `).join("");

  els.devsList.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Email</th><th>Dev Key</th><th>Joined</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
});

// ── Endpoints ──
document.getElementById("loadEndpointsBtn").addEventListener("click", async () => {
  const data = await getJSON("/api/admin/endpoints");
  out(data);

  if (!data.endpoints || data.endpoints.length === 0) {
    els.endpointsList.innerHTML = "<p class='muted'>No endpoints yet.</p>";
    return;
  }

  const rows = data.endpoints.map(ep => `
    <tr>
      <td><strong>${ep.name}</strong></td>
      <td>${ep.developer_name || ""}</td>
      <td style="font-size:12px;">${ep.url}</td>
      <td>${formatCost(ep.cost_per_call)}</td>
      <td>${ep.is_active ? "Active" : "Inactive"}</td>
    </tr>
  `).join("");

  els.endpointsList.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Developer</th><th>URL</th><th>Cost</th><th>Status</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
});

// ── Customers ──
document.getElementById("loadCustomersBtn").addEventListener("click", async () => {
  const data = await getJSON("/api/admin/customers");
  out(data);

  if (!data.customers || data.customers.length === 0) {
    els.customersList.innerHTML = "<p class='muted'>No customers yet.</p>";
    return;
  }

  const rows = data.customers.map(u => `
    <tr>
      <td>${u.name}</td>
      <td>${u.email}</td>
      <td>${formatCost(u.balance)}</td>
      <td><code style="font-size:11px;">${u.api_key.slice(0,12)}...</code></td>
      <td>${u.created_at.slice(0,10)}</td>
    </tr>
  `).join("");

  els.customersList.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Email</th><th>Balance</th><th>API Key</th><th>Joined</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
});

// ── Escrows ──
document.getElementById("loadEscrowsBtn").addEventListener("click", async () => {
  const data = await getJSON("/api/admin/escrows");
  out(data);

  if (!data.escrows || data.escrows.length === 0) {
    els.escrowsList.innerHTML = "<p class='muted'>No escrows yet.</p>";
    return;
  }

  const rows = data.escrows.map(e => `
    <tr>
      <td>${e.user_name}</td>
      <td>${e.total_credits}</td>
      <td>${e.claimed_credits}</td>
      <td>${e.total_credits - e.claimed_credits}</td>
      <td>${e.status}</td>
      <td>${e.created_at.slice(0,10)}</td>
    </tr>
  `).join("");

  els.escrowsList.innerHTML = `
    <table>
      <thead><tr><th>Customer</th><th>Total</th><th>Claimed</th><th>Remaining</th><th>Status</th><th>Created</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
});
