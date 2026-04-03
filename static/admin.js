/*
  Admin Dashboard UI logic.
  Handles: stats, developers, endpoints, customers, XRPL payments.
*/

const els = {
  devsList: document.getElementById("devsList"),
  endpointsList: document.getElementById("endpointsList"),
  customersList: document.getElementById("customersList"),
  paymentsList: document.getElementById("paymentsList"),
  feesList: document.getElementById("feesList"),
};


// ── Stats ──
async function loadStats() {
  const data = await getJSON("/api/admin/stats");

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

  if (!data.developers || data.developers.length === 0) {
    els.devsList.innerHTML = "<p class='muted'>No developers yet.</p>";
    return;
  }

  const rows = data.developers.map(d => `
    <tr>
      <td>${d.name}</td>
      <td>${d.email}</td>
      <td>XXXXXX...${d.developer_key.slice(-6)}</td>
      <td>${d.created_at.slice(0,19).replace('T',' ')}</td>
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

  if (!data.endpoints || data.endpoints.length === 0) {
    els.endpointsList.innerHTML = "<p class='muted'>No endpoints yet.</p>";
    return;
  }

  const rows = data.endpoints.map(ep => `
    <tr>
      <td>${ep.name}</td>
      <td>${ep.developer_name || ""}</td>
      <td>${ep.url}</td>
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

  if (!data.customers || data.customers.length === 0) {
    els.customersList.innerHTML = "<p class='muted'>No customers yet.</p>";
    return;
  }

  const rows = data.customers.map(u => `
    <tr>
      <td>${u.name}</td>
      <td>${u.email}</td>
      <td>${formatCost(u.balance)}</td>
      <td>XXXXXX...${u.api_key.slice(-6)}</td>
      <td>${u.created_at.slice(0,19).replace('T',' ')}</td>
    </tr>
  `).join("");

  els.customersList.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Email</th><th>Balance</th><th>API Key</th><th>Joined</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
});

// ── XRPL Payments ──
document.getElementById("loadPaymentsBtn").addEventListener("click", async () => {
  const data = await getJSON("/api/admin/payments");

  if (!data.payments || data.payments.length === 0) {
    els.paymentsList.innerHTML = "<p class='muted'>No payments yet.</p>";
    return;
  }

  const rows = data.payments.map(p => `
    <tr>
      <td>${p.user_name}</td>
      <td>${formatCost(p.delta_credits)}</td>
      <td>${p.reason}</td>
      <td>${p.meta?.txHash || '-'}</td>
      <td>${p.created_at.slice(0,19).replace('T',' ')}</td>
    </tr>
  `).join("");

  els.paymentsList.innerHTML = `
    <table>
      <thead><tr><th>Customer</th><th>Credits</th><th>Type</th><th>TX Hash</th><th>Date</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
});

// ── Platform Fees ──
document.getElementById("loadFeesBtn").addEventListener("click", async () => {
  const data = await getJSON("/api/admin/fees");

  if (!data.fees || data.fees.length === 0) {
    els.feesList.innerHTML = "<p class='muted'>No fees recorded yet.</p>";
    return;
  }

  const rows = data.fees.map(f => `
    <tr>
      <td>${f.developer_name}</td>
      <td>${f.amount_credits} credits</td>
      <td>${f.amount_xrp} XRP</td>
      <td>${f.status}</td>
      <td>${f.created_at.slice(0,19).replace('T',' ')}</td>
    </tr>
  `).join("");

  els.feesList.innerHTML = `
    <table>
      <thead><tr><th>Developer</th><th>Credits</th><th>XRP</th><th>Status</th><th>Date</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
});
