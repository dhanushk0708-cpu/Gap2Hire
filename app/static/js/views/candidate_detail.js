// ==========================================================================
// Candidate Profile, Resume, Evidence & Shortlist Decision View
// Clean Professional B2B SaaS Design System
// ==========================================================================

const candidateDetailView = {
  currentAppId: null,
  screeningReport: null,
  screeningProfile: null,
  application: null,
  activeTab: "screening",

  async render(applicationId) {
    const container = document.getElementById("main-view");
    if (!container) return;

    this.currentAppId = applicationId;
    appState.activeApplicationId = applicationId;

    container.innerHTML = `
      <div id="candidate-detail-wrapper" style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.75rem; color: #0F172A; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 2rem;">
        <!-- Top Nav & Breadcrumb -->
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem;">
          <a href="javascript:void(0)" onclick="router.navigate('candidates')" style="font-size: 0.875rem; color: #475569; font-weight: 500; text-decoration: none; display: flex; align-items: center; gap: 0.35rem;">
            <span>←</span> Back to Screening Queue
          </a>
          <span style="font-size: 0.8rem; color: #64748B; font-family: var(--font-mono);" id="cand-app-id">ID: ${applicationId.slice(0, 8)}...</span>
        </div>

        <!-- Header Profile Card -->
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 1rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
          <div>
            <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
              <h1 id="cand-name" style="font-size: 1.75rem; font-weight: 700; color: #0F172A; margin: 0;">Loading Candidate...</h1>
              <span id="cand-shortlist-badge" style="background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; font-size: 0.8rem; font-weight: 600; padding: 0.25rem 0.65rem; border-radius: 9999px;">
                Pending Review
              </span>
            </div>
            <p id="cand-email" style="color: #475569; font-size: 0.875rem; margin-top: 0.35rem; margin-bottom: 0;">-</p>
          </div>

          <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
            <button class="btn btn-secondary btn-sm" onclick="candidateDetailView.runScreening()" style="background: #F1F5F9; color: #0F172A; border: 1px solid #CBD5E1; font-weight: 500;">
              <span>⚡</span> Run Screening Evaluation
            </button>
            <div id="shortlist-action-btns" style="display: flex; gap: 0.5rem;">
              <button class="btn btn-sm" onclick="candidateDetailView.applyShortlist('SHORTLISTED')" style="background: #059669; color: #FFFFFF; border: none; font-weight: 600; padding: 0.4rem 0.85rem; border-radius: 6px;">
                <span>⭐</span> Shortlist
              </button>
              <button class="btn btn-sm" onclick="candidateDetailView.applyShortlist('NOT_SHORTLISTED')" style="background: #FFFFFF; color: #DC2626; border: 1px solid #FCA5A5; font-weight: 600; padding: 0.4rem 0.85rem; border-radius: 6px;">
                <span>✕</span> Not Shortlist
              </button>
            </div>
            <button id="btn-goto-interview" class="btn btn-primary btn-sm" style="display: none; background: #2563EB; font-weight: 600;" onclick="candidateDetailView.startInterviewFlow()">
              <span>📋</span> Prepare Interview →
            </button>
          </div>
        </div>

        <!-- Tab Navigation (Clean B2B SaaS Style) -->
        <div style="display: flex; gap: 0.35rem; background: #E2E8F0; padding: 4px; border-radius: 8px; width: fit-content; margin-bottom: 1.5rem; flex-wrap: wrap;">
          <button class="cand-tab-btn active" id="tab-screening" onclick="candidateDetailView.switchTab('screening')" style="padding: 0.45rem 0.85rem; font-size: 0.825rem; font-weight: 600; border-radius: 6px; border: none; cursor: pointer; transition: all 0.15s ease; background: #FFFFFF; color: #0F172A; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            📋 Screening Analysis
          </button>
          <button class="cand-tab-btn" id="tab-evidence" onclick="candidateDetailView.switchTab('evidence')" style="padding: 0.45rem 0.85rem; font-size: 0.825rem; font-weight: 500; border-radius: 6px; border: none; cursor: pointer; transition: all 0.15s ease; background: transparent; color: #475569;">
            🧩 Capability Evidence
          </button>
          <button class="cand-tab-btn" id="tab-resume" onclick="candidateDetailView.switchTab('resume')" style="padding: 0.45rem 0.85rem; font-size: 0.825rem; font-weight: 500; border-radius: 6px; border: none; cursor: pointer; transition: all 0.15s ease; background: transparent; color: #475569;">
            📄 Resume
          </button>
          <button class="cand-tab-btn" id="tab-replay" onclick="candidateDetailView.switchTab('replay')" style="padding: 0.45rem 0.85rem; font-size: 0.825rem; font-weight: 500; border-radius: 6px; border: none; cursor: pointer; transition: all 0.15s ease; background: transparent; color: #475569;">
            ⏪ Decision Replay
          </button>
          <button class="cand-tab-btn" id="tab-outcomes" onclick="candidateDetailView.switchTab('outcomes')" style="padding: 0.45rem 0.85rem; font-size: 0.825rem; font-weight: 500; border-radius: 6px; border: none; cursor: pointer; transition: all 0.15s ease; background: transparent; color: #475569;">
            📊 Post-Hire Outcomes
          </button>
          <button class="cand-tab-btn" id="tab-autopsy" onclick="candidateDetailView.switchTab('autopsy')" style="padding: 0.45rem 0.85rem; font-size: 0.825rem; font-weight: 500; border-radius: 6px; border: none; cursor: pointer; transition: all 0.15s ease; background: transparent; color: #475569;">
            🔬 Hiring Autopsy
          </button>
        </div>

        <!-- Tab Contents -->
        <div id="tab-content-container">
          <p style="color: #64748B; padding: 2rem 0; text-align: center;">Loading candidate screening analysis...</p>
        </div>
      </div>
    `;

    await this.loadData();
  },

  async loadData() {
    try {
      const [report, profile, application] = await Promise.all([
        api.screening.getScreeningReport(this.currentAppId),
        api.screening.getScreeningProfile(this.currentAppId).catch(() => null),
        api.getApplicationDetail(this.currentAppId).catch(() => null),
      ]);
      this.screeningReport = report;
      this.screeningProfile = profile;
      this.application = application;
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

    const isDemo = Boolean(
      (this.application && this.application.is_demo) ||
      (rep.candidate_email && (rep.candidate_email.includes("@demo.gap2hire.local") || rep.candidate_email.includes("@synthetic.gap2hire.local")))
    );
    if (nameEl) {
      nameEl.innerHTML = `<span>${rep.candidate_name || "Applicant Profile"}</span>${
        isDemo
          ? `<span style="background: #F3E8FF; color: #7E22CE; border: 1px solid #D8B4FE; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 9999px; margin-left: 0.5rem; vertical-align: middle;">DEMO CANDIDATE</span>`
          : ""
      }`;
    }
    if (emailEl) emailEl.textContent = `${rep.candidate_email} • Applied for: ${rep.job_title}`;

    if (badgeEl) {
      if (rep.shortlist_status === "SHORTLISTED") {
        badgeEl.style.background = "#ECFDF5";
        badgeEl.style.color = "#065F46";
        badgeEl.style.borderColor = "#A7F3D0";
        badgeEl.textContent = "⭐ Shortlisted";
      } else if (rep.shortlist_status === "NOT_SHORTLISTED") {
        badgeEl.style.background = "#FFF1F2";
        badgeEl.style.color = "#9F1239";
        badgeEl.style.borderColor = "#FECDD3";
        badgeEl.textContent = "Not Shortlisted";
      } else if (rep.shortlist_status === "HOLD") {
        badgeEl.style.background = "#FFFBEB";
        badgeEl.style.color = "#92400E";
        badgeEl.style.borderColor = "#FDE68A";
        badgeEl.textContent = "Hold for Review";
      } else {
        badgeEl.style.background = "#F1F5F9";
        badgeEl.style.color = "#475569";
        badgeEl.style.borderColor = "#CBD5E1";
        badgeEl.textContent = "Pending Review";
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
    document.querySelectorAll(".cand-tab-btn").forEach((btn) => {
      btn.style.background = "transparent";
      btn.style.color = "#475569";
      btn.style.fontWeight = "500";
      btn.style.boxShadow = "none";
    });
    const activeBtn = document.getElementById(`tab-${tabName}`);
    if (activeBtn) {
      activeBtn.style.background = "#FFFFFF";
      activeBtn.style.color = "#0F172A";
      activeBtn.style.fontWeight = "600";
      activeBtn.style.boxShadow = "0 1px 2px rgba(0,0,0,0.05)";
    }
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
    } else if (this.activeTab === "replay") {
      this.renderDecisionReplayTab(container);
    } else if (this.activeTab === "outcomes") {
      this.renderPostHireOutcomesTab(container);
    } else if (this.activeTab === "autopsy") {
      this.renderHiringAutopsyTab(container);
    }
  },

  renderScreeningTab(container) {
    const rep = this.screeningReport;
    const reqs = rep.requirements_evaluated || [];
    const prof = this.screeningProfile;

    // Factual counts from backend data
    const totalReqs = rep.total_requirements_count || reqs.length;
    const supportedCount = rep.supported_count || reqs.filter((r) => r.status === "MET").length;
    const verifiedCount = rep.verified_count || reqs.filter((r) => r.provenance === "VERIFIED").length;
    const demonstratedCount =
      rep.demonstrated_count ||
      reqs.filter((r) => r.provenance === "DEMONSTRATED" || r.provenance === "CORROBORATED").length;
    const claimsCount = rep.claims_count || reqs.filter((r) => r.provenance === "CLAIM").length;
    const unknownCount =
      rep.unknown_count || reqs.filter((r) => r.status === "UNKNOWN" || r.provenance === "UNKNOWN").length;
    const verificationNeededCount =
      rep.verification_needed_count ||
      reqs.filter((r) => r.verification_needed || (r.status === "MET" && r.provenance !== "VERIFIED")).length;

    // Factual status headline & notice
    let statusPill = `<span style="background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 9999px;">Resume claims identified</span>`;
    if (verifiedCount > 0) {
      statusPill = `<span style="background: #F5F3FF; color: #6D28D9; border: 1px solid #DDD6FE; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 9999px;">Verified capabilities on file</span>`;
    } else if (demonstratedCount > 0) {
      statusPill = `<span style="background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 9999px;">Demonstrated project evidence</span>`;
    } else if (supportedCount === 0) {
      statusPill = `<span style="background: #F8FAFC; color: #64748B; border: 1px solid #CBD5E1; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 9999px;">No evidence detected</span>`;
    }

    container.innerHTML = `
      <div style="display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: 1.5rem; align-items: start;">
        <!-- Left Column: Capability Requirements & Evidence -->
        <div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
            <div>
              <h3 style="font-size: 1.15rem; font-weight: 700; color: #0F172A; margin: 0;">Requirements & Capability Evaluation</h3>
              <p style="font-size: 0.8rem; color: #64748B; margin-top: 0.2rem; margin-bottom: 0;">Factual evaluation separating applicant claims from demonstrated evidence and verification.</p>
            </div>
            <span style="font-size: 0.8rem; color: #475569; font-weight: 600; background: #FFFFFF; border: 1px solid #E2E8F0; padding: 0.25rem 0.65rem; border-radius: 6px;">
              ${supportedCount}/${totalReqs} Supported
            </span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 1rem;">
            ${reqs
              .map((r) => {
                // Determine clear requirement status label (avoiding ambiguous standalone "MET")
                let statusBadge = `<span style="background: #F0FDF4; color: #166534; border: 1px solid #BBF7D0; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 6px;">Requirement Supported</span>`;
                if (r.status === "INSUFFICIENT") {
                  statusBadge = `<span style="background: #FFF1F2; color: #9F1239; border: 1px solid #FECDD3; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 6px;">Insufficient Evidence</span>`;
                } else if (r.status === "UNKNOWN") {
                  statusBadge = `<span style="background: #F8FAFC; color: #475569; border: 1px solid #CBD5E1; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 6px;">Unknown / Not Found</span>`;
                } else if (r.status === "NEEDS_REVIEW") {
                  statusBadge = `<span style="background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 6px;">Needs Verification</span>`;
                }

                // Evidence status pill
                let provPill = `<span style="background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 4px; text-transform: uppercase;">CLAIM</span>`;
                if (r.provenance === "DEMONSTRATED") {
                  provPill = `<span style="background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 4px; text-transform: uppercase;">DEMONSTRATED</span>`;
                } else if (r.provenance === "VERIFIED") {
                  provPill = `<span style="background: #F5F3FF; color: #6D28D9; border: 1px solid #DDD6FE; font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 4px; text-transform: uppercase;">VERIFIED</span>`;
                } else if (r.provenance === "UNKNOWN") {
                  provPill = `<span style="background: #F8FAFC; color: #64748B; border: 1px solid #CBD5E1; font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 4px; text-transform: uppercase;">UNKNOWN</span>`;
                }

                // Source label
                let sourceLabel = "Candidate Resume";
                if (r.provenance === "VERIFIED") {
                  sourceLabel = "Practical Assessment";
                } else if (r.provenance === "DEMONSTRATED") {
                  sourceLabel = r.source_url
                    ? `<a href="${r.source_url}" target="_blank" style="color: #2563EB; text-decoration: underline;">GitHub Repository ↗</a>`
                    : "GitHub — public repository";
                } else if (r.status === "UNKNOWN") {
                  sourceLabel = "No source detected";
                }

                // Verification state
                let verifState = `<span style="color: #64748B; font-weight: 600;">NOT YET VERIFIED</span>`;
                if (r.provenance === "VERIFIED" || r.verification_status === "PASSED") {
                  verifState = `<span style="color: #059669; font-weight: 700;">PASSED</span>`;
                }

                // Next Step
                let nextStep = "Practical verification";
                if (r.provenance === "VERIFIED") {
                  nextStep = "Verified";
                } else if (r.provenance === "DEMONSTRATED") {
                  nextStep = "Interview / practical verification";
                } else if (r.status === "UNKNOWN" || r.status === "INSUFFICIENT") {
                  nextStep = "Technical interview probing";
                }

                return `
                  <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.15rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
                      <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-weight: 700; font-size: 1.05rem; color: #0F172A;">${r.requirement_name}</span>
                        <span style="font-size: 0.7rem; color: #475569; background: #F1F5F9; border: 1px solid #E2E8F0; padding: 0.1rem 0.4rem; border-radius: 4px;">
                          Requirement
                        </span>
                      </div>
                      <div>${statusBadge}</div>
                    </div>

                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem 1rem; font-size: 0.8rem; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 0.75rem; margin-bottom: 0.75rem;">
                      <div>
                        <span style="color: #64748B; font-weight: 500;">Evidence Status:</span>
                        <span style="margin-left: 0.35rem;">${provPill}</span>
                      </div>
                      <div>
                        <span style="color: #64748B; font-weight: 500;">Source:</span>
                        <span style="color: #0F172A; font-weight: 600; margin-left: 0.35rem;">${sourceLabel}</span>
                      </div>
                      <div>
                        <span style="color: #64748B; font-weight: 500;">Strength:</span>
                        <span style="color: #0F172A; font-weight: 600; margin-left: 0.35rem;">${r.strength || "NONE"}</span>
                      </div>
                      <div>
                        <span style="color: #64748B; font-weight: 500;">Verification:</span>
                        <span style="margin-left: 0.35rem;">${verifState}</span>
                      </div>
                      <div style="grid-column: 1 / -1; border-top: 1px dashed #E2E8F0; padding-top: 0.4rem; margin-top: 0.2rem;">
                        <span style="color: #64748B; font-weight: 500;">Next Step:</span>
                        <span style="color: #2563EB; font-weight: 600; margin-left: 0.35rem;">${nextStep}</span>
                      </div>
                    </div>

                    ${
                      r.evidence_found
                        ? `<div style="background: #F1F5F9; border-left: 3px solid #3B82F6; padding: 0.5rem 0.75rem; font-size: 0.8rem; color: #334155; font-family: var(--font-mono); border-radius: 0 4px 4px 0; margin-bottom: 0.4rem;">
                            "${r.evidence_found}"
                          </div>`
                        : `<div style="font-size: 0.75rem; color: #94A3B8; font-style: italic; margin-bottom: 0.4rem;">No explicit excerpt found in candidate sources.</div>`
                    }
                    <div style="font-size: 0.78rem; color: #64748B; line-height: 1.4;">${r.reason}</div>
                  </div>
                `;
              })
              .join("")}
          </div>
        </div>

        <!-- Right Column: Factual Evidence Summary & Recruiter Gate -->
        <div style="display: flex; flex-direction: column; gap: 1.25rem;">
          <!-- Card 1: Factual Evidence Summary -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
              <h4 style="font-size: 0.95rem; font-weight: 700; color: #0F172A; text-transform: uppercase; letter-spacing: 0.05em; margin: 0;">
                Screening Status
              </h4>
              ${statusPill}
            </div>

            <div style="font-size: 1.15rem; font-weight: 700; color: #0F172A; margin-bottom: 1rem;">
              ${supportedCount} / ${totalReqs} requirements have supporting evidence
            </div>

            <!-- Factual Metrics Breakdown -->
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.65rem; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 0.85rem; margin-bottom: 1.25rem;">
              <div style="display: flex; justify-content: space-between; font-size: 0.825rem;">
                <span style="color: #64748B;">Verified:</span>
                <strong style="color: ${verifiedCount > 0 ? '#059669' : '#0F172A'};">${verifiedCount}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 0.825rem;">
                <span style="color: #64748B;">Demonstrated:</span>
                <strong style="color: ${demonstratedCount > 0 ? '#047857' : '#0F172A'};">${demonstratedCount}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 0.825rem;">
                <span style="color: #64748B;">Resume claims:</span>
                <strong style="color: #1D4ED8;">${claimsCount}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 0.825rem;">
                <span style="color: #64748B;">Unknown:</span>
                <strong style="color: ${unknownCount > 0 ? '#D97706' : '#64748B'};">${unknownCount}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 0.825rem; grid-column: 1 / -1; border-top: 1px dashed #E2E8F0; padding-top: 0.5rem;">
                <span style="color: #64748B;">Verification needed:</span>
                <strong style="color: #B45309;">${verificationNeededCount}</strong>
              </div>
            </div>

            <!-- Factual Callout Notice -->
            <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 6px; padding: 0.75rem; font-size: 0.825rem; color: #1E40AF; line-height: 1.5; margin-bottom: 1rem;">
              ℹ️ <strong>Evidence Finding:</strong> ${
                verifiedCount === 0 && demonstratedCount === 0
                  ? "Resume evidence supports initial screening. Independent verification is still required."
                  : verifiedCount === 0
                  ? "Preliminary project artifacts demonstrate capability. Live verification remains required before final hiring."
                  : "Candidate has independently verified capabilities on record."
              }
            </div>

            <!-- Probing Needs -->
            ${
              rep.unknowns_summary && rep.unknowns_summary.length > 0
                ? `<div style="border-top: 1px solid #E2E8F0; padding-top: 0.85rem;">
                    <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase; margin-bottom: 0.4rem;">
                      Requires Technical Probing
                    </div>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.35rem;">
                      ${rep.unknowns_summary.map((u) => `<span style="background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px;">${u}</span>`).join("")}
                    </div>
                  </div>`
                : ""
            }
          </div>

          <!-- Card 2: Human Recruiter Shortlist Gate -->
          <div style="background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
              <h4 style="font-size: 0.95rem; font-weight: 700; color: #0F172A; margin: 0;">
                Human Recruiter Shortlist Gate
              </h4>
              <span style="font-size: 0.72rem; color: #059669; font-weight: 600; background: #ECFDF5; border: 1px solid #A7F3D0; padding: 0.15rem 0.45rem; border-radius: 4px;">
                Human-Controlled
              </span>
            </div>

            <p style="font-size: 0.8rem; color: #64748B; line-height: 1.5; margin-bottom: 1rem;">
              Gap2Hire provides automated, evidence-grounded screening recommendations. The final hiring and interview progression decision remains strictly human-controlled.
            </p>

            <div style="margin-bottom: 1rem;">
              <label style="display: block; font-size: 0.8rem; font-weight: 600; color: #334155; margin-bottom: 0.35rem;">
                Recruiter Decision Notes / Rationale
              </label>
              <textarea id="shortlist-reason-input" placeholder="e.g. Strong FastAPI and Python evidence; verify PostgreSQL indexing in technical interview..." rows="3" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.6rem; font-size: 0.85rem; color: #0F172A; background: #FFFFFF; font-family: inherit; line-height: 1.4; resize: vertical;">${rep.shortlist_reason || ""}</textarea>
            </div>

            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
              <button class="btn btn-sm" onclick="candidateDetailView.applyShortlist('SHORTLISTED')" style="background: #059669; color: #FFFFFF; border: none; font-weight: 600; padding: 0.6rem; border-radius: 6px; width: 100%; text-align: center; cursor: pointer;">
                ⭐ Shortlist Candidate
              </button>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
                <button class="btn btn-sm" onclick="candidateDetailView.applyShortlist('NOT_SHORTLISTED')" style="background: #FFFFFF; color: #DC2626; border: 1px solid #FCA5A5; font-weight: 600; padding: 0.5rem; border-radius: 6px; cursor: pointer;">
                  ✕ Do Not Shortlist
                </button>
                <button class="btn btn-sm" onclick="candidateDetailView.applyShortlist('HOLD')" style="background: #FFFFFF; color: #D97706; border: 1px solid #FDE68A; font-weight: 600; padding: 0.5rem; border-radius: 6px; cursor: pointer;">
                  ⏸ Hold for Review
                </button>
              </div>
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
      <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
        <!-- Header & Semantic Progression Banner -->
        <div style="margin-bottom: 1.5rem;">
          <h3 style="font-size: 1.2rem; font-weight: 700; color: #0F172A; margin: 0 0 0.35rem 0;">Evidence Provenance & Verification Progression</h3>
          <p style="font-size: 0.85rem; color: #64748B; margin: 0 0 1rem 0;">
            Evidence Progression Principle: Resume excerpts represent applicant claims. Capabilities are only DEMONSTRATED when confirmed through public repositories or project artifacts, and VERIFIED when passed in practical assessments or live interviews.
          </p>

          <!-- Progression Steps Bar -->
          <div style="display: flex; align-items: center; justify-content: space-between; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 0.85rem 1.25rem; font-size: 0.825rem; flex-wrap: wrap; gap: 0.5rem;">
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <span style="background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; font-weight: 700; padding: 0.15rem 0.45rem; border-radius: 4px; font-size: 0.7rem;">1. CLAIM</span>
              <span style="color: #475569; font-weight: 600;">Resume Claim</span>
            </div>
            <span style="color: #94A3B8;">→</span>
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <span style="background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; font-weight: 700; padding: 0.15rem 0.45rem; border-radius: 4px; font-size: 0.7rem;">2. DEMONSTRATED</span>
              <span style="color: #475569; font-weight: 600;">Public Project Artifact</span>
            </div>
            <span style="color: #94A3B8;">→</span>
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <span style="background: #F5F3FF; color: #6D28D9; border: 1px solid #DDD6FE; font-weight: 700; padding: 0.15rem 0.45rem; border-radius: 4px; font-size: 0.7rem;">3. VERIFIED</span>
              <span style="color: #475569; font-weight: 600;">Practical Verification Passed</span>
            </div>
          </div>
        </div>

        <!-- Evidence Cards Grid -->
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1.25rem;">
          ${reqs
            .map((r) => {
              const isVerified = r.provenance === "VERIFIED";
              const isDemo = r.provenance === "DEMONSTRATED";
              const isClaim = r.provenance === "CLAIM";

              let statusColor = "#EFF6FF";
              let statusText = "#1D4ED8";
              let statusBorder = "#BFDBFE";
              let evidenceType = "Resume claim";
              let sourceText = "Candidate resume";

              if (isVerified) {
                statusColor = "#F5F3FF";
                statusText = "#6D28D9";
                statusBorder = "#DDD6FE";
                evidenceType = "Practical assessment";
                sourceText = "Practical Assessment (Passed)";
              } else if (isDemo) {
                statusColor = "#ECFDF5";
                statusText = "#047857";
                statusBorder = "#A7F3D0";
                evidenceType = "Public project artifact";
                sourceText = r.source_url
                  ? `<a href="${r.source_url}" target="_blank" style="color: #2563EB; text-decoration: underline;">${r.source_type || 'GitHub'} Repository ↗</a>`
                  : (r.source_type ? `${r.source_type} Project Artifact` : "GitHub — public repository");
              } else if (r.status === "UNKNOWN") {
                statusColor = "#F8FAFC";
                statusText = "#64748B";
                statusBorder = "#CBD5E1";
                evidenceType = "No evidence found";
                sourceText = "No source detected";
              }

              return `
                <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1.25rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02); display: flex; flex-direction: column; justify-content: space-between;">
                  <div>
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
                      <strong style="font-size: 1.1rem; color: #0F172A;">${r.requirement_name}</strong>
                      <span style="background: ${statusColor}; color: ${statusText}; border: 1px solid ${statusBorder}; font-size: 0.72rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 4px; text-transform: uppercase;">
                        ${r.provenance || "CLAIM"}
                      </span>
                    </div>

                    <div style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.8rem; margin-bottom: 0.85rem;">
                      <div>
                        <span style="color: #64748B;">Evidence:</span>
                        <span style="color: #0F172A; font-weight: 600; margin-left: 0.35rem;">${evidenceType}</span>
                      </div>
                      <div>
                        <span style="color: #64748B;">Source:</span>
                        <span style="color: #0F172A; font-weight: 600; margin-left: 0.35rem;">${sourceText}</span>
                      </div>
                      <div>
                        <span style="color: #64748B;">Strength:</span>
                        <span style="color: #0F172A; font-weight: 600; margin-left: 0.35rem;">${r.strength || "NONE"}</span>
                      </div>
                      <div>
                        <span style="color: #64748B;">Verification:</span>
                        <span style="font-weight: 600; margin-left: 0.35rem; color: ${isVerified ? '#059669' : '#64748B'};">
                          ${isVerified ? "PASSED" : "Pending Verification"}
                        </span>
                      </div>
                    </div>
                  </div>

                  ${
                    r.evidence_found
                      ? `<div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 0.6rem 0.75rem; font-size: 0.78rem; color: #334155; font-family: var(--font-mono); line-height: 1.4;">
                          "${r.evidence_found}"
                        </div>`
                      : `<div style="font-size: 0.75rem; color: #94A3B8; font-style: italic;">No concrete excerpt identified.</div>`
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
    const resumeText =
      this.application?.resume_text ||
      this.screeningReport?.resume_text ||
      "No extracted resume text is available for this application.";

    container.innerHTML = `
      <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 0.75rem;">
          <div>
            <h3 style="font-size: 1.15rem; font-weight: 700; color: #0F172A; margin: 0;">Extracted Resume Text & Provenance Claims</h3>
            <p style="font-size: 0.8rem; color: #64748B; margin-top: 0.2rem; margin-bottom: 0;">
              Deterministic text extracted from uploaded resume file. Excerpts are classified strictly as CLAIM provenance.
            </p>
          </div>
          <span style="background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 6px;">
            Parsed & Indexed
          </span>
        </div>

        <div style="background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 1.25rem; font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.6; color: #1E293B; white-space: pre-wrap; max-height: 600px; overflow-y: auto;">
${resumeText}
        </div>
      </div>
    `;
  },

  async renderDecisionReplayTab(container) {
    container.innerHTML = `<div style="text-align: center; padding: 2rem; color: #64748B;">Reconstructing decision state snapshot...</div>`;
    try {
      const replay = await api.decisionReplay.getReplay(this.currentAppId);
      const dec = replay.decision_context;
      const iv = replay.interview_context;

      container.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 1.25rem;">
          <!-- Card 1: Decision Snapshot -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem;">
              <div>
                <span style="font-size: 0.75rem; font-weight: 700; color: #4338CA; background: #EEF2FF; padding: 2px 8px; border-radius: 4px; text-transform: uppercase;">
                  Historical Audit Replay
                </span>
                <h3 style="font-size: 1.2rem; font-weight: 700; color: #0F172A; margin: 0.35rem 0 0 0;">
                  Decision Context at Timestamp
                </h3>
              </div>
              <span class="badge ${dec.decision === 'SELECTED' ? 'badge-success' : dec.decision === 'REJECTED' ? 'badge-danger' : 'badge-warning'}" style="font-size: 0.85rem; padding: 6px 14px;">
                DECISION: ${dec.decision}
              </span>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; font-size: 0.85rem;">
              <div><strong>Decision Maker:</strong> ${dec.decided_by_name}</div>
              <div><strong>Decided At:</strong> ${new Date(dec.decided_at).toLocaleString()}</div>
              <div><strong>Job:</strong> ${dec.job_title}</div>
              <div><strong>Status:</strong> ${dec.application_status}</div>
            </div>

            <div style="background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 1rem; font-size: 0.875rem; line-height: 1.5;">
              <strong style="color: #334155;">Human Decision Rationale:</strong>
              <div style="color: #0F172A; margin-top: 0.25rem;">"${dec.decision_reason}"</div>
            </div>
          </div>

          <!-- Card 2: Knowledge State Available at Decision Time -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <h4 style="font-size: 1rem; font-weight: 700; color: #0F172A; margin: 0 0 1rem 0;">
              Evidence State Available During Evaluation
            </h4>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
              <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1rem;">
                <div style="font-size: 0.8rem; font-weight: 700; color: #059669; text-transform: uppercase; margin-bottom: 0.5rem;">
                  Demonstrated in Interview (${iv?.demonstrated_capabilities?.length || 0})
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 0.35rem;">
                  ${(iv?.demonstrated_capabilities || []).map(c => `<span class="badge badge-success" style="font-size: 0.75rem;">${c}</span>`).join('') || '<span style="color: #94A3B8; font-size: 0.8rem;">None</span>'}
                </div>
              </div>

              <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1rem;">
                <div style="font-size: 0.8rem; font-weight: 700; color: #D97706; text-transform: uppercase; margin-bottom: 0.5rem;">
                  Unknown / Unverified at Decision (${iv?.unknown_capabilities?.length || 0})
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 0.35rem;">
                  ${(iv?.unknown_capabilities || []).map(c => `<span class="badge badge-warning" style="font-size: 0.75rem;">${c}</span>`).join('') || '<span style="color: #94A3B8; font-size: 0.8rem;">None</span>'}
                </div>
              </div>
            </div>

            <!-- Decision History Chain -->
            <h4 style="font-size: 0.9rem; font-weight: 700; color: #0F172A; margin: 1.25rem 0 0.5rem 0;">
              Audit History Chain (${replay.decision_history?.length || 0})
            </h4>
            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
              ${(replay.decision_history || []).map((h, i) => `
                <div style="padding: 0.65rem 0.85rem; background: #F8FAFC; border-radius: 6px; border-left: 3px solid #6366F1; font-size: 0.8rem; display: flex; justify-content: space-between; align-items: center;">
                  <div><strong>${h.decision}</strong> by ${h.decided_by}: "${h.decision_reason}"</div>
                  <span style="color: #64748B;">${new Date(h.decided_at).toLocaleString()}</span>
                </div>
              `).join('')}
            </div>

            <!-- Limitations -->
            <div style="margin-top: 1.25rem; padding: 0.75rem; background: #F1F5F9; border-radius: 6px; font-size: 0.75rem; color: #64748B; line-height: 1.4;">
              <strong>Architectural Fidelity Note:</strong> ${(replay.limitations || []).join(' ')}
            </div>
          </div>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `<div style="color: #EF4444; padding: 2rem; text-align: center;">Failed to load Decision Replay: ${err.message}</div>`;
    }
  },

  async renderPostHireOutcomesTab(container) {
    container.innerHTML = `<div style="text-align: center; padding: 2rem; color: #64748B;">Loading post-hire outcomes...</div>`;
    try {
      const resp = await api.postHireOutcomes.listOutcomes(this.currentAppId);
      const outcomes = resp.outcomes || [];

      container.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 1.25rem;">
          <!-- Record New Outcome Card -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
              <div>
                <h3 style="font-size: 1.15rem; font-weight: 700; color: #0F172A; margin: 0;">
                  Record Post-Hire Work Outcome Observation
                </h3>
                <p style="font-size: 0.8rem; color: #64748B; margin: 0.2rem 0 0 0;">
                  Structured feedback comparing expected capability vs actual on-the-job execution.
                </p>
              </div>
              <span style="background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 6px;">
                Organizational Learning
              </span>
            </div>

            <form id="form-new-outcome" onsubmit="candidateDetailView.submitNewOutcome(event)" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
              <div>
                <label style="display: block; font-size: 0.8rem; font-weight: 600; color: #334155; margin-bottom: 0.35rem;">Capability Name *</label>
                <input type="text" id="out-cap-name" required placeholder="e.g. Redis Distributed Caching" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.5rem; font-size: 0.85rem;" />
              </div>

              <div>
                <label style="display: block; font-size: 0.8rem; font-weight: 600; color: #334155; margin-bottom: 0.35rem;">Observation Window *</label>
                <select id="out-period" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.5rem; font-size: 0.85rem; background: #FFF;">
                  <option value="90_DAYS">90 Days</option>
                  <option value="60_DAYS">60 Days</option>
                  <option value="30_DAYS">30 Days</option>
                  <option value="PROBATION">Probation Period</option>
                </select>
              </div>

              <div>
                <label style="display: block; font-size: 0.8rem; font-weight: 600; color: #334155; margin-bottom: 0.35rem;">Outcome Status *</label>
                <select id="out-status" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.5rem; font-size: 0.85rem; background: #FFF;">
                  <option value="MEETS_EXPECTATION">✅ Meets Expectation</option>
                  <option value="PARTIALLY_MEETS_EXPECTATION">⚠️ Partially Meets Expectation</option>
                  <option value="NEEDS_DEVELOPMENT">🔧 Needs Development</option>
                  <option value="INSUFFICIENT_OBSERVATION">❓ Insufficient Observation</option>
                </select>
              </div>

              <div>
                <label style="display: block; font-size: 0.8rem; font-weight: 600; color: #334155; margin-bottom: 0.35rem;">Evidence / Artifact Reference</label>
                <input type="text" id="out-ref" placeholder="e.g. PR #1042 / Architecture RFC" style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.5rem; font-size: 0.85rem;" />
              </div>

              <div style="grid-column: span 2;">
                <label style="display: block; font-size: 0.8rem; font-weight: 600; color: #334155; margin-bottom: 0.35rem;">Observed Outcome Description *</label>
                <textarea id="out-desc" required rows="2" placeholder="Factual observation: e.g. Candidate successfully configured cluster Redis failover but required guidance on distributed lock ttl." style="width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0.5rem; font-size: 0.85rem;"></textarea>
              </div>

              <div style="grid-column: span 2; display: flex; justify-content: flex-end;">
                <button type="submit" class="btn btn-primary btn-sm" style="background: #2563EB; font-weight: 600; padding: 0.5rem 1.25rem;">
                  Save Work Outcome Observation
                </button>
              </div>
            </form>
          </div>

          <!-- Existing Outcomes List -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <h4 style="font-size: 1rem; font-weight: 700; color: #0F172A; margin: 0 0 1rem 0;">
              Recorded Post-Hire Outcomes (${outcomes.length})
            </h4>

            ${outcomes.length === 0 ? `
              <div style="text-align: center; color: #94A3B8; padding: 1.5rem 0; font-style: italic;">
                No post-hire outcomes recorded yet. Use the form above to record 30/60/90-day observations.
              </div>
            ` : `
              <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                ${outcomes.map(o => {
                  const badgeClass = o.outcome_status === 'MEETS_EXPECTATION' ? 'badge-success' : o.outcome_status === 'NEEDS_DEVELOPMENT' ? 'badge-danger' : 'badge-warning';
                  return `
                    <div style="padding: 1rem; background: #F8FAFC; border-radius: 8px; border-left: 3px solid #2563EB; display: flex; flex-direction: column; gap: 0.4rem;">
                      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                          <span style="font-weight: 700; color: #0F172A; font-size: 0.95rem;">${o.capability_name}</span>
                          <span class="badge ${badgeClass}" style="font-size: 0.75rem;">${o.outcome_status}</span>
                          <span style="font-size: 0.75rem; color: #64748B; background: #E2E8F0; padding: 2px 6px; border-radius: 4px;">${o.outcome_period}</span>
                        </div>
                        <span style="font-size: 0.75rem; color: #64748B;">Recorded by ${o.recorded_by_name} • ${new Date(o.recorded_at).toLocaleDateString()}</span>
                      </div>
                      <div style="font-size: 0.85rem; color: #334155; line-height: 1.4;">"${o.observed_outcome_description}"</div>
                      ${o.evidence_reference ? `<div style="font-size: 0.75rem; color: #2563EB;">🔗 Reference: ${o.evidence_reference}</div>` : ''}
                    </div>
                  `;
                }).join('')}
              </div>
            `}
          </div>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `<div style="color: #EF4444; padding: 2rem; text-align: center;">Failed to load outcomes: ${err.message}</div>`;
    }
  },

  async submitNewOutcome(event) {
    event.preventDefault();
    const capName = document.getElementById("out-cap-name")?.value;
    const period = document.getElementById("out-period")?.value;
    const outStatus = document.getElementById("out-status")?.value;
    const desc = document.getElementById("out-desc")?.value;
    const ref = document.getElementById("out-ref")?.value;

    try {
      await api.postHireOutcomes.createOutcome(this.currentAppId, {
        capability_name: capName,
        outcome_period: period,
        outcome_status: outStatus,
        observed_outcome_description: desc,
        evidence_reference: ref || null,
      });
      toast.success("Post-hire outcome recorded successfully!");
      const container = document.getElementById("tab-content-container");
      if (container) this.renderPostHireOutcomesTab(container);
    } catch (err) {
      toast.error(`Failed to record outcome: ${err.message}`);
    }
  },

  async renderHiringAutopsyTab(container) {
    container.innerHTML = `<div style="text-align: center; padding: 2rem; color: #64748B;">Running Hiring Autopsy analysis...</div>`;
    try {
      const autopsy = await api.hiringAutopsy.getAutopsy(this.currentAppId);

      container.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 1.25rem;">
          <!-- Header Banner -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.75rem;">
              <div>
                <span style="font-size: 0.75rem; font-weight: 700; color: #047857; background: #ECFDF5; padding: 2px 8px; border-radius: 4px; text-transform: uppercase;">
                  Continuous Process Improvement
                </span>
                <h3 style="font-size: 1.25rem; font-weight: 700; color: #0F172A; margin: 0.35rem 0 0.2rem 0;">
                  Hiring Autopsy & Learning Analysis
                </h3>
                <p style="font-size: 0.825rem; color: #64748B; margin: 0;">
                  Compares Expected Capabilities vs What Was Known During Hiring vs Observed Work Execution.
                </p>
              </div>
              <div style="font-size: 0.8rem; color: #334155; text-align: right;">
                <strong>Role:</strong> ${autopsy.job_title}<br />
                <span style="color: #64748B;">Evaluated Capabilities: ${autopsy.capability_comparison?.length || 0}</span>
              </div>
            </div>
          </div>

          <!-- Section 1: Facts & Observed Data Matrix -->
          <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <h4 style="font-size: 1rem; font-weight: 700; color: #0F172A; margin: 0 0 0.5rem 0;">
              📊 Facts & Observed Data Matrix
            </h4>
            <p style="font-size: 0.8rem; color: #64748B; margin: 0 0 1rem 0;">
              Objective side-by-side comparison across all hiring pipeline stages.
            </p>

            <div style="overflow-x: auto;">
              <table style="width: 100%; border-collapse: collapse; font-size: 0.825rem; text-align: left;">
                <thead>
                  <tr style="background: #F8FAFC; border-bottom: 2px solid #E2E8F0; color: #475569;">
                    <th style="padding: 0.65rem 0.75rem;">Capability</th>
                    <th style="padding: 0.65rem 0.75rem;">Pre-Hire Evidence</th>
                    <th style="padding: 0.65rem 0.75rem;">Interview Evaluation</th>
                    <th style="padding: 0.65rem 0.75rem;">Post-Hire Outcome</th>
                    <th style="padding: 0.65rem 0.75rem;">Grounded Observation</th>
                  </tr>
                </thead>
                <tbody>
                  ${(autopsy.capability_comparison || []).map(c => {
                    const postBadge = c.post_hire_outcome_status === 'MEETS_EXPECTATION' ? 'badge-success' : c.post_hire_outcome_status === 'NEEDS_DEVELOPMENT' ? 'badge-danger' : 'badge-warning';
                    return `
                      <tr style="border-bottom: 1px solid #F1F5F9;">
                        <td style="padding: 0.75rem; font-weight: 600; color: #0F172A;">${c.capability_name}</td>
                        <td style="padding: 0.75rem;"><span class="badge ${c.pre_hire_evidence_state === 'DEMONSTRATED' ? 'badge-success' : 'badge-warning'}" style="font-size: 0.72rem;">${c.pre_hire_evidence_state}</span></td>
                        <td style="padding: 0.75rem;"><span class="badge ${c.interview_demonstration_state === 'DEMONSTRATED_STRONG' ? 'badge-success' : 'badge-primary'}" style="font-size: 0.72rem;">${c.interview_demonstration_state}</span></td>
                        <td style="padding: 0.75rem;"><span class="badge ${postBadge}" style="font-size: 0.72rem;">${c.post_hire_outcome_status}</span></td>
                        <td style="padding: 0.75rem; color: #475569; line-height: 1.35;">${c.outcome_delta_observation}</td>
                      </tr>
                    `;
                  }).join('')}
                </tbody>
              </table>
            </div>
          </div>

          <!-- Section 2: AI Process Improvement Suggestions -->
          <div style="background: #FFFFFF; border: 2px solid #3B82F6; border-radius: 10px; padding: 1.5rem; box-shadow: 0 2px 4px rgba(59,130,246,0.06);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <h4 style="font-size: 1rem; font-weight: 700; color: #1E3A8A; margin: 0; display: flex; align-items: center; gap: 0.5rem;">
                <span>💡</span> AI Process Improvement Suggestions
              </h4>
              <span style="font-size: 0.72rem; font-weight: 700; color: #2563EB; background: #DBEAFE; padding: 2px 8px; border-radius: 4px;">
                Advisory Only • Non-Automated
              </span>
            </div>
            <p style="font-size: 0.8rem; color: #64748B; margin: 0 0 1rem 0;">
              Evidence-grounded suggestions to improve future interview rubrics and screening blueprints.
            </p>

            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
              ${(autopsy.ai_improvement_suggestions || []).map(s => `
                <div style="padding: 1rem; background: #F8FAFC; border: 1px solid #BFDBFE; border-radius: 8px;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap; gap: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                      <span class="badge badge-primary" style="font-size: 0.75rem; font-weight: 700;">${s.action_type}</span>
                      <strong style="color: #0F172A; font-size: 0.9rem;">${s.affected_capability}</strong>
                    </div>
                    <span style="font-size: 0.72rem; color: #059669; font-weight: 600;">${s.confidence_strength}</span>
                  </div>
                  <div style="font-size: 0.85rem; color: #1E293B; line-height: 1.4; margin-bottom: 0.4rem;">
                    <strong>Recommendation:</strong> ${s.suggested_improvement}
                  </div>
                  <div style="font-size: 0.75rem; color: #64748B;">
                    <strong>Observed Pattern:</strong> ${s.observed_pattern}
                  </div>
                </div>
              `).join('')}
            </div>

            <!-- Autopsy Limitations Statement -->
            <div style="margin-top: 1rem; padding: 0.65rem 0.85rem; background: #EFF6FF; border-radius: 6px; font-size: 0.75rem; color: #1E40AF; line-height: 1.35;">
              <strong>Principle:</strong> ${(autopsy.limitations || []).join(' ')}
            </div>
          </div>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `<div style="color: #EF4444; padding: 2rem; text-align: center;">Failed to generate Hiring Autopsy: ${err.message}</div>`;
    }
  },
    try {
      toast.info("Executing automated screening evaluation...");
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
    const jobId =
      (this.screeningReport && this.screeningReport.job_id) ||
      (window.appState && window.appState.activeJobId) ||
      "";
    router.navigate("interview-setup", { applicationId: this.currentAppId, jobId });
  },
};

window.candidateDetailView = candidateDetailView;
window.CandidateDetailView = candidateDetailView;
