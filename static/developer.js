/*
  Developer Dashboard UI logic.
  Handles: registration, endpoint management, revenue, usage stats, fees, security.
*/

const els = {
  devKey: document.getElementById("devKey"),
  epName: document.getElementById("epName"),
  epDesc: document.getElementById("epDesc"),
  epUrl: document.getElementById("epUrl"),
  epXrpCost: document.getElementById("epXrpCost"),
  endpointsList: document.getElementById("endpointsList"),
  revenueInfo: document.getElementById("revenueInfo"),
  usageList: document.getElementById("usageList"),
};

// ── Locked sections (greyed out until signed in) ──
const lockedSections = document.querySelectorAll(".locked-section");
let currentDevKey = "";

function unlockSections() {
  lockedSections.forEach(s => {
    s.style.opacity = "1";
    s.style.pointerEvents = "auto";
  });
}

function lockSections() {
  lockedSections.forEach(s => {
    s.style.opacity = "0.35";
    s.style.pointerEvents = "none";
  });
}

function showSignedIn(name, email) {
  document.getElementById("modeButtons").style.display = "none";
  document.getElementById("loginForm").style.display = "none";
  document.getElementById("registerForm").style.display = "none";
  document.getElementById("updateXrplForm").style.display = "none";
  document.getElementById("signedInStatus").style.display = "block";
  document.getElementById("signedInMsg").textContent = `Signed in as ${name} (${email})`;
  document.getElementById("accountModeLabel").textContent = "";
}

function showForm(formId) {
  document.getElementById("loginForm").style.display = "none";
  document.getElementById("registerForm").style.display = "none";
  document.getElementById("updateXrplForm").style.display = "none";
  document.getElementById("signedInStatus").style.display = "none";
  document.getElementById(formId).style.display = "block";
}

// Start locked
lockSections();

// ── Mode buttons ──
document.getElementById("showLoginBtn").addEventListener("click", () => {
  showForm("loginForm");
  document.getElementById("accountModeLabel").textContent = "Enter your email to sign in.";
});

document.getElementById("showRegisterBtn").addEventListener("click", () => {
  showForm("registerForm");
  document.getElementById("accountModeLabel").textContent = "Create a new developer account.";
});

document.getElementById("showUpdateXrplBtn").addEventListener("click", () => {
  showForm("updateXrplForm");
  document.getElementById("accountModeLabel").textContent = "Sign in first, then update your XRPL address.";
});

// ── Copy customer registration link ──
function copyLink(endpointId) {
  const url = `${window.location.origin}/portal/customer?endpoint=${endpointId}`;
  navigator.clipboard.writeText(url).then(() => {
    alert("Link copied to clipboard!");
  }).catch(() => {
    prompt("Copy this link:", url);
  });
}

// ── Live credits preview from XRP input ──
function updateDevCostPreview() {
  const xrp = Number(els.epXrpCost.value) || 0;
  const credits = xrpToCredits(xrp);
  const preview = document.getElementById("devCostPreview");
  if (preview) {
    preview.textContent = `= ${credits} credits (rate: ${CREDITS_PER_XRP} credits per XRP)`;
  }
}
els.epXrpCost.addEventListener("input", updateDevCostPreview);
setTimeout(updateDevCostPreview, 500);

// ── Sign in ──
document.getElementById("devLoginBtn").addEventListener("click", async () => {
  const email = document.getElementById("devEmail").value;
  const password = document.getElementById("loginPassword").value;
  const data = await postJSON("/api/developer/login", { email, password });
  if (data?.detail) {
    alert(data.detail.error || JSON.stringify(data.detail));
    return;
  }
  if (data?.developer?.developerKey) {
    currentDevKey = data.developer.developerKey;
    els.devKey.value = currentDevKey;
    showSignedIn(data.developer.name, data.developer.email);
    unlockSections();
  }
});

// ── Register ──
document.getElementById("devRegisterBtn").addEventListener("click", async () => {
  const data = await postJSON("/api/developer/register", {
    name: document.getElementById("regUsername").value,
    email: document.getElementById("devEmailReg").value,
    password: document.getElementById("regPassword").value,
    xrplAddress: document.getElementById("devXrplAddress").value,
  });
  if (data?.detail) {
    alert(data.detail.error || data.detail.details || JSON.stringify(data.detail));
    return;
  }
  if (data?.developer?.developerKey) {
    currentDevKey = data.developer.developerKey;
    els.devKey.value = currentDevKey;
    showSignedIn(data.developer.name, data.developer.email);
    unlockSections();
  }
});

// ── Add endpoint ──
document.getElementById("addEndpointBtn").addEventListener("click", async () => {
  const xrp = Number(els.epXrpCost.value) || 0;
  const credits = xrpToCredits(xrp);
  if (credits < 1) {
    alert("Cost must be at least 1 credit. Check the XRP amount.");
    return;
  }
  const data = await postJSON("/api/developer/endpoint", {
    developerKey: els.devKey.value,
    name: els.epName.value,
    description: els.epDesc.value,
    url: els.epUrl.value,
    costPerCall: credits,
  });
  if (data.error || data.detail) {
    alert(JSON.stringify(data.detail || data.error));
  } else {
    // Auto-reload endpoints after adding
    document.getElementById("loadEndpointsBtn").click();
  }
});

// ── Load endpoints ──
document.getElementById("loadEndpointsBtn").addEventListener("click", async () => {
  const key = els.devKey.value.trim();
  const data = await getJSON(`/api/developer/${encodeURIComponent(key)}/endpoints`);

  if (!data.endpoints || data.endpoints.length === 0) {
    els.endpointsList.innerHTML = "<p class='muted'>No endpoints yet.</p>";
    return;
  }

  const rows = data.endpoints.map(ep => `
    <tr>
      <td><strong>${ep.name}</strong></td>
      <td style="font-size:12px;">${ep.url}</td>
      <td>${creditsToXrp(ep.cost_per_call)} XRP <span class="muted">(${ep.cost_per_call} credits)</span></td>
      <td>${ep.is_active ? "Active" : "Inactive"}</td>
      <td>
        <button onclick="copyLink('${ep.id}')" style="margin:0; width:auto; padding:6px 10px; font-size:12px;">Copy link</button>
      </td>
    </tr>
  `).join("");

  els.endpointsList.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>URL</th><th>Price per call</th><th>Status</th><th>Share</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
});

// ── Revenue ──
document.getElementById("revenueBtn").addEventListener("click", async () => {
  const key = els.devKey.value.trim();
  const data = await getJSON(`/api/developer/${encodeURIComponent(key)}/revenue`);

  // Clear other sections
  els.usageList.innerHTML = "";
  if (data.totalRevenue !== undefined) {
    let html = `<p><strong>Total revenue: ${formatCost(data.totalRevenue)}</strong></p>`;
    if (data.endpoints && data.endpoints.length > 0) {
      const rows = data.endpoints.map(ep => `
        <tr><td>${ep.name}</td><td>${ep.call_count}</td><td>${formatCost(ep.total_revenue)}</td></tr>
      `).join("");
      html += `<table><thead><tr><th>Endpoint</th><th>Calls</th><th>Revenue</th></tr></thead><tbody>${rows}</tbody></table>`;
    }
    els.revenueInfo.innerHTML = html;
  }
});

// ── Usage ──
document.getElementById("usageBtn").addEventListener("click", async () => {
  const key = els.devKey.value.trim();
  const data = await getJSON(`/api/developer/${encodeURIComponent(key)}/usage`);

  // Clear other sections
  els.revenueInfo.innerHTML = "";
  if (!data.calls || data.calls.length === 0) {
    els.usageList.innerHTML = "<p class='muted'>No calls yet.</p>";
    return;
  }

  const rows = data.calls.map(c => `
    <tr><td>${c.created_at}</td><td>${c.endpoint_name}</td><td>${c.user_name}</td><td>${formatCost(c.cost)}</td></tr>
  `).join("");

  els.usageList.innerHTML = `
    <table><thead><tr><th>Time</th><th>Endpoint</th><th>Customer</th><th>Cost</th></tr></thead><tbody>${rows}</tbody></table>`;
});

// ── Save XRPL address (sign in by email first, then update) ──
document.getElementById("saveXrplBtn").addEventListener("click", async () => {
  const email = document.getElementById("updateEmail").value;
  const password = document.getElementById("updatePassword").value;
  const newAddress = document.getElementById("newXrplAddress").value.trim();

  // Sign in first to get the key
  const loginData = await postJSON("/api/developer/login", { email, password });
  if (!loginData?.developer?.developerKey) return;

  const key = loginData.developer.developerKey;
  currentDevKey = key;
  els.devKey.value = key;

  // Update the address
  await putJSON(`/api/developer/${encodeURIComponent(key)}/xrpl-address`, {
    xrplAddress: newAddress,
  });

  showSignedIn(loginData.developer.name, loginData.developer.email);
  unlockSections();
});


// ── Security settings ──
const secEls = {
  rateLimitPerKey: document.getElementById("secRateLimitPerKey"),
  rateLimitPerIp: document.getElementById("secRateLimitPerIp"),
  rateLimitWindow: document.getElementById("secRateLimitWindow"),
  ddosBurst: document.getElementById("secDdosBurst"),
  ddosWindow: document.getElementById("secDdosWindow"),
  ddosCooldown: document.getElementById("secDdosCooldown"),
  ipWhitelist: document.getElementById("secIpWhitelist"),
  ipBlacklist: document.getElementById("secIpBlacklist"),
  bruteForceThreshold: document.getElementById("secBruteForceThreshold"),
  bruteForceWindow: document.getElementById("secBruteForceWindow"),
  bruteForceBlock: document.getElementById("secBruteForceBlock"),
  maxBodySize: document.getElementById("secMaxBodySize"),
};

document.getElementById("loadSecurityBtn").addEventListener("click", async () => {
  const key = els.devKey.value.trim();
  const data = await getJSON(`/api/developer/${encodeURIComponent(key)}/security`);

  if (data.rateLimitPerKey !== undefined) {
    document.getElementById("securityForm").style.display = "block";
    secEls.rateLimitPerKey.value = data.rateLimitPerKey;
    secEls.rateLimitPerIp.value = data.rateLimitPerIp;
    secEls.rateLimitWindow.value = data.rateLimitWindowSeconds;
    secEls.ddosBurst.value = data.ddosBurstThreshold;
    secEls.ddosWindow.value = data.ddosBurstWindowSeconds;
    secEls.ddosCooldown.value = data.ddosCooldownSeconds;
    secEls.ipWhitelist.value = (data.ipWhitelist || []).join(", ");
    secEls.ipBlacklist.value = (data.ipBlacklist || []).join(", ");
    secEls.bruteForceThreshold.value = data.bruteForceThreshold;
    secEls.bruteForceWindow.value = data.bruteForceWindowSeconds;
    secEls.bruteForceBlock.value = data.bruteForceBlockSeconds;
    secEls.maxBodySize.value = data.maxBodySize;
  }
});

document.getElementById("saveSecurityBtn").addEventListener("click", async () => {
  const key = els.devKey.value.trim();
  const settings = {
    rateLimitPerKey: Number(secEls.rateLimitPerKey.value),
    rateLimitPerIp: Number(secEls.rateLimitPerIp.value),
    rateLimitWindowSeconds: Number(secEls.rateLimitWindow.value),
    ddosBurstThreshold: Number(secEls.ddosBurst.value),
    ddosBurstWindowSeconds: Number(secEls.ddosWindow.value),
    ddosCooldownSeconds: Number(secEls.ddosCooldown.value),
    ipWhitelist: secEls.ipWhitelist.value.split(",").map(s => s.trim()).filter(Boolean),
    ipBlacklist: secEls.ipBlacklist.value.split(",").map(s => s.trim()).filter(Boolean),
    bruteForceThreshold: Number(secEls.bruteForceThreshold.value),
    bruteForceWindowSeconds: Number(secEls.bruteForceWindow.value),
    bruteForceBlockSeconds: Number(secEls.bruteForceBlock.value),
    maxBodySize: Number(secEls.maxBodySize.value),
  };

  await putJSON(`/api/developer/${encodeURIComponent(key)}/security`, settings);
  document.getElementById("securityForm").style.display = "none";
});
