// ==========================================================================
// Gap2Hire - Interview Intelligence & Planning View (Phases 1–3)
// Clean Professional Light B2B SaaS Aesthetic
// ==========================================================================

window.InterviewSetupView = {
  currentAppId: null,
  currentJobId: null,
  candidateData: null,
  preAnalysis: null,
  activeDatasetFile: null,
  availableDatasets: [],
  currentPlan: null,
  planHistory: [],

  async render(container, params = {}) {
    this.currentAppId = params.applicationId || (window.appState && window.appState.activeApplicationId);
    this.currentJobId = params.jobId || (window.appState && window.appState.activeJobId);

    if (!this.currentAppId && !this.currentJobId) {
      container.innerHTML = `
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 3rem; text-align: center; margin: 2rem auto; max-width: 600px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <div style="font-size: 2.5rem; margin-bottom: 1rem;">📋</div>
          <h3 style="color: #0F172A; font-weight: 700; margin-bottom: 0.5rem;">No Candidate or Job Selected</h3>
          <p style="color: #64748B; margin-bottom: 1.5rem; font-size: 0.95rem;">Please select a candidate from the screening queue to configure their interview plan.</p>
          <a href="#candidates" class="btn btn-primary" style="background: #2563EB; font-weight: 600; padding: 0.6rem 1.25rem;">← Go to Screening Queue</a>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div style="padding: 2rem 2.5rem; background: #F8FAFC; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 1.25rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.35rem;">
              <span style="font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; color: #2563EB; background: #EFF6FF; border: 1px solid #DBEAFE; padding: 3px 8px; border-radius: 4px;">
                INTERVIEW INTELLIGENCE
              </span>
              <span id="target-job-pill" style="font-size: 0.85rem; color: #64748B; font-weight: 500;"></span>
            </div>
            <h1 id="plan-page-title" style="font-size: 1.5rem; font-weight: 700; color: #0F172A; margin: 0;">
              Candidate Interview Planning & Approval
            </h1>
            <p style="color: #64748B; font-size: 0.875rem; margin-top: 0.25rem;">
              Evidence-grounded question targeting, multi-concept dataset configuration, and immutable HR plan approval.
            </p>
          </div>
          <div style="display: flex; gap: 0.75rem;">
            <button id="btn-back-to-cand" class="btn btn-sm" style="background: #FFFFFF; color: #334155; border: 1px solid #CBD5E1; font-weight: 600; padding: 0.45rem 0.9rem; border-radius: 6px;">
              ← Back to Candidate Detail
            </button>
            <button id="btn-open-upload-dataset" class="btn btn-sm" style="background: #FFFFFF; color: #2563EB; border: 1px solid #BFDBFE; font-weight: 600; padding: 0.45rem 0.9rem; border-radius: 6px;">
              📤 Upload Interview Dataset (.xlsx)
            </button>
          </div>
        </div>

        <!-- Target Candidate Banner -->
        <div id="candidate-banner-container" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
          <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="width: 44px; height: 44px; border-radius: 50%; background: #EFF6FF; color: #2563EB; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.1rem; border: 1px solid #BFDBFE;">
              👤
            </div>
            <div>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <h3 id="cand-banner-name" style="margin: 0; font-size: 1.1rem; font-weight: 700; color: #0F172A;">Loading...</h3>
                <span id="cand-banner-shortlist-badge" style="font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 4px;"></span>
              </div>
              <p id="cand-banner-sub" style="margin: 0.2rem 0 0 0; color: #64748B; font-size: 0.85rem;">Loading application data...</p>
            </div>
          </div>
          <div id="plan-version-badge-container"></div>
        </div>

        <!-- 3-SECTION PIPELINE GRID -->
        <div style="display: flex; flex-direction: column; gap: 1.5rem;">

          <!-- SECTION 1: HR Curated Question Datasets -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid #F1F5F9; padding-bottom: 0.75rem;">
              <div>
                <h2 style="font-size: 1.05rem; font-weight: 700; color: #0F172A; margin: 0;">
                  1. Curated Question Datasets (HR Question Pool)
                </h2>
                <span style="font-size: 0.8rem; color: #64748B;">Multi-concept question repository uploaded by HR (.xlsx)</span>
              </div>
              <button id="btn-inspect-dataset" class="btn btn-sm" style="display: none; background: #F8FAFC; color: #334155; border: 1px solid #CBD5E1; font-weight: 600; padding: 0.35rem 0.75rem; border-radius: 6px;">
                👁️ Inspect Questions
              </button>
            </div>
            <div id="dataset-summary-content">
              <div style="text-align: center; padding: 1.5rem; color: #64748B; font-size: 0.88rem;">
                Loading interview datasets...
              </div>
            </div>
          </div>

          <!-- SECTION 2: Candidate Pre-Interview Analysis -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid #F1F5F9; padding-bottom: 0.75rem;">
              <div>
                <h2 style="font-size: 1.05rem; font-weight: 700; color: #0F172A; margin: 0;">
                  2. Candidate Pre-Interview Analysis
                </h2>
                <span style="font-size: 0.8rem; color: #64748B;">Evidence-grounded capability mapping distinguishing claims from verified demonstrations</span>
              </div>
              <span style="font-size: 0.75rem; font-weight: 600; color: #065F46; background: #ECFDF5; border: 1px solid #A7F3D0; padding: 2px 8px; border-radius: 4px;">
                EVIDENCE GROUNDED
              </span>
            </div>
            <div id="pre-analysis-container">
              <div style="text-align: center; padding: 1.5rem; color: #64748B; font-size: 0.88rem;">
                Analyzing candidate evidence and resume claims...
              </div>
            </div>
          </div>

          <!-- SECTION 3: AI Interview Plan & HR Approval -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; border-bottom: 1px solid #F1F5F9; padding-bottom: 0.75rem;">
              <div>
                <h2 style="font-size: 1.05rem; font-weight: 700; color: #0F172A; margin: 0;">
                  3. Candidate-Specific Interview Plan & HR Approval
                </h2>
                <span style="font-size: 0.8rem; color: #64748B;">Targeted multi-round interview structure with immutable versioning</span>
              </div>
              <div id="plan-action-buttons" style="display: flex; gap: 0.5rem; align-items: center;"></div>
            </div>
            <div id="interview-plan-container">
              <div style="text-align: center; padding: 2rem; color: #64748B; font-size: 0.88rem;">
                Loading interview plan...
              </div>
            </div>
          </div>

        </div>

        <!-- MODAL CONTAINERS -->
        <div id="setup-modal-overlay" style="display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.6); z-index: 1000; align-items: center; justify-content: center;">
          <div id="setup-modal-content" style="background: #FFFFFF; border-radius: 12px; max-width: 700px; width: 90%; max-height: 85vh; overflow-y: auto; padding: 2rem; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);">
          </div>
        </div>
      </div>
    `;

    this.wireGlobalEvents(container);
    await this.loadAllData();
  },

  wireGlobalEvents(container) {
    const btnBack = container.querySelector('#btn-back-to-cand');
    if (btnBack) {
      btnBack.addEventListener('click', () => {
        if (this.currentAppId) {
          router.navigate('candidate-detail', { id: this.currentAppId });
        } else {
          router.navigate('candidates');
        }
      });
    }

    const btnUpload = container.querySelector('#btn-open-upload-dataset');
    if (btnUpload) {
      btnUpload.addEventListener('click', () => this.openUploadDatasetModal());
    }

    const btnInspect = container.querySelector('#btn-inspect-dataset');
    if (btnInspect) {
      btnInspect.addEventListener('click', () => this.openInspectDatasetModal());
    }
  },

  async loadAllData() {
    try {
      // 1. Load Application & Candidate
      if (this.currentAppId) {
        this.candidateData = await api.getApplicationDetail(this.currentAppId).catch(() => null);
        if (this.candidateData) {
          this.currentJobId = this.candidateData.job_id || this.currentJobId;
        }
      }

      // 2. Load Datasets
      await this.loadDatasets();

      // 3. Load Pre-Analysis
      if (this.currentAppId) {
        this.preAnalysis = await api.interviewPlans.getPreAnalysis(this.currentAppId).catch(() => null);
      }

      // 4. Load Existing Plans
      if (this.currentAppId) {
        this.currentApplicationId = this.currentAppId;
        this.planHistory = await api.interviewPlans.listPlans(this.currentAppId).catch(() => []);
        // Active plan is the most recent (version 1, 2...)
        this.currentPlan = this.planHistory.length > 0 ? this.planHistory[0] : null;

        // 5. Load Schedule if plan is approved
        if (this.currentPlan && this.currentPlan.status === 'APPROVED') {
          // Check if session exists and has schedule
          try {
            const sessions = await api.get(`/applications/${this.currentAppId}`).catch(() => null);
            if (sessions && sessions.interview_session_id) {
              this.currentSchedule = await api.interviewSchedules.getSchedule(sessions.interview_session_id).catch(() => null);
            }
          } catch (e) {}
        }
      }

      this.renderCandidateBanner();
      this.renderDatasetsSummary();
      this.renderPreAnalysis();
      this.renderInterviewPlan();
    } catch (err) {
      console.error(err);
      toast.error(`Error loading interview setup: ${err.message}`);
    }
  },

  async loadDatasets() {
    try {
      const files = await api.interviewDatasets.list(this.currentJobId).catch(() => []);
      this.availableDatasets = files;
      if (files.length > 0) {
        // Fetch full active dataset file with questions
        this.activeDatasetFile = await api.interviewDatasets.get(files[0].id).catch(() => files[0]);
      } else {
        this.activeDatasetFile = null;
      }
    } catch (e) {
      console.warn("Dataset load error:", e);
    }
  },

  renderCandidateBanner() {
    const cand = this.candidateData;
    const pre = this.preAnalysis;
    const nameEl = document.getElementById('cand-banner-name');
    const subEl = document.getElementById('cand-banner-sub');
    const badgeEl = document.getElementById('cand-banner-shortlist-badge');
    const jobPill = document.getElementById('target-job-pill');

    const displayName = (pre && pre.candidate_name) || (cand && cand.candidate_name) || 'Candidate';
    const displayJob = (pre && pre.job_title) || (cand && cand.job_title) || 'Backend Python Developer';
    const displayEmail = (cand && cand.candidate_email) || 'Verified Profile';

    if (nameEl) nameEl.textContent = displayName;
    if (subEl) subEl.textContent = `${displayEmail} • Applied for ${displayJob}`;
    if (jobPill) jobPill.textContent = `Job: ${displayJob}`;

    if (badgeEl) {
      badgeEl.textContent = '⭐ SHORTLISTED';
      badgeEl.style.background = '#ECFDF5';
      badgeEl.style.color = '#065F46';
      badgeEl.style.border = '1px solid #A7F3D0';
    }
  },

  renderDatasetsSummary() {
    const container = document.getElementById('dataset-summary-content');
    const inspectBtn = document.getElementById('btn-inspect-dataset');
    if (!container) return;

    if (!this.activeDatasetFile || !this.activeDatasetFile.datasets || this.activeDatasetFile.datasets.length === 0) {
      if (inspectBtn) inspectBtn.style.display = 'none';
      container.innerHTML = `
        <div style="background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 6px; padding: 2rem; text-align: center;">
          <p style="color: #475569; font-size: 0.9rem; margin-bottom: 0.5rem; font-weight: 500;">
            No interview question dataset uploaded yet for this position.
          </p>
          <p style="color: #64748B; font-size: 0.825rem; margin-bottom: 1.25rem;">
            Upload an Excel (.xlsx) file containing 3 question pools (e.g. Python, FastAPI, PostgreSQL).
          </p>
          <button class="btn btn-sm btn-primary" onclick="InterviewSetupView.openUploadDatasetModal()" style="background: #2563EB; font-weight: 600; padding: 0.45rem 1rem;">
            📤 Upload Interview Dataset (.xlsx)
          </button>
        </div>
      `;
      return;
    }

    if (inspectBtn) inspectBtn.style.display = 'inline-flex';

    const f = this.activeDatasetFile;
    const datasets = f.datasets || [];

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; background: #F8FAFC; padding: 0.75rem 1rem; border-radius: 6px; border: 1px solid #E2E8F0;">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <span style="font-size: 1.25rem;">📊</span>
          <div>
            <div style="font-weight: 700; color: #0F172A; font-size: 0.925rem;">
              ${f.filename}
            </div>
            <div style="font-size: 0.8rem; color: #64748B;">
              Uploaded question configuration • ${f.total_questions} total questions across ${datasets.length} distinct concept datasets
            </div>
          </div>
        </div>
        <span style="font-size: 0.8rem; font-weight: 700; color: #1E40AF; background: #DBEAFE; border: 1px solid #BFDBFE; padding: 3px 10px; border-radius: 12px;">
          ${f.total_questions} QUESTIONS READY
        </span>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
        ${datasets.map((d, idx) => `
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 1rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase; margin-bottom: 0.25rem;">
              Dataset ${idx + 1}
            </div>
            <div style="font-size: 1.1rem; font-weight: 700; color: #0F172A; margin-bottom: 0.5rem;">
              ${d.concept || d.name}
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #2563EB; font-weight: 600;">
              <span>${d.question_count || (d.questions ? d.questions.length : 0)} questions</span>
              <span style="color: #64748B; font-weight: 400; font-size: 0.78rem;">✓ Validated</span>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  },

  renderPreAnalysis() {
    const container = document.getElementById('pre-analysis-container');
    if (!container) return;

    if (!this.preAnalysis) {
      container.innerHTML = `
        <div style="text-align: center; padding: 1.5rem; color: #64748B; font-size: 0.88rem;">
          No pre-interview analysis available yet.
        </div>
      `;
      return;
    }

    const pa = this.preAnalysis;
    const strengths = pa.candidate_strengths || [];
    const claims = pa.candidate_claims || [];
    const unknowns = pa.candidate_unknowns || [];
    const targets = pa.verification_targets || [];

    container.innerHTML = `
      <!-- Summary Box -->
      <div style="background: #F8FAFC; border-left: 4px solid #2563EB; padding: 0.875rem 1rem; border-radius: 0 6px 6px 0; margin-bottom: 1.25rem; font-size: 0.88rem; color: #334155; line-height: 1.5;">
        <strong>Evidence-Grounded Intelligence:</strong> ${pa.grounded_summary || 'Analysis completed.'}
      </div>

      <!-- 3 Columns of Evidence Status -->
      <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-bottom: 1.25rem;">

        <!-- 1. Strengths (DEMONSTRATED / VERIFIED) -->
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid #F1F5F9; padding-bottom: 0.5rem;">
            <span style="font-weight: 700; font-size: 0.85rem; color: #065F46;">
              ✓ DEMONSTRATED STRENGTHS
            </span>
            <span style="font-size: 0.75rem; font-weight: 700; color: #065F46; background: #ECFDF5; padding: 1px 6px; border-radius: 4px;">
              ${strengths.length}
            </span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.6rem;">
            ${strengths.length === 0 ? `
              <div style="font-size: 0.8rem; color: #94A3B8;">No external code/assessment proof yet.</div>
            ` : strengths.map(s => `
              <div style="padding: 0.5rem; background: #F0FDF4; border: 1px solid #DCFCE7; border-radius: 4px;">
                <div style="font-weight: 700; font-size: 0.88rem; color: #166534;">
                  ${s.capability_name}
                  <span style="font-size: 0.7rem; font-weight: 600; color: #15803D; background: #DCFCE7; padding: 1px 4px; border-radius: 3px; margin-left: 4px;">
                    ${s.provenance}
                  </span>
                </div>
                <div style="font-size: 0.75rem; color: #166534; margin-top: 2px;">
                  ${s.rationale || 'Demonstrated in project source artifacts'}
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- 2. Claims (CLAIM - Unverified) -->
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid #F1F5F9; padding-bottom: 0.5rem;">
            <span style="font-weight: 700; font-size: 0.85rem; color: #92400E;">
              ⚠️ RESUME CLAIMS (UNVERIFIED)
            </span>
            <span style="font-size: 0.75rem; font-weight: 700; color: #92400E; background: #FEF3C7; padding: 1px 6px; border-radius: 4px;">
              ${claims.length}
            </span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.6rem;">
            ${claims.length === 0 ? `
              <div style="font-size: 0.8rem; color: #94A3B8;">No unverified resume claims.</div>
            ` : claims.map(c => `
              <div style="padding: 0.5rem; background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 4px;">
                <div style="font-weight: 700; font-size: 0.88rem; color: #92400E;">
                  ${c.capability_name}
                  <span style="font-size: 0.7rem; font-weight: 600; color: #B45309; background: #FEF3C7; padding: 1px 4px; border-radius: 3px; margin-left: 4px;">
                    CLAIM
                  </span>
                </div>
                <div style="font-size: 0.75rem; color: #92400E; margin-top: 2px;">
                  Self-reported on resume; interview verification recommended
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- 3. Unknowns (UNKNOWN / INSUFFICIENT) -->
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid #F1F5F9; padding-bottom: 0.5rem;">
            <span style="font-weight: 700; font-size: 0.85rem; color: #475569;">
              ❓ UNKNOWN CAPABILITIES
            </span>
            <span style="font-size: 0.75rem; font-weight: 700; color: #475569; background: #F1F5F9; padding: 1px 6px; border-radius: 4px;">
              ${unknowns.length}
            </span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.6rem;">
            ${unknowns.length === 0 ? `
              <div style="font-size: 0.8rem; color: #94A3B8;">No unknown capabilities.</div>
            ` : unknowns.map(u => `
              <div style="padding: 0.5rem; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 4px;">
                <div style="font-weight: 700; font-size: 0.88rem; color: #334155;">
                  ${u.capability_name}
                  <span style="font-size: 0.7rem; font-weight: 600; color: #64748B; background: #E2E8F0; padding: 1px 4px; border-radius: 3px; margin-left: 4px;">
                    UNKNOWN
                  </span>
                </div>
                <div style="font-size: 0.75rem; color: #64748B; margin-top: 2px;">
                  No prior evidence; foundational probing recommended
                </div>
              </div>
            `).join('')}
          </div>
        </div>

      </div>

      <!-- Verification Targets List -->
      <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 0.875rem 1rem;">
        <span style="font-size: 0.8rem; font-weight: 700; color: #0F172A; text-transform: uppercase;">
          Interview Focus Targets:
        </span>
        <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem;">
          ${targets.map(t => `
            <span style="font-size: 0.8rem; font-weight: 600; color: #1E40AF; background: #DBEAFE; border: 1px solid #BFDBFE; padding: 2px 8px; border-radius: 4px;">
              🎯 ${t.capability_name} (${t.current_state} • Priority: ${t.priority})
            </span>
          `).join('')}
        </div>
      </div>
    `;
  },

  renderInterviewPlan() {
    const container = document.getElementById('interview-plan-container');
    const actionsContainer = document.getElementById('plan-action-buttons');
    const versionContainer = document.getElementById('plan-version-badge-container');
    if (!container || !actionsContainer) return;

    if (!this.currentPlan) {
      if (versionContainer) versionContainer.innerHTML = '';
      actionsContainer.innerHTML = `
        <button id="btn-generate-plan" class="btn btn-sm btn-primary" onclick="InterviewSetupView.generatePlan()" style="background: #2563EB; font-weight: 600; padding: 0.45rem 1rem;">
          ✨ Generate AI Interview Plan
        </button>
      `;
      container.innerHTML = `
        <div style="background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 6px; padding: 2.5rem; text-align: center;">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">🤖</div>
          <h4 style="color: #0F172A; font-weight: 700; margin-bottom: 0.5rem;">No Interview Plan Generated Yet</h4>
          <p style="color: #64748B; font-size: 0.875rem; margin-bottom: 1.25rem; max-width: 500px; margin-left: auto; margin-right: auto;">
            The AI will use the candidate's pre-interview analysis, resume claims, and HR question datasets to structure a candidate-specific multi-round interview.
          </p>
          <button class="btn btn-primary" onclick="InterviewSetupView.generatePlan()" style="background: #2563EB; font-weight: 600; padding: 0.6rem 1.25rem;">
            ✨ Generate AI Interview Plan
          </button>
        </div>
      `;
      return;
    }

    const plan = this.currentPlan;
    const isApproved = plan.status === 'APPROVED';

    // Update version badge in candidate banner
    if (versionContainer) {
      versionContainer.innerHTML = `
        <div style="text-align: right;">
          <div style="font-size: 0.75rem; color: #64748B; font-weight: 600; text-transform: uppercase;">Interview Plan</div>
          <div style="display: flex; align-items: center; gap: 0.5rem; margin-top: 2px;">
            <span style="font-weight: 700; font-size: 0.95rem; color: #0F172A;">Version ${plan.version}</span>
            <span style="font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; ${isApproved ? 'background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0;' : 'background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE;'}">
              ${plan.status}
            </span>
          </div>
        </div>
      `;
    }

    // Action buttons
    actionsContainer.innerHTML = `
      <button class="btn btn-sm" onclick="InterviewSetupView.generatePlan()" style="background: #FFFFFF; color: #334155; border: 1px solid #CBD5E1; font-weight: 600; padding: 0.4rem 0.85rem; border-radius: 6px;">
        🔄 Regenerate Plan
      </button>
      ${!isApproved ? `
        <button class="btn btn-sm" onclick="InterviewSetupView.openEditPlanModal()" style="background: #FFFFFF; color: #2563EB; border: 1px solid #BFDBFE; font-weight: 600; padding: 0.4rem 0.85rem; border-radius: 6px;">
          ✏️ Edit Plan
        </button>
        <button class="btn btn-sm btn-success" onclick="InterviewSetupView.openApprovePlanModal()" style="background: #059669; color: #FFFFFF; border: none; font-weight: 600; padding: 0.4rem 1rem; border-radius: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
          ✅ Approve Plan
        </button>
      ` : `
        <span style="font-size: 0.85rem; font-weight: 700; color: #065F46; background: #ECFDF5; border: 1px solid #A7F3D0; padding: 0.4rem 0.85rem; border-radius: 6px;">
          ✓ Plan Approved & Locked
        </span>
        <button class="btn btn-sm btn-primary" onclick="InterviewSetupView.openScheduleModal()" style="background: #2563EB; color: #FFFFFF; border: none; font-weight: 600; padding: 0.4rem 1rem; border-radius: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
          📅 Schedule Interview
        </button>
      `}
    `;

    // Render Rounds & Schedule Banner
    const rounds = plan.rounds || [];
    const sched = this.currentSchedule;
    container.innerHTML = `
      <!-- Schedule Confirmation Banner if Scheduled -->
      ${sched ? `
        <div style="background: #F0FDF4; border: 1px solid #86EFAC; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-size: 0.75rem; font-weight: 700; background: #16A34A; color: #FFFFFF; padding: 2px 8px; border-radius: 4px;">
                SCHEDULED
              </span>
              <span style="font-size: 0.95rem; font-weight: 700; color: #166534;">
                📅 ${new Date(sched.scheduled_start).toLocaleString(undefined, { dateStyle: 'full', timeStyle: 'short' })} (${sched.timezone})
              </span>
            </div>
            <span style="font-size: 0.8rem; font-weight: 600; color: #15803D;">
              ⏱️ ${sched.duration_minutes} min duration
            </span>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 1rem; font-size: 0.88rem; color: #374151; padding-top: 0.5rem; border-top: 1px solid #DCFCE7;">
            <div>
              <strong>Google Meet:</strong>
              <a href="${sched.meeting_url}" target="_blank" style="color: #2563EB; font-weight: 600; text-decoration: underline; margin-left: 0.35rem;">
                ${sched.meeting_url}
              </a>
            </div>
            <div style="color: #15803D; font-weight: 600; font-size: 0.82rem;">
              ✓ Candidate invitation sent
            </div>
          </div>
        </div>
      ` : ''}

      <!-- Approval Notice if Approved -->
      ${isApproved ? `
        <div style="background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 6px; padding: 0.875rem 1rem; margin-bottom: 1.25rem; display: flex; justify-content: space-between; align-items: center;">
          <div style="color: #065F46; font-size: 0.88rem;">
            <strong>✓ HR Approved:</strong> This interview plan is immutable and locked.
            ${plan.hr_feedback ? `<span style="margin-left: 0.5rem; font-style: italic;">"${plan.hr_feedback}"</span>` : ''}
          </div>
          <span style="font-size: 0.8rem; color: #047857; font-weight: 600;">
            Approved on ${new Date(plan.approved_at || plan.updated_at).toLocaleDateString()}
          </span>
        </div>
      ` : ''}

      <!-- Rounds List -->
      <div style="display: flex; flex-direction: column; gap: 1.25rem;">
        ${rounds.map((r) => `
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <!-- Round Header -->
            <div style="background: #F8FAFC; border-bottom: 1px solid #E2E8F0; padding: 1rem 1.25rem; display: flex; justify-content: space-between; align-items: center;">
              <div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                  <span style="font-size: 0.75rem; font-weight: 700; color: #2563EB; background: #EFF6FF; border: 1px solid #DBEAFE; padding: 2px 6px; border-radius: 4px;">
                    ROUND ${r.round_number}
                  </span>
                  <h3 style="font-size: 1.05rem; font-weight: 700; color: #0F172A; margin: 0;">
                    ${r.title}
                  </h3>
                </div>
                <div style="font-size: 0.825rem; color: #64748B; margin-top: 0.25rem;">
                  <strong>Objective:</strong> ${r.objective}
                </div>
              </div>
              <div style="text-align: right;">
                <span style="font-size: 0.85rem; font-weight: 700; color: #334155; background: #FFFFFF; border: 1px solid #CBD5E1; padding: 4px 10px; border-radius: 6px;">
                  ⏱️ ${r.estimated_duration_minutes} min
                </span>
              </div>
            </div>

            <!-- Round Body -->
            <div style="padding: 1.25rem;">
              <!-- Concepts Tagged -->
              <div style="margin-bottom: 0.875rem; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                <span style="font-size: 0.78rem; font-weight: 700; color: #64748B;">CONCEPTS:</span>
                ${(r.concepts || []).map(c => `
                  <span style="font-size: 0.78rem; font-weight: 600; color: #1E40AF; background: #EFF6FF; border: 1px solid #BFDBFE; padding: 2px 8px; border-radius: 4px;">
                    ${c}
                  </span>
                `).join('')}
              </div>

              <!-- Reasoning / Purpose -->
              ${r.reasoning ? `
                <div style="background: #F8FAFC; border-left: 3px solid #64748B; padding: 0.6rem 0.85rem; font-size: 0.825rem; color: #475569; margin-bottom: 1rem; border-radius: 0 4px 4px 0;">
                  <strong>Focus Rationale:</strong> ${r.reasoning}
                </div>
              ` : ''}

              <!-- Questions List -->
              <div style="font-size: 0.82rem; font-weight: 700; color: #0F172A; text-transform: uppercase; margin-bottom: 0.5rem;">
                Targeted Questions (${(r.questions || []).length}):
              </div>

              <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                ${(r.questions || []).map((q, qIdx) => `
                  <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 0.875rem 1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;">
                      <div style="font-weight: 600; font-size: 0.9rem; color: #0F172A; line-height: 1.4;">
                        ${qIdx + 1}. "${q.question_text}"
                      </div>
                      <div style="display: flex; gap: 0.35rem; white-space: nowrap;">
                        <span style="font-size: 0.72rem; font-weight: 700; color: #1E40AF; background: #DBEAFE; padding: 2px 6px; border-radius: 3px;">
                          ${q.concept}
                        </span>
                        <span style="font-size: 0.72rem; font-weight: 700; color: #64748B; background: #F1F5F9; padding: 2px 6px; border-radius: 3px;">
                          ${q.difficulty}
                        </span>
                      </div>
                    </div>

                    <div style="margin-top: 0.5rem; display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; color: #64748B; border-top: 1px dashed #F1F5F9; padding-top: 0.4rem;">
                      <div>
                        <strong>Target:</strong> ${q.purpose || 'Competency assessment'}
                      </div>
                      <div>
                        ${q.evidence_being_verified ? `<span style="color: #92400E; font-weight: 600;">Verifies: ${q.evidence_being_verified}</span>` : ''}
                      </div>
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  },

  async generatePlan() {
    if (!this.currentAppId) {
      toast.error("Application ID is required.");
      return;
    }

    const container = document.getElementById('interview-plan-container');
    if (container) {
      container.innerHTML = `
        <div style="text-align: center; padding: 3rem;">
          <div class="loading-spinner" style="margin: 0 auto 1rem;"></div>
          <h4 style="color: #0F172A; font-weight: 700; margin-bottom: 0.25rem;">Synthesizing Candidate-Specific Interview Plan...</h4>
          <p style="color: #64748B; font-size: 0.85rem;">Selecting questions from uploaded datasets to probe claims and unknowns...</p>
        </div>
      `;
    }

    try {
      const datasetFileId = this.activeDatasetFile ? this.activeDatasetFile.id : null;
      const newPlan = await api.interviewPlans.generatePlan(this.currentAppId, datasetFileId);
      this.currentPlan = newPlan;
      toast.success(`Generated Interview Plan Version ${newPlan.version}!`);
      this.renderInterviewPlan();
      this.renderCandidateBanner();
    } catch (err) {
      console.error(err);
      toast.error(`Plan generation failed: ${err.message}`);
      this.renderInterviewPlan();
    }
  },

  openUploadDatasetModal() {
    const overlay = document.getElementById('setup-modal-overlay');
    const content = document.getElementById('setup-modal-content');
    if (!overlay || !content) return;

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 0.75rem;">
        <h3 style="font-size: 1.2rem; font-weight: 700; color: #0F172A; margin: 0;">
          📤 Upload Interview Question Dataset (.xlsx)
        </h3>
        <button onclick="InterviewSetupView.closeModal()" style="background: none; border: none; font-size: 1.25rem; color: #64748B; cursor: pointer;">✕</button>
      </div>

      <div style="background: #EFF6FF; border: 1px solid #DBEAFE; border-radius: 6px; padding: 0.875rem 1rem; margin-bottom: 1.25rem; font-size: 0.85rem; color: #1E40AF; line-height: 1.4;">
        <strong>Multi-Concept Format:</strong> Upload a single Excel (.xlsx) file containing 3 distinct question datasets (e.g. Python, FastAPI, PostgreSQL).
        The file can have multiple sheets or a 'Concept' / 'Dataset' column.
      </div>

      <div style="border: 2px dashed #CBD5E1; border-radius: 8px; padding: 2rem; text-align: center; margin-bottom: 1.25rem; background: #F8FAFC;" id="drop-zone-dataset">
        <input type="file" id="dataset-file-input" accept=".xlsx,.xls" style="display: none;" onchange="InterviewSetupView.onDatasetFileSelected(event)" />
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📊</div>
        <button class="btn btn-secondary btn-sm" onclick="document.getElementById('dataset-file-input').click()" style="background: #FFFFFF; font-weight: 600; padding: 0.5rem 1rem; border: 1px solid #CBD5E1;">
          Choose Excel File
        </button>
        <p id="selected-dataset-filename" style="margin-top: 0.75rem; font-size: 0.85rem; color: #64748B;">No file chosen yet (.xlsx)</p>
      </div>

      <div id="upload-progress-area" style="display: none; margin-bottom: 1rem; text-align: center;">
        <div class="loading-spinner" style="margin: 0 auto 0.5rem;"></div>
        <span style="font-size: 0.85rem; color: #64748B;">Parsing and validating interview datasets...</span>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 0.75rem; border-top: 1px solid #E2E8F0; padding-top: 1rem;">
        <button class="btn btn-sm" onclick="InterviewSetupView.closeModal()" style="background: #FFFFFF; color: #475569; border: 1px solid #CBD5E1; font-weight: 600; padding: 0.45rem 1rem;">
          Cancel
        </button>
        <button id="btn-submit-upload-dataset" class="btn btn-sm btn-primary" onclick="InterviewSetupView.submitUploadDataset()" disabled style="background: #2563EB; font-weight: 600; padding: 0.45rem 1.25rem;">
          Upload & Parse Dataset
        </button>
      </div>
    `;

    overlay.style.display = 'flex';
  },

  selectedDatasetFileObj: null,

  onDatasetFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    this.selectedDatasetFileObj = file;
    const nameEl = document.getElementById('selected-dataset-filename');
    const submitBtn = document.getElementById('btn-submit-upload-dataset');
    if (nameEl) nameEl.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    if (submitBtn) submitBtn.disabled = false;
  },

  async submitUploadDataset() {
    if (!this.selectedDatasetFileObj) return;

    const progress = document.getElementById('upload-progress-area');
    const submitBtn = document.getElementById('btn-submit-upload-dataset');
    if (progress) progress.style.display = 'block';
    if (submitBtn) submitBtn.disabled = true;

    try {
      const resp = await api.interviewDatasets.upload(this.selectedDatasetFileObj, this.currentJobId);
      toast.success(`Successfully uploaded ${resp.filename} (${resp.total_questions} questions across ${resp.datasets.length} datasets)!`);
      this.closeModal();
      await this.loadDatasets();
      this.renderDatasetsSummary();
    } catch (err) {
      console.error(err);
      toast.error(`Upload failed: ${err.message}`);
      if (progress) progress.style.display = 'none';
      if (submitBtn) submitBtn.disabled = false;
    }
  },

  openInspectDatasetModal() {
    if (!this.activeDatasetFile) return;

    const overlay = document.getElementById('setup-modal-overlay');
    const content = document.getElementById('setup-modal-content');
    if (!overlay || !content) return;

    const f = this.activeDatasetFile;
    const datasets = f.datasets || [];

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 0.75rem;">
        <div>
          <h3 style="font-size: 1.2rem; font-weight: 700; color: #0F172A; margin: 0;">
            Question Pool Inspection: ${f.filename}
          </h3>
          <span style="font-size: 0.8rem; color: #64748B;">Total: ${f.total_questions} questions across ${datasets.length} datasets</span>
        </div>
        <button onclick="InterviewSetupView.closeModal()" style="background: none; border: none; font-size: 1.25rem; color: #64748B; cursor: pointer;">✕</button>
      </div>

      <div style="max-height: 60vh; overflow-y: auto; display: flex; flex-direction: column; gap: 1.25rem;">
        ${datasets.map(d => `
          <div style="border: 1px solid #E2E8F0; border-radius: 6px; padding: 1rem; background: #FFFFFF;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; border-bottom: 1px solid #F1F5F9; padding-bottom: 0.35rem;">
              <span style="font-weight: 700; color: #1E40AF; font-size: 0.95rem;">
                ${d.name || d.concept} (${(d.questions || []).length} questions)
              </span>
              <span style="font-size: 0.75rem; color: #64748B; background: #F1F5F9; padding: 1px 6px; border-radius: 3px;">
                Concept: ${d.concept}
              </span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
              ${(d.questions || []).map((q, idx) => `
                <div style="font-size: 0.85rem; padding: 0.4rem 0.6rem; background: #F8FAFC; border-radius: 4px; display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
                  <span style="color: #0F172A;">${idx + 1}. ${q.question_text}</span>
                  <span style="font-size: 0.7rem; font-weight: 600; color: #64748B; white-space: nowrap; background: #FFFFFF; border: 1px solid #E2E8F0; padding: 1px 4px; border-radius: 3px;">
                    ${q.difficulty} • ${q.question_type}
                  </span>
                </div>
              `).join('')}
            </div>
          </div>
        `).join('')}
      </div>

      <div style="display: flex; justify-content: flex-end; margin-top: 1.25rem; border-top: 1px solid #E2E8F0; padding-top: 0.75rem;">
        <button class="btn btn-sm btn-primary" onclick="InterviewSetupView.closeModal()" style="background: #2563EB; font-weight: 600; padding: 0.45rem 1rem;">
          Close
        </button>
      </div>
    `;

    overlay.style.display = 'flex';
  },

  openApprovePlanModal() {
    if (!this.currentPlan) return;

    const overlay = document.getElementById('setup-modal-overlay');
    const content = document.getElementById('setup-modal-content');
    if (!overlay || !content) return;

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 0.75rem;">
        <h3 style="font-size: 1.2rem; font-weight: 700; color: #0F172A; margin: 0;">
          ✅ Approve Interview Plan (Version ${this.currentPlan.version})
        </h3>
        <button onclick="InterviewSetupView.closeModal()" style="background: none; border: none; font-size: 1.25rem; color: #64748B; cursor: pointer;">✕</button>
      </div>

      <div style="background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 6px; padding: 1rem; margin-bottom: 1.25rem; font-size: 0.88rem; color: #065F46; line-height: 1.5;">
        <strong>Audit Confirmation:</strong> Approving this plan locks Version ${this.currentPlan.version} as the approved interview blueprint for this candidate.
        The rounds, questions, and duration will be permanently auditable for future Decision Replay.
      </div>

      <div style="margin-bottom: 1.25rem;">
        <label style="display: block; font-size: 0.85rem; font-weight: 600; color: #334155; margin-bottom: 0.35rem;">
          HR Review Notes / Approval Comments (Optional):
        </label>
        <textarea id="approval-notes-input" rows="3" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.5rem; font-size: 0.88rem; font-family: inherit;" placeholder="e.g. Approved with focus on probing PostgreSQL depth and Docker architecture."></textarea>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 0.75rem; border-top: 1px solid #E2E8F0; padding-top: 1rem;">
        <button class="btn btn-sm" onclick="InterviewSetupView.closeModal()" style="background: #FFFFFF; color: #475569; border: 1px solid #CBD5E1; font-weight: 600; padding: 0.45rem 1rem;">
          Cancel
        </button>
        <button class="btn btn-sm btn-success" onclick="InterviewSetupView.confirmApprovePlan()" style="background: #059669; color: #FFFFFF; border: none; font-weight: 600; padding: 0.45rem 1.25rem; border-radius: 6px;">
          Confirm & Lock Approval
        </button>
      </div>
    `;

    overlay.style.display = 'flex';
  },

  async confirmApprovePlan() {
    if (!this.currentPlan) return;
    const notesInput = document.getElementById('approval-notes-input');
    const notes = notesInput ? notesInput.value.trim() : null;

    try {
      const approved = await api.interviewPlans.approvePlan(this.currentPlan.id, notes);
      this.currentPlan = approved;
      toast.success(`Interview Plan Version ${approved.version} approved!`);
      this.closeModal();
      this.renderInterviewPlan();
      this.renderCandidateBanner();
    } catch (err) {
      console.error(err);
      toast.error(`Approval failed: ${err.message}`);
    }
  },

  openEditPlanModal() {
    if (!this.currentPlan || this.currentPlan.status === 'APPROVED') return;

    const overlay = document.getElementById('setup-modal-overlay');
    const content = document.getElementById('setup-modal-content');
    if (!overlay || !content) return;

    const rounds = this.currentPlan.rounds || [];

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 0.75rem;">
        <h3 style="font-size: 1.2rem; font-weight: 700; color: #0F172A; margin: 0;">
          ✏️ Edit Interview Plan (Draft v${this.currentPlan.version})
        </h3>
        <button onclick="InterviewSetupView.closeModal()" style="background: none; border: none; font-size: 1.25rem; color: #64748B; cursor: pointer;">✕</button>
      </div>

      <div style="max-height: 60vh; overflow-y: auto; display: flex; flex-direction: column; gap: 1.25rem;">
        ${rounds.map((r, rIdx) => `
          <div style="border: 1px solid #E2E8F0; border-radius: 6px; padding: 1rem; background: #F8FAFC;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <span style="font-weight: 700; font-size: 0.95rem; color: #0F172A;">Round ${r.round_number}: ${r.title}</span>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <label style="font-size: 0.8rem; color: #475569; font-weight: 600;">Duration (min):</label>
                <input type="number" id="edit-duration-r${rIdx}" value="${r.estimated_duration_minutes}" style="width: 60px; padding: 3px 6px; border: 1px solid #CBD5E1; border-radius: 4px; font-size: 0.85rem;" />
              </div>
            </div>

            <div style="margin-bottom: 0.5rem;">
              <label style="font-size: 0.8rem; color: #475569; font-weight: 600; display: block; margin-bottom: 0.25rem;">Objective:</label>
              <input type="text" id="edit-objective-r${rIdx}" value="${r.objective}" style="width: 100%; padding: 4px 8px; border: 1px solid #CBD5E1; border-radius: 4px; font-size: 0.85rem;" />
            </div>

            <div style="margin-top: 0.75rem;">
              <span style="font-size: 0.78rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Questions in this round:</span>
              <div style="display: flex; flex-direction: column; gap: 0.35rem; margin-top: 0.35rem;">
                ${(r.questions || []).map((q, qIdx) => `
                  <div style="font-size: 0.825rem; background: #FFFFFF; padding: 4px 8px; border: 1px solid #E2E8F0; border-radius: 4px; color: #334155;">
                    ${qIdx + 1}. ${q.question_text}
                  </div>
                `).join('')}
              </div>
            </div>
          </div>
        `).join('')}

        <div>
          <label style="display: block; font-size: 0.85rem; font-weight: 600; color: #334155; margin-bottom: 0.35rem;">
            HR Feedback / Edit Rationale:
          </label>
          <input type="text" id="edit-plan-feedback" value="${this.currentPlan.hr_feedback || ''}" placeholder="e.g. Adjusted round duration to 35 mins." style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.5rem; font-size: 0.88rem;" />
        </div>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.25rem; border-top: 1px solid #E2E8F0; padding-top: 0.75rem;">
        <button class="btn btn-sm" onclick="InterviewSetupView.closeModal()" style="background: #FFFFFF; color: #475569; border: 1px solid #CBD5E1; font-weight: 600; padding: 0.45rem 1rem;">
          Cancel
        </button>
        <button class="btn btn-sm btn-primary" onclick="InterviewSetupView.savePlanEdits()" style="background: #2563EB; font-weight: 600; padding: 0.45rem 1.25rem;">
          Save Edits
        </button>
      </div>
    `;

    overlay.style.display = 'flex';
  },

  async savePlanEdits() {
    if (!this.currentPlan) return;

    const rounds = this.currentPlan.rounds || [];
    const updatedRounds = rounds.map((r, idx) => {
      const durInput = document.getElementById(`edit-duration-r${idx}`);
      const objInput = document.getElementById(`edit-objective-r${idx}`);
      return {
        ...r,
        estimated_duration_minutes: durInput ? parseInt(durInput.value) || r.estimated_duration_minutes : r.estimated_duration_minutes,
        objective: objInput ? objInput.value.trim() : r.objective,
      };
    });

    const fbInput = document.getElementById('edit-plan-feedback');
    const feedback = fbInput ? fbInput.value.trim() : null;

    try {
      const updated = await api.interviewPlans.updatePlan(this.currentPlan.id, {
        rounds: updatedRounds,
        hr_feedback: feedback,
      });
      this.currentPlan = updated;
      toast.success("Interview plan updated!");
      this.closeModal();
      this.renderInterviewPlan();
    } catch (err) {
      console.error(err);
      toast.error(`Update failed: ${err.message}`);
    }
  },

  openScheduleModal() {
    if (!this.currentPlan || this.currentPlan.status !== 'APPROVED') {
      toast.error("You must approve the interview plan before scheduling.");
      return;
    }

    const overlay = document.getElementById('setup-modal-overlay');
    const modal = document.getElementById('setup-modal-content');
    if (!overlay || !modal) return;

    // Calculate default date (tomorrow) and time (10:00 AM)
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const defaultDate = tomorrow.toISOString().split('T')[0];
    const defaultTime = "10:00";
    const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

    modal.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #E2E8F0; padding-bottom: 0.75rem; margin-bottom: 1rem;">
        <div>
          <h2 style="font-size: 1.15rem; font-weight: 700; color: #0F172A; margin: 0;">📅 Schedule Interview</h2>
          <p style="font-size: 0.8rem; color: #64748B; margin: 2px 0 0 0;">Create calendar meeting and send invitation to candidate</p>
        </div>
        <button onclick="InterviewSetupView.closeModal()" style="background: none; border: none; font-size: 1.25rem; color: #94A3B8; cursor: pointer;">&times;</button>
      </div>

      <div style="display: flex; flex-direction: column; gap: 1rem;">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
          <div>
            <label style="display: block; font-size: 0.82rem; font-weight: 600; color: #334155; margin-bottom: 0.25rem;">
              Interview Date <span style="color: #DC2626;">*</span>
            </label>
            <input type="date" id="schedule-date-input" value="${defaultDate}" min="${new Date().toISOString().split('T')[0]}" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.45rem 0.6rem; font-size: 0.88rem;" />
          </div>
          <div>
            <label style="display: block; font-size: 0.82rem; font-weight: 600; color: #334155; margin-bottom: 0.25rem;">
              Start Time <span style="color: #DC2626;">*</span>
            </label>
            <input type="time" id="schedule-time-input" value="${defaultTime}" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.45rem 0.6rem; font-size: 0.88rem;" />
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
          <div>
            <label style="display: block; font-size: 0.82rem; font-weight: 600; color: #334155; margin-bottom: 0.25rem;">
              Timezone
            </label>
            <select id="schedule-tz-input" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.45rem 0.6rem; font-size: 0.88rem; background: #FFFFFF;">
              <option value="${userTz}" selected>${userTz} (Local)</option>
              <option value="UTC">UTC</option>
              <option value="America/New_York">America/New_York (EST)</option>
              <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
              <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
              <option value="Europe/London">Europe/London (GMT/BST)</option>
            </select>
          </div>
          <div>
            <label style="display: block; font-size: 0.82rem; font-weight: 600; color: #334155; margin-bottom: 0.25rem;">
              Duration
            </label>
            <select id="schedule-duration-input" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.45rem 0.6rem; font-size: 0.88rem; background: #FFFFFF;">
              <option value="30">30 minutes</option>
              <option value="45" selected>45 minutes</option>
              <option value="60">60 minutes (1 hour)</option>
              <option value="90">90 minutes</option>
            </select>
          </div>
        </div>

        <div>
          <label style="display: block; font-size: 0.82rem; font-weight: 600; color: #334155; margin-bottom: 0.25rem;">
            Instructions / Custom Notes (Optional):
          </label>
          <textarea id="schedule-notes-input" rows="2" placeholder="e.g. Please be prepared with a modern browser for live technical discussion." style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.45rem 0.6rem; font-size: 0.85rem; font-family: inherit;"></textarea>
        </div>

        <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 0.6rem 0.75rem; font-size: 0.8rem; color: #64748B;">
          💡 <strong>What happens next:</strong> A Google Meet conference link is generated and an invitation email is sent directly to the candidate with joining instructions.
        </div>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.25rem; border-top: 1px solid #E2E8F0; padding-top: 0.75rem;">
        <button class="btn btn-sm" onclick="InterviewSetupView.closeModal()" style="background: #FFFFFF; color: #475569; border: 1px solid #CBD5E1; font-weight: 600; padding: 0.45rem 1rem;">
          Cancel
        </button>
        <button class="btn btn-sm btn-primary" id="schedule-submit-btn" onclick="InterviewSetupView.submitSchedule()" style="background: #2563EB; font-weight: 600; padding: 0.45rem 1.25rem;">
          ✉️ Schedule & Send Invitation
        </button>
      </div>
    `;

    overlay.style.display = 'flex';
  },

  async submitSchedule() {
    const dateVal = document.getElementById('schedule-date-input')?.value;
    const timeVal = document.getElementById('schedule-time-input')?.value;
    const tzVal = document.getElementById('schedule-tz-input')?.value || 'UTC';
    const durVal = parseInt(document.getElementById('schedule-duration-input')?.value || '45');
    const notesVal = document.getElementById('schedule-notes-input')?.value?.trim() || null;
    const submitBtn = document.getElementById('schedule-submit-btn');

    if (!dateVal || !timeVal) {
      toast.error("Please specify both date and start time.");
      return;
    }

    const scheduledStart = new Date(`${dateVal}T${timeVal}:00`).toISOString();

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerText = "Scheduling...";
    }

    try {
      const scheduleRes = await api.interviewSchedules.scheduleApplication(this.currentApplicationId, {
        scheduled_start: scheduledStart,
        timezone: tzVal,
        duration_minutes: durVal,
        invitation_notes: notesVal,
      });

      this.currentSchedule = scheduleRes;
      toast.success("Interview scheduled & invitation sent to candidate!");
      this.closeModal();
      this.renderInterviewPlan();
    } catch (err) {
      console.error(err);
      toast.error(`Scheduling failed: ${err.message}`);
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerText = "✉️ Schedule & Send Invitation";
      }
    }
  },

  closeModal() {
    const overlay = document.getElementById('setup-modal-overlay');
    if (overlay) overlay.style.display = 'none';
  },
};

window.interviewSetupView = window.InterviewSetupView;
