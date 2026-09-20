// ==========================================================================
// Candidate Screening Queue & Resumes Ingestion View
// ==========================================================================

const candidatesView = {
  currentJobId: null,
  candidates: [],

  async render(params = {}) {
    const container = document.getElementById("main-view");
    if (!container) return;

    this.currentJobId = params.jobId || appState.activeJobId || null;

    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2rem; flex-wrap: wrap; gap: 1rem;">
        <div>
          <h1 style="font-size: 1.85rem; margin-bottom: 0.25rem;">Candidate Screening Queue</h1>
          <p style="color: var(--text-secondary);">Evidence coverage, capability claims, and recruiter shortlist decisions.</p>
        </div>
        <div style="display: flex; gap: 0.75rem; align-items: center;">
          <div style="min-width: 200px;">
            <select class="form-select" id="candidate-job-filter" onchange="candidatesView.onJobFilterChange(this.value)">
              <option value="">All Job Positions</option>
            </select>
          </div>
          <button class="btn btn-primary" onclick="candidatesView.triggerLoadResumesModal(candidatesView.currentJobId)">
            <span>📥</span> Load New Resumes
          </button>
        </div>
      </div>

      <div class="card" style="padding: 0; overflow: hidden;">
        <div id="candidates-table-container">
          <p style="color: var(--text-muted); padding: 3rem; text-align: center;">Loading candidates...</p>
        </div>
      </div>
    `;

    await this.loadJobsFilter();
    await this.loadCandidates();
  },

  async loadJobsFilter() {
    try {
      const jobs = await api.jobs.list();
      const selectEl = document.getElementById("candidate-job-filter");
      if (!selectEl) return;

      selectEl.innerHTML = `<option value="">All Job Positions (${jobs.length})</option>`;
      jobs.forEach((j) => {
        const selected = j.id === this.currentJobId ? "selected" : "";
        selectEl.innerHTML += `<option value="${j.id}" ${selected}>${j.title}</option>`;
      });
    } catch (e) {
      console.warn("Could not load jobs filter:", e);
    }
  },

  async onJobFilterChange(jobId) {
    this.currentJobId = jobId || null;
    appState.activeJobId = this.currentJobId;
    await this.loadCandidates();
  },

  async loadCandidates() {
    const tableContainer = document.getElementById("candidates-table-container");
    if (!tableContainer) return;

    try {
      let candidateList = [];

      if (this.currentJobId) {
        candidateList = await api.screening.listJobCandidates(this.currentJobId);
      } else {
        // Fetch candidates across all jobs
        const jobs = await api.jobs.list();
        for (const job of jobs) {
          try {
            const list = await api.screening.listJobCandidates(job.id);
            candidateList.push(...list);
          } catch (e) {
            // Ignore empty
          }
        }
      }

      this.candidates = candidateList;

      if (!candidateList || candidateList.length === 0) {
        tableContainer.innerHTML = `
          <div style="text-align: center; padding: 4rem 2rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">👥</div>
            <h3 style="margin-bottom: 0.5rem;">No candidates in queue</h3>
            <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">Click 'Load New Resumes' to synchronize and screen incoming email applications.</p>
            <button class="btn btn-primary" onclick="candidatesView.triggerLoadResumesModal('${this.currentJobId || ""}')">
              📥 Load New Resumes
            </button>
          </div>
        `;
        return;
      }

      let html = `
        <table class="data-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Job Position</th>
              <th>Evidence Coverage</th>
              <th>Eligibility</th>
              <th>Screening Status</th>
              <th>Shortlist Status</th>
              <th style="text-align: right;">Action</th>
            </tr>
          </thead>
          <tbody>
      `;

      for (const cand of candidateList) {
        const knownCount = cand.known_capabilities ? cand.known_capabilities.length : 0;
        const unknownCount = cand.unknown_capabilities ? cand.unknown_capabilities.length : 0;
        const total = knownCount + unknownCount;

        // Eligibility Pill
        let eligBadge = `<span class="badge badge-warning">Needs Review</span>`;
        if (cand.eligibility_status === "ELIGIBLE") {
          eligBadge = `<span class="badge badge-success"><span class="badge-dot"></span> Eligible</span>`;
        } else if (cand.eligibility_status === "NOT_ELIGIBLE") {
          eligBadge = `<span class="badge badge-danger">Not Eligible</span>`;
        }

        // Shortlist Badge
        let shortBadge = `<span class="badge badge-neutral">Pending</span>`;
        if (cand.shortlist_status === "SHORTLISTED") {
          shortBadge = `<span class="badge badge-success">⭐ Shortlisted</span>`;
        } else if (cand.shortlist_status === "NOT_SHORTLISTED") {
          shortBadge = `<span class="badge badge-danger">Not Shortlisted</span>`;
        } else if (cand.shortlist_status === "HOLD") {
          shortBadge = `<span class="badge badge-warning">Hold</span>`;
        }

        html += `
          <tr>
            <td>
              <div style="font-weight: 700; color: var(--text-primary); cursor: pointer;" onclick="router.navigate('candidate-detail', { id: '${cand.application_id}' })">
                ${cand.candidate_name || "Applicant"}
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">${cand.candidate_email}</div>
            </td>
            <td>
              <span style="font-weight: 600; color: var(--text-secondary); font-size: 0.875rem;">
                ${cand.job_title || "General Application"}
              </span>
            </td>
            <td>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-weight: 700; color: var(--primary-light);">${knownCount}/${total}</span>
                <span style="font-size: 0.75rem; color: var(--text-muted);">claims</span>
                ${
                  unknownCount > 0
                    ? `<span style="font-size: 0.75rem; color: #FBBF24;">(${unknownCount} unknown)</span>`
                    : ""
                }
              </div>
            </td>
            <td>${eligBadge}</td>
            <td>
              <span class="badge badge-info">${cand.screening_status || "SCREENING"}</span>
            </td>
            <td>${shortBadge}</td>
            <td style="text-align: right;">
              <button class="btn btn-secondary btn-sm" onclick="router.navigate('candidate-detail', { id: '${cand.application_id}' })">
                View Candidate →
              </button>
            </td>
          </tr>
        `;
      }

      html += `</tbody></table>`;
      tableContainer.innerHTML = html;
    } catch (err) {
      toast.error(`Failed to load candidates: ${err.message}`);
    }
  },

  triggerLoadResumesModal(targetJobId = null) {
    modal.open(`
      <div class="modal-header">
        <h3 class="modal-title">📥 Load New Resumes (Bounded Ingestion)</h3>
        <button class="btn btn-outline btn-sm" onclick="modal.close()">✕</button>
      </div>
      <div>
        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.5rem;">
          Gap2Hire will fetch a bounded batch of incoming emails from the configured inbox, classify attachments, extract resume evidence, and prepare candidates for screening with full idempotency.
        </p>
        
        <div class="form-group">
          <label class="form-label" for="sync-limit">Batch Size Limit (Max emails to fetch)</label>
          <select class="form-select" id="sync-limit">
            <option value="5">5 emails (Fast Smoke Test)</option>
            <option value="10" selected>10 emails (Standard Batch)</option>
            <option value="20">20 emails</option>
          </select>
        </div>

        <div id="sync-progress-area" style="display: none; margin: 1.5rem 0; padding: 1.25rem; background: var(--bg-surface-elevated); border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
          <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div style="font-size: 1.2rem; animation: spin 1.5s linear infinite;">⏳</div>
            <div style="font-weight: 600; font-size: 0.9rem; color: var(--text-primary);" id="sync-status-msg">
              Fetching emails from inbox...
            </div>
          </div>
          <div style="font-size: 0.8rem; color: var(--text-secondary);">
            Classifying attachments • Extracting resume claims • Running evidence analysis...
          </div>
        </div>

        <div id="sync-result-area" style="display: none; margin: 1.5rem 0;"></div>

        <div class="modal-footer" id="sync-modal-footer">
          <button type="button" class="btn btn-outline" onclick="modal.close()">Cancel</button>
          <button type="button" class="btn btn-primary" id="btn-start-sync" onclick="candidatesView.executeResumeSync('${targetJobId || ""}')">
            Start Ingestion
          </button>
        </div>
      </div>
    `);
  },

  async executeResumeSync(targetJobId) {
    const limit = parseInt(document.getElementById("sync-limit").value, 10) || 10;
    const startBtn = document.getElementById("btn-start-sync");
    const progressArea = document.getElementById("sync-progress-area");
    const resultArea = document.getElementById("sync-result-area");
    const footer = document.getElementById("sync-modal-footer");

    if (startBtn) startBtn.disabled = true;
    if (progressArea) progressArea.style.display = "block";
    if (resultArea) resultArea.style.display = "none";

    try {
      const res = await api.email.loadNewResumes(limit, targetJobId || null);

      if (progressArea) progressArea.style.display = "none";
      if (resultArea) {
        resultArea.style.display = "block";
        resultArea.innerHTML = `
          <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-md); padding: 1.25rem;">
            <h4 style="color: #34D399; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem;">
              <span>✅</span> Batch Ingestion Completed
            </h4>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.75rem; font-size: 0.875rem;">
              <div><strong>Emails Fetched:</strong> ${res.emails_fetched}</div>
              <div><strong>Candidate Applications:</strong> <span style="color: #6EE7B7; font-weight: 700;">${res.candidate_emails}</span></div>
              <div><strong>Resumes Processed:</strong> ${res.resumes_processed}</div>
              <div><strong>Duplicates Skipped:</strong> ${res.duplicates_skipped}</div>
              <div><strong>Irrelevant / Spam:</strong> ${res.irrelevant_emails}</div>
              <div><strong>Flagged for Review:</strong> ${res.possible_applications}</div>
            </div>
          </div>
        `;
      }

      if (footer) {
        footer.innerHTML = `
          <button type="button" class="btn btn-primary" onclick="modal.close(); candidatesView.loadCandidates();">
            View Screening Queue
          </button>
        `;
      }

      toast.success(`Processed ${res.candidate_emails} candidate resumes (${res.duplicates_skipped} duplicates skipped).`);
    } catch (err) {
      if (progressArea) progressArea.style.display = "none";
      toast.error(`Sync error: ${err.message}`);
      if (startBtn) {
        startBtn.disabled = false;
        startBtn.textContent = "Try Again";
      }
    }
  },
};
