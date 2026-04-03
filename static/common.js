/*
  Shared utility functions used across all portals.
*/

// ── Exchange rate (loaded from server on page load) ──
let CREDITS_PER_XRP = 100;
let XRP_PER_CREDIT = 0.01;

async function loadConfig() {
  try {
    const cfg = await getJSON("/api/config");
    CREDITS_PER_XRP = cfg.creditsPerXrp || 100;
    XRP_PER_CREDIT = cfg.xrpPerCredit || 0.01;
  } catch (e) { /* use defaults */ }
}

function creditsToXrp(credits) {
  return (credits * XRP_PER_CREDIT).toFixed(6);
}

function xrpToCredits(xrp) {
  return Math.floor(xrp * CREDITS_PER_XRP);
}

function formatCost(credits) {
  return `${credits} credits (${creditsToXrp(credits)} XRP)`;
}

// ── Utilities ──

function renderOutput(el, data) {
  el.textContent = JSON.stringify(data, null, 2);
}

async function postJSON(url, body, headers = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers
    },
    body: JSON.stringify(body)
  });
  return response.json();
}

async function putJSON(url, body) {
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  return response.json();
}

async function getJSON(url) {
  const response = await fetch(url);
  return response.json();
}

function pollXamanStatus(payloadId, qrStatus, outputEl, onSuccess) {
  const pollInterval = setInterval(async () => {
    try {
      const status = await getJSON(`/api/topup/xaman/${payloadId}`);
      if (status.signed) {
        clearInterval(pollInterval);
        qrStatus.textContent = "Payment confirmed! Credits added.";
        qrStatus.style.color = "#a8f0c6";
        renderOutput(outputEl, status);
        if (onSuccess) setTimeout(onSuccess, 3000);
      } else if (status.rejected || status.expired) {
        clearInterval(pollInterval);
        qrStatus.textContent = status.expired ? "Expired." : "Rejected.";
        qrStatus.style.color = "#ff9f9f";
        renderOutput(outputEl, status);
      }
    } catch (err) { /* keep polling */ }
  }, 3000);
  setTimeout(() => clearInterval(pollInterval), 300000);
}

// Load config on every page
loadConfig();
