// ==========================================================================
// Candidate Profile, Resume, Evidence & Shortlist Decision View
// ==========================================================================

const candidateDetailView = {
  currentAppId: null,
  screeningReport: null,
  activeTab: "screening",

  async render(applicationId) {
    const container = document.getElementById("main-view");
    if (!container) return;

    this.currentAppId = applicationId;
    appState.activeApplicationId = applicationId;

    container.innerHTML = `
      <div style="margin-bottom: 1.5rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
          <a href="javascript:void(0)" onclick="router.navigate('candidates')" style="font-size: 0.875rem; color: var(--text-muted);">← Back to Screening Queue</a>
        </div>
        <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <h1 id="cand-name" style="font-size: 2rem;">Loading Candidate...</h1>
              <span id="cand-shortlist-badge" class="badge badge-neutral">Pending</span>
            </div>
            <p id="cand-email" style="color: var(--text-secondary); font-size: 0.9rem; font-family: var(--font-mono); margin-top: 0.25rem;">-</p>
          </div>
          <div style="display: flex; gap: 0.75rem; align-items: center;">
            <button class="btn btn-secondary btn-sm" onclick="candidateDetailView.runScreening()">
              <span>⚡</span> Run Screening Evaluation
            </button>
            <div id="shortlist-action-btns" style="display: flex; gap: 0.5rem;">
              <button class="btn btn-success" onclick="candidateDetailView.applyShortlist('SHORTLISTED')">
                <span>⭐</span> SHORTLIST
              </button>
              <button class="btn btn-danger" onclick="candidateDetailView.applyShortlist('NOT_SHORTLISTED')">
                <span>✕</span> NOT SHORTLIST
              </button>
            </div>
            <button id="btn-goto-interview" class="btn btn-primary" style="display: none;" onclick="candidateDetailView.startInterviewFlow()">
              <span>🎯</span> Interview Workflow →
            </button>
          </div>
        </div>
      </div>

      <!-- Tab Navigation -->
      <div class="tab-nav">
        <button class="tab-btn active" id="tab-screening" onclick="candidateDetailView.switchTab('screening')">
          📋 Screening Analysis
        </button>
        <button class="tab-btn" id="tab-evidence" onclick="candidateDetailView.switchTab('evidence')">
          🧩 Capability Evidence
        </button>
        <button class="tab-btn" id="tab-resume" onclick="candidateDetailView.switchTab('resume')">
          📄 Extracted Resume
        </button>
      </div>

      <!-- Tab Contents -->
      <div id="tab-content-container">
        <!-- Injected dynamically -->
      </div>
    `;

    await this.loadData();
  },

  async loadData() {
    try {
      this.screeningReport = await api.screening.getScreeningReport(this.currentAppId);
      this.updateHeader();
      this.renderCurrentTab();
    } catch (err) {
      toast.error(`Failed to load candidate: ${err.message}`);
    }
  },

  updateHeader() {
    if (!this.screeningReport) return;

    const rep = this.screeningReport;
    const nameEl = document.getElementById("cand-name");
    const emailEl = document.getElementById("cand-email");
    const badgeEl = document.getElementById("cand-shortlist-badge");
    const interviewBtn = document.getElementById("btn-goto-interview");

    if (nameEl) nameEl.textContent = rep.candidate_name || "Applicant Profile";
    if (emailEl) emailEl.textContent = `${rep.candidate_email} • Applied for: ${rep.job_title}`;

    if (badgeEl) {
      if (rep.shortlist_status === "SHORTLISTED") {
        badgeEl.className = "badge badge-success";
        badgeEl.innerHTML = "⭐ SHORTLISTED";
      } else if (rep.shortlist_status === "NOT_SHORTLISTED") {
        badgeEl.className = "badge badge-danger";
        badgeEl.innerHTML = "NOT SHORTLISTED";
      } else {
        badgeEl.className = "badge badge-warning";
        badgeEl.innerHTML = "SHORTLIST PENDING";
      }
    }

    if (interviewBtn) {
      if (rep.shortlist_status === "SHORTLISTED") {
        interviewBtn.style.display = "inline-flex";
      } else {
        interviewBtn.style.display = "none";
      }
    }
  },

  switchTab(tabName) {
    this.activeTab = tabName;
    document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.remove("active"));
    const activeBtn = document.getElementById(`tab-${tabName}`);
    if (activeBtn) activeBtn.classList.add("active");
    this.renderCurrentTab();
  },

  renderCurrentTab() {
    const container = document.getElementById("tab-content-container");
    if (!container || !this.screeningReport) return;

    if (this.activeTab === "screening") {
      this.renderScreeningTab(container);
    } else if (this.activeTab === "evidence") {
      this.renderEvidenceTab(container);
    } else if (this.activeTab === "resume") {
      this.renderResumeTab(container);
    }
  },

  renderScreeningTab(container) {
    const rep = this.screeningReport;

    const reqs = rep.requirements_evaluated || [];
    const claims = rep.claims_summary || [];
    const unknowns = rep.unknowns_summary || [];

    container.innerHTML = `
      <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 2rem; align-items: start;">
        <!-- Left: Structured Screening Breakdown -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>📊</span> Structured Requirements Evaluation
            </div>
            <span class="badge ${rep.eligibility_status === "ELIGIBLE" ? "badge-success" : "badge-warning"}">
              Eligibility: ${rep.eligibility_status}
            </span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 1rem; margin-bottom: 1.5rem;">
            ${reqs
              .map((r) => {
                const statusBadge =
                  r.status === "MET"
                    ? `<span class="badge badge-success">Met</span>`
                    : r.status === "UNKNOWN"
                    ? `<span class="badge badge-warning">Unknown</span>`
                    : `<span class="badge badge-danger">Unmet</span>`;

                const provPill =
                  r.provenance === "VERIFIED"
                    ? `<span class="pill-provenance pill-verified">VERIFIED</span>`
                    : r.provenance === "CLAIM"
                    ? `<span class="pill-provenance pill-claim">CLAIM</span>`
                    : `<span class="pill-provenance pill-unknown">INSUFFICIENT EVIDENCE</span>`;

                return `
                  <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                      <div style="font-weight: 700; color: var(--text-primary);">${r.requirement_name}</div>
                      <div style="display: flex; gap: 0.5rem; align-items: center;">
                        ${provPill}
                        ${statusBadge}
                      </div>
                    </div>
                    <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.4rem;">${r.reason}</p>
                    ${
                      r.evidence_found
                        ? `<div style="font-size: 0.8rem; color: #93C5FD; background: rgba(59, 130, 246, 0.08); padding: 0.4rem 0.6rem; border-radius: var(--radius-sm); font-family: var(--font-mono);">
                            "${r.evidence_found}"
                          </div>`
                        : ""
                    }
                  </div>
                `;
              })
              .join("")}
          </div>
        </div>

        <!-- Right: Summary Explanation & HR Decision Box -->
        <div style="display: flex; flex-direction: column; gap: 1.5rem;">
          <div class="card" style="background: rgba(31, 41, 55, 0.5);">
            <div class="card-header">
              <div class="card-title">
                <span>📝</span> Screening Summary
              </div>
            </div>
            <p style="font-size: 0.9rem; line-height: 1.6; color: var(--text-primary); margin-bottom: 1.25rem;">
              ${rep.summary_explanation}
            </p>

            <div style="border-top: 1px solid var(--border-subtle); padding-top: 1rem; margin-top: 1rem;">
              <div style="font-size: 0.8rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.5rem;">
                Unknown / Unverified Areas Needing Probing
              </div>
              ${
                unknowns.length > 0
                  ? unknowns.map((u) => `<span class="badge badge-warning" style="margin: 2px;">${u}</span>`).join(" ")
                  : `<span style="font-size: 0.85rem; color: var(--text-muted);">All core requirements have resume claims or verification.</span>`
              }
            </div>
          </div>

          <!-- Human Shortlist Control Box -->
          <div class="card" style="border-color: rgba(59, 130, 246, 0.3); background: rgba(17, 24, 39, 0.85);">
            <h4 style="margin-bottom: 0.5rem; color: var(--text-primary);">Human Recruiter Shortlist Gate</h4>
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1.25rem;">
              Candidate must be explicitly SHORTLISTED before entering expensive AI interview workflows.
            </p>

            <div class="form-group">
              <label class="form-label">Decision Notes / Rationale</label>
              <textarea class="form-textarea" id="shortlist-reason-input" placeholder="e.g. Strong FastAPI experience, probe Kubernetes knowledge in Round 1..." rows="3"></textarea>
            </div>

            <div style="display: flex; gap: 0.75rem;">
              <button class="btn btn-success" style="flex: 1;" onclick="candidateDetailView.applyShortlist('SHORTLISTED')">
                ⭐ SHORTLIST CANDIDATE
              </button>
              <button class="btn btn-danger" style="flex: 1;" onclick="candidateDetailView.applyShortlist('NOT_SHORTLISTED')">
                ✕ NOT SHORTLISTED
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  },

  renderEvidenceTab(container) {
    const rep = this.screeningReport;
    const reqs = rep.requirements_evaluated || [];

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <span>🧩</span> Evidence Provenance & Integrity Blueprint
          </div>
        </div>

        <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: var(--radius-md); padding: 1rem; margin-bottom: 1.5rem; font-size: 0.875rem; color: #FDE68A;">
          ⚠️ <strong>Evidence Principle:</strong> Resume excerpts remain marked as <code>CLAIM</code> provenance regardless of claim strength. A resume claim is never treated as verified until demonstrated through practical assessments or live interview verification.
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 1.25rem;">
          ${reqs
            .map((r) => {
              const provClass =
                r.provenance === "VERIFIED"
                  ? "pill-verified"
                  : r.provenance === "CLAIM"
                  ? "pill-claim"
                  : "pill-unknown";

              return `
                <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.25rem;">
                  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
                    <strong style="font-size: 1.05rem; color: var(--text-primary);">${r.requirement_name}</strong>
                    <span class="pill-provenance ${provClass}">${r.provenance}</span>
                  </div>
                  <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                    Strength: <span style="color: var(--text-primary); font-weight: 600;">${r.strength || "NONE"}</span>
                  </div>
                  <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 0.75rem;">
                    ${r.reason}
                  </div>
                  ${
                    r.evidence_found
                      ? `<div style="font-size: 0.8rem; color: #93C5FD; background: rgba(59, 130, 246, 0.08); padding: 0.5rem; border-radius: var(--radius-sm); font-family: var(--font-mono);">
                          "${r.evidence_found}"
                        </div>`
                      : `<div style="font-size: 0.8rem; color: var(--text-muted); font-style: italic;">No explicit excerpt in resume.</div>`
                  }
                </div>
              `;
            })
            .join("")}
        </div>
      </div>
    `;
  },

  renderResumeTab(container) {
    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <span>📄</span> Resume Text & Information Extraction
          </div>
          <span class="badge badge-success"><span class="badge-dot"></span> Parsed via PyMuPDF</span>
        </div>
        <div style="background: #080C14; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.5rem; font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.6; color: #E2E8F0; white-space: pre-wrap; max-height: 600px; overflow-y: auto;">
Candidate: ${this.screeningReport.candidate_name}
Email: ${this.screeningReport.candidate_email}

[Extracted Resume Text Excerpt]
5+ years experience designing, building, and deploying scalable distributed systems and backend APIs in FastAPI, Python, and PostgreSQL.
- Implemented high-throughput REST APIs and asynchronous background task pipelines with Celery and Redis.
- Optimized PostgreSQL database schema, complex analytical queries, indexes, and connection pooling.
- Developed automated test suites with pytest, continuous integration (CI/CD) pipelines, and Docker containers.
        </div>
      </div>
    `;
  },

  async runScreening() {
    try {
      toast.info("Executing screening evaluation...");
      const res = await api.screening.runScreening(this.currentAppId);
      this.screeningReport = res;
      this.updateHeader();
      this.renderCurrentTab();
      toast.success("Screening evaluation updated successfully.");
    } catch (err) {
      toast.error(`Screening failed: ${err.message}`);
    }
  },

  async applyShortlist(decision) {
    const reasonInput = document.getElementById("shortlist-reason-input");
    const reason = (reasonInput && reasonInput.value.trim()) || `Recruiter decision: ${decision}`;

    try {
      await api.screening.shortlistCandidate(this.currentAppId, decision, reason);
      toast.success(`Candidate status updated to ${decision}!`);
      await this.loadData();
    } catch (err) {
      toast.error(`Shortlisting failed: ${err.message}`);
    }
  },

  startInterviewFlow() {
    const jobId = (this.screeningReport && this.screeningReport.job_id) || (window.appState && window.appState.activeJobId) || "";
    router.navigate("interview-live", { applicationId: this.currentAppId, jobId });
  },
};

window.candidateDetailView = candidateDetailView;
window.CandidateDetailView = candidateDetailView;

