/* Use case: Transfers one private bootstrap credential to the expected local frame.
What it does: Checks source, origin and grant ID; avoids storage, URLs and broad credentials. */
"use strict";

const form = document.getElementById("open-view");
const address = document.getElementById("frame-url");
const secretInput = document.getElementById("bootstrap");
const view = document.getElementById("view");
const status = document.getElementById("status");
let pending = null;
let timeout = null;

function clearView() {
  pending = null;
  window.clearTimeout(timeout);
  timeout = null;
  secretInput.value = "";
  view.replaceChildren();
  view.hidden = true;
}

form.addEventListener("submit", event => {
  event.preventDefault();
  const secret = secretInput.value;
  clearView();
  let url;
  try { url = new URL(address.value); } catch { status.textContent = "Enter a valid local Syntelio frame address."; return; }
  const grant = url.pathname.match(/^\/embed\/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$/)?.[1];
  if (!grant || !["http:", "https:"].includes(url.protocol) || !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) || url.origin === window.location.origin || url.username || url.password || url.search || url.hash) {
    status.textContent = "Use a local /embed/ address on a different origin, without credentials, query or fragment.";
    return;
  }
  if (!/^epb_[A-Za-z0-9_-]{43}$/.test(secret)) {
    status.textContent = "Use a one-use epb_ embed secret. Account tokens and API keys are not accepted.";
    return;
  }
  const frame = document.createElement("iframe");
  frame.title = "Private Syntelio dashboard";
  frame.referrerPolicy = "no-referrer";
  frame.setAttribute("sandbox", "allow-scripts allow-same-origin");
  pending = { frame, origin: url.origin, grant, secret };
  frame.src = url.href;
  view.append(frame);
  view.hidden = false;
  status.textContent = "Waiting for the approved frame to check access…";
  timeout = window.setTimeout(() => {
    clearView();
    status.textContent = "The frame did not respond. Check its address and approved host, then create a new one-use secret.";
  }, 20_000);
});

window.addEventListener("message", event => {
  if (!pending || event.source !== pending.frame.contentWindow || event.origin !== pending.origin || event.data?.type !== "execplus:ready" || event.data.grantId !== pending.grant) return;
  const value = pending;
  pending = null;
  window.clearTimeout(timeout);
  timeout = null;
  value.frame.contentWindow.postMessage({ type: "execplus:open", grantId: value.grant, secret: value.secret }, value.origin);
  status.textContent = "The access request was sent. The dashboard shows the result of its permission check.";
});

document.getElementById("close-view").addEventListener("click", () => {
  clearView();
  address.value = "";
  status.textContent = "View cleared. Create a new one-use secret to open it again.";
});
window.addEventListener("pagehide", clearView);
