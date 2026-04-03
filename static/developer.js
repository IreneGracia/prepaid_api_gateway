/*
  Developer Dashboard UI logic.
  Handles: registration, endpoint management, revenue, usage stats.
*/

const els = {
  devName: document.getElementById("devName"),
  devEmail: document.getElementById("devEmail"),
  devKey: document.getElementById("devKey"),
  epName: document.getElementById("epName"),
  epDesc: document.getElementById("epDesc"),
  epUrl: document.getElementById("epUrl"),
  epXrpCost: document.getElementById("epXrpCost"),
  endpointsList: document.getElementById("endpointsList"),
  revenueInfo: document.getElementById("revenueInfo"),
  usageList: document.getElementById("usageList"),
  output: document.getElementById("output"),
};

const out = (data) => renderOutput(els.output, data);

// ── Copy customer registration link ──
function copyLink(endpointId) {
  const url = `${window.location.origin}/portal/customer?endpoint=${endpointId}`;
  navigator.clipboard.writeText(url).then(() => {
    out({ message: "Link copied to clipboard", url });
  }).catch(() => {
    out({ message: "Copy this link", url });
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
  const data = await postJSON("/api/developer/login", {
    email: els.devEmail.value
  });
  out(data);
  if (data?.developer?.developerKey) {
    els.devKey.value = data.developer.developerKey;
    els.devName.value = data.developer.name;
  }
});

// ── Register ──
document.getElementById("devRegisterBtn").addEventListener("click", async () => {
  const data = await postJSON("/api/developer/register", {
    name: els.devName.value,
    email: els.devEmail.value
  });
  out(data);
  if (data?.developer?.developerKey) {
    els.devKey.value = data.developer.developerKey;
  }
});

// ── Add endpoint ──
document.getElementById("addEndpointBtn").addEventListener("click", async () => {
  const xrp = Number(els.epXrpCost.value) || 0;
  const credits = xrpToCredits(xrp);
  if (credits < 1) {
    return out({ error: "Cost must be at least 1 credit" });
  }
  const data = await postJSON("/api/developer/endpoint", {
    developerKey: els.devKey.value,
    name: els.epName.value,
    description: els.epDesc.value,
    url: els.epUrl.value,
    costPerCall: credits,
  });
  out(data);
});

// ── Load endpoints ──
document.getElementById("loadEndpointsBtn").addEventListener("click", async () => {
  const key = els.devKey.value.trim();
  const data = await getJSON(`/api/developer/${encodeURIComponent(key)}/endpoints`);
  out(data);

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
  out(data);

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
  out(data);

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
  out(data);

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

  const data = await putJSON(`/api/developer/${encodeURIComponent(key)}/security`, settings);
  out(data);
});
