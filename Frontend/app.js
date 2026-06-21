const API_BASE = window.EVIDENCE_REVIEW_API || "";

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const thumbsEl = document.getElementById("thumbs");
const submitBtn = document.getElementById("submitBtn");
const formNote = document.getElementById("formNote");
const serverStatus = document.getElementById("serverStatus");

const ledgerEmpty = document.getElementById("ledgerEmpty");
const ledgerResult = document.getElementById("ledgerResult");
const ledgerError = document.getElementById("ledgerError");

let selectedFiles = [];

// ---------- file handling ----------
function renderThumbs() {
  thumbsEl.innerHTML = "";
  selectedFiles.forEach((file) => {
    const url = URL.createObjectURL(file);
    const div = document.createElement("div");
    div.className = "thumb";
    div.innerHTML = `<img src="${url}" alt="${file.name}" /><span class="thumb__id">${file.name}</span>`;
    thumbsEl.appendChild(div);
  });
}

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  addFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", (e) => addFiles(e.target.files));

function addFiles(fileList) {
  for (const f of fileList) {
    if (f.type.startsWith("image/")) selectedFiles.push(f);
  }
  renderThumbs();
}

// ---------- server health ----------
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    const data = await res.json();
    if (data.model_configured) {
      serverStatus.textContent = "server online · model configured";
      serverStatus.className = "topbar__status ok";
    } else {
      serverStatus.textContent = "server online · ANTHROPIC_API_KEY missing";
      serverStatus.className = "topbar__status bad";
    }
  } catch (e) {
    serverStatus.textContent = "backend not reachable";
    serverStatus.className = "topbar__status bad";
  }
}
checkHealth();

// ---------- submit ----------
submitBtn.addEventListener("click", async () => {
  const claimObject = document.getElementById("claimObject").value;
  const userClaim = document.getElementById("userClaim").value.trim();

  if (!userClaim) {
    formNote.textContent = "Add a claim description before submitting.";
    return;
  }
  if (selectedFiles.length === 0) {
    formNote.textContent = "Attach at least one evidence photo before submitting.";
    return;
  }

  formNote.textContent = "";
  submitBtn.disabled = true;
  submitBtn.querySelector("span").textContent = "Reviewing…";

  const form = new FormData();
  form.append("claim_object", claimObject);
  form.append("user_claim", userClaim);
  selectedFiles.forEach((f) => form.append("files", f));

  try {
    const res = await fetch(`${API_BASE}/api/claims`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Request failed");
    renderVerdict(data);
  } catch (err) {
    showError(err.message || String(err));
  } finally {
    submitBtn.disabled = false;
    submitBtn.querySelector("span").textContent = "Submit for review";
  }
});

function showError(message) {
  ledgerEmpty.hidden = true;
  ledgerResult.hidden = true;
  ledgerError.hidden = false;
  ledgerError.textContent = `Review failed: ${message}`;
}

function stampClassFor(status) {
  if (status === "supported") return "stamp--supported";
  if (status === "contradicted") return "stamp--contradicted";
  return "stamp--insufficient";
}

function renderVerdict(data) {
  ledgerEmpty.hidden = true;
  ledgerError.hidden = true;
  ledgerResult.hidden = false;

  const stamp = document.getElementById("stampBadge");
  stamp.textContent = data.claim_status.replace(/_/g, " ");
  stamp.className = `stamp ${stampClassFor(data.claim_status)}`;

  document.getElementById("rIssueType").textContent = data.issue_type;
  document.getElementById("rObjectPart").textContent = data.object_part;
  document.getElementById("rSeverity").textContent = data.severity;
  document.getElementById("rEvidenceMet").textContent = data.evidence_standard_met ? "true" : "false";
  document.getElementById("rSupportingIds").textContent = data.supporting_image_ids || "none";
  document.getElementById("rRiskFlags").textContent = data.risk_flags || "none";
  document.getElementById("rEvidenceReason").textContent = data.evidence_standard_met_reason || "—";
  document.getElementById("rJustification").textContent = data.claim_status_justification || "—";
  document.getElementById("rLatency").textContent =
    `model latency: ${data.latency_seconds ?? "—"}s · images reviewed: ${(data.image_ids || []).length}`;
}
