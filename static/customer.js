/*
  Customer Portal UI logic.

  REQUIRES ?endpoint=ENDPOINT_ID in the URL.
  The portal is locked to that specific endpoint — the customer
  registers, tops up, and calls that one API. Nothing else.
*/

// ── Read endpoint from URL (required) ──
const urlParams = new URLSearchParams(window.location.search);
const endpointId = urlParams.get("endpoint");

if (!endpointId) {
  document.getElementById("noEndpointError").style.display = "block";
} else {
  document.getElementById("portalContent").style.display = "block";
}

// ── DOM elements ──
const els = {
  name: document.getElementById("name"),
  email: document.getElementById("email"),
  apiKey: document.getElementById("apiKey"),
  credits: document.getElementById("credits"),
  callBody: document.getElementById("callBody"),
  output: document.getElementById("output"),
  ledgerTableWrap: document.getElementById("ledgerTableWrap"),
  qrWrap: document.getElementById("qrWrap"),
  qrImage: document.getElementById("qrImage"),
  qrStatus: document.getElementById("qrStatus"),
};

const out = (data) => { if (els.output) renderOutput(els.output, data); };

// ── Load endpoint details and populate the UI ──
let endpoint = null;

async function initPortal() {
  if (!endpointId) return;

  try {
    const data = await getJSON("/api/endpoints");
    endpoint = (data.endpoints || []).find(ep => ep.id === endpointId);
  } catch (e) { /* ignore */ }

  if (!endpoint) {
    document.getElementById("portalContent").style.display = "none";
    document.getElementById("noEndpointError").style.display = "block";
    document.getElementById("noEndpointError").querySelector("p").textContent = "This endpoint does not exist or is no longer active.";
    return;
  }

  // Populate header
  document.getElementById("portalEyebrow").textContent = endpoint.developer_name || "API Access";
  document.getElementById("portalTitle").textContent = endpoint.name;
  document.getElementById("portalSubtitle").textContent = endpoint.description || "Register, top up credits, and start calling this API.";

  // Populate banner
  document.getElementById("epBannerName").textContent = endpoint.name;
  document.getElementById("epBannerDesc").textContent = endpoint.description || "";
  document.getElementById("epBannerCost").textContent = `Cost: ${formatCost(endpoint.cost_per_call)} per call`;

  // Populate call section
  document.getElementById("callDescription").textContent =
    `Send a request to ${endpoint.name} — ${formatCost(endpoint.cost_per_call)} per call`;
}

setTimeout(initPortal, 300);


// ── Live XRP cost preview ──
function updateCostPreview() {
  const credits = Number(els.credits.value) || 0;
  const preview = document.getElementById("xrpCostPreview");
  if (preview) {
    preview.textContent = `= ${creditsToXrp(credits)} XRP (rate: ${CREDITS_PER_XRP} credits per XRP)`;
  }
}
if (els.credits) {
  els.credits.addEventListener("input", updateCostPreview);
  setTimeout(updateCostPreview, 500);
}


// ── Sign in ──
document.getElementById("loginBtn")?.addEventListener("click", async () => {
  const data = await postJSON("/api/login", {
    email: els.email.value
  });
  out(data);
  if (data?.user?.apiKey) {
    els.apiKey.value = data.user.apiKey;
    els.name.value = data.user.name;
  }
});

// ── Register ──
document.getElementById("registerBtn")?.addEventListener("click", async () => {
  const data = await postJSON("/api/register", {
    name: els.name.value,
    email: els.email.value
  });
  out(data);
  if (data?.user?.apiKey) els.apiKey.value = data.user.apiKey;
});

// ── Mock top-up ──
document.getElementById("topupBtn")?.addEventListener("click", async () => {
  const data = await postJSON("/api/topup/mock", {
    apiKey: els.apiKey.value,
    credits: Number(els.credits.value)
  });
  out(data);
});

// ── Pay with XRP ──
document.getElementById("payXrpBtn")?.addEventListener("click", async () => {
  els.qrWrap.style.display = "none";
  const data = await postJSON("/api/topup/xrp", {
    apiKey: els.apiKey.value,
    credits: Number(els.credits.value),
    endpointId: endpointId || "",
  });
  out(data);
  if (!data.qrUrl) return;
  els.qrImage.src = data.qrUrl;
  els.qrWrap.style.display = "block";
  els.qrStatus.textContent = "Scan to pay — XRP goes directly to the developer...";
  els.qrStatus.style.color = "";
  pollXamanStatus(data.payloadId, els.qrStatus, els.output, loadBalance);
});

// ── Balance ──
async function loadBalance() {
  const data = await getJSON(`/api/balance/${encodeURIComponent(els.apiKey.value)}`);
  if (data.balance !== undefined) {
    data.balanceInXrp = creditsToXrp(data.balance);
  }
  out(data);
}
document.getElementById("balanceBtn")?.addEventListener("click", loadBalance);

// ── Ledger ──
document.getElementById("ledgerBtn")?.addEventListener("click", async () => {
  const data = await getJSON(`/api/ledger/${encodeURIComponent(els.apiKey.value)}`);
  out(data);

  if (!Array.isArray(data.ledger)) {
    els.ledgerTableWrap.textContent = "No ledger data.";
    return;
  }

  const rows = data.ledger.map(e => `
    <tr>
      <td>${e.created_at}</td>
      <td>${e.reason}</td>
      <td>${e.delta_credits}</td>
      <td><code>${JSON.stringify(e.meta ?? {})}</code></td>
    </tr>
  `).join("");

  els.ledgerTableWrap.innerHTML = `
    <table>
      <thead><tr><th>Created</th><th>Reason</th><th>Delta</th><th>Meta</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="4">No entries.</td></tr>`}</tbody>
    </table>`;
});

// ── Verify ledger integrity ──
document.getElementById("verifyBtn")?.addEventListener("click", async () => {
  const data = await getJSON(`/api/ledger/${encodeURIComponent(els.apiKey.value)}/verify`);
  out(data);

  const el = document.getElementById("verifyResult");
  el.style.display = "block";

  if (data.valid) {
    el.style.background = "rgba(168, 240, 198, 0.1)";
    el.style.border = "1px solid var(--success)";
    el.innerHTML = `
      <strong style="color: var(--success);">Ledger integrity: VALID</strong><br>
      <span class="muted">${data.entries_checked} entries checked. All records are untampered.</span>
    `;
  } else {
    el.style.background = "rgba(255, 159, 159, 0.1)";
    el.style.border = "1px solid var(--danger)";
    el.innerHTML = `
      <strong style="color: var(--danger);">Ledger integrity: BROKEN</strong><br>
      <span class="muted">Tampered entry: ${data.broken_at || "unknown"}. Your records have been modified.</span>
    `;
  }
});

// ── Call endpoint (fixed to the endpoint from the URL) ──
document.getElementById("callBtn")?.addEventListener("click", async () => {
  if (!endpointId) return out({ error: "No endpoint specified" });

  const bodyText = els.callBody.value.trim();
  let body;
  try { body = JSON.parse(bodyText); } catch { body = {}; }

  // Use the old /api/proxy/call route — endpoint is fixed, no path needed
  const data = await postJSON(
    "/api/proxy/call",
    { endpointId: endpointId, payload: body },
    { "x-api-key": els.apiKey.value }
  );
  out(data);
});
