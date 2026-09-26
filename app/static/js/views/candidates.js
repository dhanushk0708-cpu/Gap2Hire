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
        <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
          <div style="min-width: 200px;">
            <select class="form-select" id="candidate-job-filter" onchange="candidatesView.onJobFilterChange(this.value)">
              <option value="">All Job Positions</option>
            </select>
          </div>
          <div id="screening-shortlist-limit-box" style="display: flex; align-items: center; gap: 0.4rem; background: var(--bg-surface); padding: 0.35rem 0.65rem; border-radius: var(--radius-md); border: 1px solid var(--border-color);">
            <label for="candidate-shortlist-limit" style="font-size: 0.85rem; color: var(--text-secondary); font-weight: 600; white-space: nowrap;">Shortlist Limit:</label>
            <input type="number" id="candidate-shortlist-limit" min="1" max="100" value="5" style="width: 55px; padding: 0.2rem 0.4rem; font-size: 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-surface-elevated); color: var(--text-primary); text-align: center;" onchange="candidatesView.saveShortlistLimit(this.value)" title="Configure maximum candidates to shortlist" />
          </div>
          <button class="btn btn-primary" onclick="candidatesView.triggerLoadResumesModal(candidatesView.currentJobId)">
            <span>📥</span> Load New Resumes
          </button>
          <button class="btn btn-secondary" style="border: 1px dashed #A855F7; color: #7E22CE; background: #FAF5FF; font-weight: 600;" onclick="candidatesView.openDemoZipModal()" title="Import synthetic candidate resumes ZIP for screening validation">
            <span>🧪</span> Import Demo Resume ZIP
          </button>
          <button class="btn btn-secondary" id="btn-run-screening" onclick="candidatesView.runJobScreening()">
            <span>⚡</span> Run Automated Screening
          </button>
          <button class="btn btn-primary" style="background: #0284C7; border: 1px solid #0369A1; font-weight: 600;" onclick="candidatesView.openBatchInterviewModal()" title="Start concurrent independent interview sessions for shortlisted candidates">
            <span>👥</span> Batch Interviews
          </button>
        </div>
      </div>

      <div id="top-n-banner-container"></div>

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
      this.jobsList = jobs || [];
      const selectEl = document.getElementById("candidate-job-filter");
      if (!selectEl) return;

      selectEl.innerHTML = `<option value="">All Job Positions (${this.jobsList.length})</option>`;
      this.jobsList.forEach((j) => {
        const selected = j.id === this.currentJobId ? "selected" : "";
        selectEl.innerHTML += `<option value="${j.id}" ${selected}>${j.title}</option>`;
      });
      this.syncShortlistLimitUI();
    } catch (e) {
      console.warn("Could not load jobs filter:", e);
    }
  },

  syncShortlistLimitUI() {
    const inputEl = document.getElementById("candidate-shortlist-limit");
    if (!inputEl) return;
    if (this.currentJobId && this.jobsList) {
      const j = this.jobsList.find((item) => item.id === this.currentJobId);
      inputEl.value = (j && j.shortlist_size) ? j.shortlist_size : 5;
      inputEl.disabled = false;
      inputEl.title = "Configure maximum shortlist size for this job";
    } else {
      inputEl.disabled = true;
      inputEl.value = 5;
      inputEl.title = "Select a specific job position to set shortlist limit";
    }
  },

  async saveShortlistLimit(val) {
    if (!this.currentJobId) {
      toast.info("Please select a specific job position to configure shortlist limit.");
      return;
    }
    const num = parseInt(val, 10);
    if (isNaN(num) || num < 1) {
      toast.error("Shortlist limit must be at least 1.");
      return;
    }
    try {
      await api.screening.updateShortlistSize(this.currentJobId, num);
      if (this.jobsList) {
        const j = this.jobsList.find((item) => item.id === this.currentJobId);
        if (j) j.shortlist_size = num;
      }
      toast.success(`Shortlist limit updated to ${num}.`);
    } catch (err) {
      toast.error(`Failed to update shortlist limit: ${err.message}`);
    }
  },

  async onJobFilterChange(jobId) {
    this.currentJobId = jobId || null;
    appState.activeJobId = this.currentJobId;
    this.syncShortlistLimitUI();
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
              <div style="font-weight: 700; color: var(--text-primary); cursor: pointer; display: flex; align-items: center; gap: 0.35rem;" onclick="router.navigate('candidate-detail', { id: '${cand.application_id}' })">
                <span>${cand.candidate_name || "Applicant"}</span>
                ${cand.is_demo ? `<span style="display: inline-flex; align-items: center; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.65rem; font-weight: 700; background: #F3E8FF; color: #7E22CE; border: 1px solid #D8B4FE;">DEMO</span>` : ''}
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
            <td>
              ${shortBadge}
              ${cand.shortlist_reason ? `<div style="font-size: 0.72rem; color: var(--text-muted); max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 0.25rem;" title="${cand.shortlist_reason.replace(/"/g, '&quot;')}">${cand.shortlist_reason}</div>` : ""}
            </td>
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

  async runJobScreening() {
    if (!this.currentJobId) {
      toast.info("Please select a specific job position to run screening.");
      return;
    }

    const btn = document.getElementById("btn-run-screening");
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span>⏳</span> Running Screening...`;
    }

    try {
      toast.info("Executing automated screening & dynamic Top-N selection...");
      const result = await api.screening.runJobScreening(this.currentJobId);
      toast.success(`Screening complete! Evaluated ${result.total_candidates_evaluated} candidates. Top-${result.shortlist_size} competitive shortlist finalized.`);

      const bannerContainer = document.getElementById("top-n-banner-container");
      if (bannerContainer) {
        const cutoffText = result.cutoff_candidate ? `Cutoff candidate: ${result.cutoff_candidate.candidate_name}` : "Shortlist filled";
        bannerContainer.innerHTML = `
          <div class="card" style="margin-bottom: 1.5rem; background: rgba(16, 185, 129, 0.08); border-color: rgba(16, 185, 129, 0.3);">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
              <div>
                <div style="font-weight: 700; color: #10B981; font-size: 1rem;">
                  🏆 Dynamic Top-${result.shortlist_size} Shortlist Finalized (${result.top_n_candidates.length}/${result.shortlist_size} positions filled)
                </div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem;">
                  Total evaluated: ${result.total_candidates_evaluated} • ${cutoffText} • Excluded pool: ${result.excluded_candidates.length}
                </div>
              </div>
              <div>
                <span class="badge badge-success"><span class="badge-dot"></span> Evaluated Continuously</span>
              </div>
            </div>
          </div>
        `;
      }

      await this.loadCandidates();
    } catch (err) {
      toast.error(`Screening failed: ${err.message}`);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<span>⚡</span> Run Automated Screening`;
      }
    }
  },

  openDemoZipModal() {
    const activeJob = this.jobsList && this.jobsList.find((j) => j.id === this.currentJobId);
    let jobSelectionHtml = "";
    if (activeJob) {
      jobSelectionHtml = `
        <div style="background: var(--bg-surface-elevated); padding: 0.75rem 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-color); margin-bottom: 1.25rem;">
          <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: var(--text-muted); letter-spacing: 0.05em;">Target Job Position</div>
          <div style="font-weight: 700; color: var(--text-primary); font-size: 1rem; margin-top: 0.2rem;">${activeJob.title}</div>
          <input type="hidden" id="demo-import-job-id" value="${activeJob.id}" />
        </div>
      `;
    } else {
      let options = (this.jobsList || []).map((j) => `<option value="${j.id}">${j.title}</option>`).join("");
      jobSelectionHtml = `
        <div class="form-group" style="margin-bottom: 1.25rem;">
          <label class="form-label" for="demo-import-job-id">Select Target Job Position</label>
          <select class="form-select" id="demo-import-job-id">
            ${options || '<option value="">No jobs available</option>'}
          </select>
        </div>
      `;
    }

    modal.open(`
      <div class="modal-header">
        <h3 class="modal-title" style="display: flex; align-items: center; gap: 0.5rem;">
          <span>🧪</span> Import Demo Resume ZIP (Algorithm Validation)
        </h3>
        <button class="btn btn-outline btn-sm" onclick="modal.close()">✕</button>
      </div>
      <div>
        <div style="background: #FAF5FF; border: 1px solid #E9D5FF; border-radius: var(--radius-md); padding: 0.85rem 1rem; margin-bottom: 1.25rem; font-size: 0.85rem; color: #6B21A8; line-height: 1.45;">
          <strong>Development & Algorithm Validation:</strong> Upload a ZIP containing synthetic resumes (e.g. <code>Gap2Hire_50_Fake_Resumes.zip</code>) to evaluate the automated screening engine and Dynamic Top-N selection against ~50 candidate profiles. Imported candidates are tagged as <strong>DEMO</strong> and will not interfere with real Gmail applicant pipelines.
        </div>

        ${jobSelectionHtml}

        <!-- File Upload Area -->
        <div id="demo-drop-zone" onclick="document.getElementById('demo-zip-file-input').click()" style="border: 2px dashed #A855F7; background: #FAF5FF; padding: 2rem 1.5rem; text-align: center; border-radius: var(--radius-md); cursor: pointer; transition: all 0.2s ease;">
          <div style="font-size: 2.2rem; margin-bottom: 0.5rem;">📦</div>
          <div style="font-weight: 700; color: #7E22CE; font-size: 0.95rem;">
            Click to select <code>Gap2Hire_50_Fake_Resumes.zip</code>
          </div>
          <div style="font-size: 0.8rem; color: #9333EA; margin-top: 0.35rem;">
            ZIP archives only • Up to 50 MB • Validates safe path traversal & extracts PDFs safely
          </div>
          <input type="file" id="demo-zip-file-input" accept=".zip" style="display: none;" onchange="candidatesView.onDemoZipSelected(this)" />
        </div>

        <!-- Selected File Info (hidden until file chosen) -->
        <div id="demo-file-info" style="display: none; margin-top: 1rem; padding: 0.85rem 1rem; background: var(--bg-surface-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-md);">
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; font-size: 0.9rem; color: var(--text-primary);" id="demo-file-name">Gap2Hire_50_Fake_Resumes.zip</div>
              <div style="font-size: 0.8rem; color: var(--text-muted);" id="demo-file-meta">-</div>
            </div>
            <span class="badge badge-info">Ready to Ingest</span>
          </div>
        </div>

        <!-- Progress Indicator -->
        <div id="demo-progress-area" style="display: none; margin: 1.5rem 0; padding: 1.25rem; background: var(--bg-surface-elevated); border-radius: var(--radius-md); border: 1px solid var(--border-color);">
          <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div style="font-size: 1.2rem; animation: spin 1.5s linear infinite;">⏳</div>
            <div style="font-weight: 600; font-size: 0.9rem; color: var(--text-primary);" id="demo-progress-msg">
              Unpacking ZIP & processing synthetic resumes...
            </div>
          </div>
          <div style="font-size: 0.8rem; color: var(--text-secondary);">
            Extracting text with PyMuPDF • Deriving deterministic demo emails • Grounding capability evidence • Registering candidate profiles...
          </div>
        </div>

        <!-- Result Summary -->
        <div id="demo-result-area" style="display: none; margin: 1.5rem 0;"></div>

        <div class="modal-footer" id="demo-modal-footer">
          <button type="button" class="btn btn-outline" onclick="modal.close()">Cancel</button>
          <button type="button" class="btn btn-primary" id="btn-start-demo-import" disabled onclick="candidatesView.executeDemoZipImport()">
            Import & Process Resumes
          </button>
        </div>
      </div>
    `);
  },

  onDemoZipSelected(input) {
    const file = input.files && input.files[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".zip")) {
      toast.error("Please select a valid .zip archive.");
      input.value = "";
      return;
    }

    const infoEl = document.getElementById("demo-file-info");
    const nameEl = document.getElementById("demo-file-name");
    const metaEl = document.getElementById("demo-file-meta");
    const startBtn = document.getElementById("btn-start-demo-import");

    if (infoEl) infoEl.style.display = "block";
    if (nameEl) nameEl.textContent = file.name;
    if (metaEl) metaEl.textContent = `${(file.size / 1024).toFixed(1)} KB • Application archive ready`;
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.textContent = `Import & Ingest "${file.name}"`;
    }
  },

  async executeDemoZipImport() {
    const input = document.getElementById("demo-zip-file-input");
    const file = input && input.files && input.files[0];
    const jobSelect = document.getElementById("demo-import-job-id");
    const jobId = jobSelect ? jobSelect.value : this.currentJobId;

    if (!file) {
      toast.error("Please choose a ZIP file to import.");
      return;
    }

    if (!jobId) {
      toast.error("Please select a target job position.");
      return;
    }

    const startBtn = document.getElementById("btn-start-demo-import");
    const progressArea = document.getElementById("demo-progress-area");
    const resultArea = document.getElementById("demo-result-area");
    const footer = document.getElementById("demo-modal-footer");
    const dropZone = document.getElementById("demo-drop-zone");
    const fileInfo = document.getElementById("demo-file-info");

    if (startBtn) startBtn.disabled = true;
    if (dropZone) dropZone.style.display = "none";
    if (fileInfo) fileInfo.style.display = "none";
    if (progressArea) progressArea.style.display = "block";
    if (resultArea) resultArea.style.display = "none";

    try {
      const res = await api.demo.importResumes(jobId, file);

      if (progressArea) progressArea.style.display = "none";
      if (resultArea) {
        resultArea.style.display = "block";
        resultArea.innerHTML = `
          <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-md); padding: 1.25rem;">
            <h4 style="color: #10B981; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem;">
              <span>✅</span> Demo Resumes Ingestion Completed
            </h4>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.75rem; font-size: 0.875rem;">
              <div><strong>PDF Resumes Discovered:</strong> ${res.total_found}</div>
              <div><strong>Demo Candidates Created:</strong> <span style="color: #059669; font-weight: 700;">${res.created}</span></div>
              <div><strong>Duplicates Skipped:</strong> ${res.skipped_duplicates}</div>
              <div><strong>Failed:</strong> ${res.failed}</div>
            </div>
            <div style="margin-top: 0.75rem; font-size: 0.8rem; color: #047857;">
              ${res.message}
            </div>
          </div>
        `;
      }

      if (footer) {
        footer.innerHTML = `
          <button type="button" class="btn btn-primary" onclick="modal.close(); candidatesView.loadCandidates();">
            View Screening Queue (${res.created} New Demo Candidates)
          </button>
        `;
      }

      toast.success(`Demo import successful! ${res.created} candidates created (${res.skipped_duplicates} duplicates skipped).`);
      this.currentJobId = jobId;
    } catch (err) {
      if (progressArea) progressArea.style.display = "none";
      if (dropZone) dropZone.style.display = "block";
      if (fileInfo) fileInfo.style.display = "block";
      toast.error(`Demo import failed: ${err.message}`);
      if (startBtn) {
        startBtn.disabled = false;
        startBtn.textContent = "Retry Import";
      }
    }
  },

  openBatchInterviewModal() {
    const shortlistedCandidates = (this.candidates || []).filter(
      (c) => c.shortlist_status === "SHORTLISTED"
    );

    if (shortlistedCandidates.length === 0) {
      toast.info("No shortlisted candidates found. Please shortlist candidates before starting batch interviews.");
      return;
    }

    modal.open(`
      <div class="modal-header">
        <h3 class="modal-title">👥 Start Concurrent Independent Interviews</h3>
        <button class="btn btn-outline btn-sm" onclick="modal.close()">✕</button>
      </div>
      <div style="padding-top: 0.5rem;">
        <p style="color: var(--text-secondary); font-size: 0.88rem; margin-bottom: 1.25rem;">
          Select shortlisted candidates to initialize independent interview sessions with isolated LangGraph threads, dedicated question pools, and separate live rooms.
        </p>

        <div class="form-group" style="margin-bottom: 1.25rem;">
          <label class="form-label" style="font-weight: 600; font-size: 0.88rem;">
            Concurrency Capacity (Simultaneous Interview Capacity)
          </label>
          <select class="form-select" id="batch-concurrency-select" style="width: 100%;">
            <option value="1">1 candidate at a time</option>
            <option value="2" selected>2 candidates at a time</option>
            <option value="3">3 candidates at a time</option>
            <option value="5">5 candidates at a time</option>
          </select>
          <small style="color: var(--text-muted); font-size: 0.78rem; display: block; margin-top: 0.35rem;">
            Each candidate runs on an independent session and unique LangGraph thread without shared state.
          </small>
        </div>

        <div class="form-group" style="margin-bottom: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <label class="form-label" style="font-weight: 600; font-size: 0.88rem; margin: 0;">
              Select Shortlisted Candidates (${shortlistedCandidates.length} available)
            </label>
            <button type="button" class="btn btn-xs" style="font-size: 0.75rem; color: var(--primary-color);" onclick="document.querySelectorAll('.batch-cand-check').forEach(cb => cb.checked = true)">
              Select All
            </button>
          </div>
          <div style="max-height: 220px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 0.5rem; background: var(--bg-surface-elevated);">
            ${shortlistedCandidates.map((c) => `
              <label style="display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0.6rem; border-radius: var(--radius-sm); cursor: pointer; border-bottom: 1px solid var(--border-color);">
                <input type="checkbox" class="batch-cand-check" value="${c.application_id}" checked style="accent-color: var(--primary-color); width: 16px; height: 16px;" />
                <div style="flex: 1;">
                  <div style="font-weight: 600; font-size: 0.88rem; color: var(--text-primary);">${c.candidate_name || "Applicant"}</div>
                  <div style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">${c.candidate_email} • ${c.job_title || "General"}</div>
                </div>
                <span class="badge badge-success" style="font-size: 0.7rem;">Shortlisted</span>
              </label>
            `).join('')}
          </div>
        </div>

        <div id="batch-results-area" style="display: none; margin-bottom: 1.25rem;"></div>

        <div id="batch-modal-footer" style="display: flex; justify-content: flex-end; gap: 0.75rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
          <button type="button" class="btn btn-secondary" onclick="modal.close()">Cancel</button>
          <button type="button" class="btn btn-primary" id="btn-submit-batch" onclick="candidatesView.submitBatchInterviews()">
            🚀 Start Batch Sessions
          </button>
        </div>
      </div>
    `);
  },

  async submitBatchInterviews() {
    const checkEls = document.querySelectorAll('.batch-cand-check:checked');
    const appIds = Array.from(checkEls).map(cb => cb.value);
    const concurrencyVal = parseInt(document.getElementById('batch-concurrency-select')?.value || '2', 10);
    const submitBtn = document.getElementById('btn-submit-batch');
    const resultsArea = document.getElementById('batch-results-area');
    const footer = document.getElementById('batch-modal-footer');

    if (appIds.length === 0) {
      toast.error("Please select at least one candidate for the batch.");
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Initializing Sessions...";
    }

    try {
      const resp = await api.interviews.batchStart({
        application_ids: appIds,
        concurrency_limit: concurrencyVal,
        auto_start: true,
      });

      if (resultsArea) {
        resultsArea.style.display = "block";
        resultsArea.innerHTML = `
          <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-md); padding: 1rem;">
            <h4 style="color: #10B981; font-size: 0.95rem; margin-bottom: 0.5rem;">
              ✅ ${resp.sessions_created} Independent Interview Sessions Initialized (Capacity: ${resp.concurrency_limit})
            </h4>
            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
              Each session has an isolated LangGraph thread identity:
            </div>
            <div style="max-height: 120px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.35rem;">
              ${resp.sessions.map(s => `
                <div style="background: var(--bg-surface); padding: 0.35rem 0.6rem; border-radius: 4px; font-size: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
                  <span><strong>${s.candidate_name || s.candidate_email}:</strong> Session <code style="font-family: var(--font-mono);">${s.session_id.substring(0, 8)}...</code></span>
                  <span class="badge badge-info" style="font-size: 0.65rem;">Thread: ${s.thread_id.substring(0, 8)}...</span>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }

      if (footer) {
        footer.innerHTML = `
          <button type="button" class="btn btn-primary" onclick="modal.close(); candidatesView.loadCandidates();">
            Done
          </button>
        `;
      }

      toast.success(`Successfully initialized ${resp.sessions_created} independent interview sessions!`);
    } catch (err) {
      toast.error(`Batch initialization failed: ${err.message}`);
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "🚀 Start Batch Sessions";
      }
    }
  },
};

window.candidatesView = candidatesView;
window.CandidatesView = candidatesView;
