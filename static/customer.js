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

// ── Locked sections (greyed out until signed in) ──
const lockedSections = document.querySelectorAll(".locked-section");

function unlockSections() {
  lockedSections.forEach(s => {
    s.style.opacity = "1";
    s.style.pointerEvents = "auto";
  });
}

// Start locked
lockedSections.forEach(s => {
  s.style.opacity = "0.35";
  s.style.pointerEvents = "none";
});

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
    email: els.email.value,
    password: document.getElementById("password").value,
  });
  if (data?.detail) {
    alert(data.detail.error || JSON.stringify(data.detail));
    return;
  }
  out(data);
  if (data?.user?.apiKey) {
    els.apiKey.value = data.user.apiKey;
    els.name.value = data.user.name;
    unlockSections();
  }
});

// ── Register ──
document.getElementById("registerBtn")?.addEventListener("click", async () => {
  const data = await postJSON("/api/register", {
    name: els.name.value,
    email: els.email.value,
    password: document.getElementById("password").value,
  });
  if (data?.detail) {
    alert(data.detail.error || data.detail.details || JSON.stringify(data.detail));
    return;
  }
  out(data);
  if (data?.user?.apiKey) {
    els.apiKey.value = data.user.apiKey;
    unlockSections();
  }
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

// ── Account output (shared area for balance, ledger, verify) ──
function showAccountOutput(html) {
  const el = document.getElementById("accountOutput");
  if (el) el.innerHTML = html;
}

// ── Balance ──
async function loadBalance() {
  const data = await getJSON(`/api/balance/${encodeURIComponent(els.apiKey.value)}`);
  if (data.balance !== undefined) {
    showAccountOutput(`
      <p><strong>Balance: ${formatCost(data.balance)}</strong></p>
    `);
  }
}
document.getElementById("balanceBtn")?.addEventListener("click", loadBalance);

// ── Ledger ──
document.getElementById("ledgerBtn")?.addEventListener("click", async () => {
  const data = await getJSON(`/api/ledger/${encodeURIComponent(els.apiKey.value)}`);

  if (!Array.isArray(data.ledger) || data.ledger.length === 0) {
    showAccountOutput("<p class='muted'>No ledger entries yet.</p>");
    return;
  }

  const rows = data.ledger.map(e => `
    <tr>
      <td>${e.created_at.slice(0,19).replace('T',' ')}</td>
      <td>${e.reason}</td>
      <td>${e.delta_credits}</td>
      <td><code>${JSON.stringify(e.meta ?? {})}</code></td>
      <td><code>${e.hash ? e.hash.slice(0,16) + '...' : '-'}</code></td>
    </tr>
  `).join("");

  showAccountOutput(`
    <div class="table-wrap" style="overflow:auto; max-height:400px;">
      <table>
        <thead><tr><th>Time</th><th>Reason</th><th>Delta</th><th>Meta</th><th>Hash</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `);
});

// ── Verify ledger integrity ──
document.getElementById("verifyBtn")?.addEventListener("click", async () => {
  const data = await getJSON(`/api/ledger/${encodeURIComponent(els.apiKey.value)}/verify`);

  if (data.valid) {
    showAccountOutput(`
      <div style="padding:12px; border-radius:10px; background:rgba(168,240,198,0.1); border:1px solid var(--success);">
        <strong style="color: var(--success);">Ledger integrity: VALID</strong><br>
        <span class="muted">${data.entries_checked} entries checked. All records are untampered.</span>
      </div>
    `);
  } else {
    showAccountOutput(`
      <div style="padding:12px; border-radius:10px; background:rgba(255,159,159,0.1); border:1px solid var(--danger);">
        <strong style="color: var(--danger);">Ledger integrity: BROKEN</strong><br>
        <span class="muted">Tampered entry: ${data.broken_at || "unknown"}. Your records have been modified.</span>
      </div>
    `);
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
