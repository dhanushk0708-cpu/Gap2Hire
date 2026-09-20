// ==========================================================================
// HR Main Dashboard View
// ==========================================================================

const dashboardView = {
  async render() {
    const container = document.getElementById("main-view");
    if (!container) return;

    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2rem;">
        <div>
          <h1 style="font-size: 1.85rem; margin-bottom: 0.25rem;">Hiring Intelligence Hub</h1>
          <p style="color: var(--text-secondary);">Overview of active hiring blueprints, candidate evidence, and interview pipelines.</p>
        </div>
        <div style="display: flex; gap: 0.75rem;">
          <button class="btn btn-secondary" onclick="candidatesView.triggerLoadResumesModal()">
            <span>📥</span> Load New Resumes
          </button>
          <button class="btn btn-primary" onclick="jobsView.openCreateJobModal()">
            <span>+</span> Create Job
          </button>
        </div>
      </div>

      <!-- Pipeline Funnel Metrics -->
      <div class="pipeline-bar" id="pipeline-funnel">
        <div class="pipeline-step">
          <div class="pipeline-step-header">1. Applications</div>
          <div class="pipeline-step-count" id="count-applications">-</div>
        </div>
        <div class="pipeline-step">
          <div class="pipeline-step-header">2. Screening Queue</div>
          <div class="pipeline-step-count" id="count-screening">-</div>
        </div>
        <div class="pipeline-step">
          <div class="pipeline-step-header">3. Shortlisted</div>
          <div class="pipeline-step-count" id="count-shortlisted">-</div>
        </div>
        <div class="pipeline-step">
          <div class="pipeline-step-header">4. AI Interviews</div>
          <div class="pipeline-step-count" id="count-interviews">-</div>
        </div>
        <div class="pipeline-step">
          <div class="pipeline-step-header">5. Completed / Decision</div>
          <div class="pipeline-step-count" id="count-completed">-</div>
        </div>
      </div>

      <!-- Active Jobs & Candidates Grid -->
      <div style="display: grid; grid-template-columns: 1fr; gap: 2rem;">
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>💼</span> Active Job Positions
            </div>
            <button class="btn btn-outline btn-sm" onclick="router.navigate('jobs')">View All Jobs</button>
          </div>
          <div id="dashboard-jobs-list">
            <p style="color: var(--text-muted); padding: 1rem 0;">Loading active jobs...</p>
          </div>
        </div>
      </div>
    `;

    await this.loadData();
  },

  async loadData() {
    try {
      const jobs = await api.jobs.list();
      const jobsListEl = document.getElementById("dashboard-jobs-list");

      let totalApps = 0;
      let totalScreening = 0;
      let totalShortlisted = 0;
      let totalInterviews = 0;
      let totalCompleted = 0;

      if (!jobs || jobs.length === 0) {
        if (jobsListEl) {
          jobsListEl.innerHTML = `
            <div style="text-align: center; padding: 3rem 1rem;">
              <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">📋</div>
              <h3 style="margin-bottom: 0.5rem;">No jobs created yet</h3>
              <p style="margin-bottom: 1.5rem;">Create your first job blueprint to begin analyzing candidate evidence.</p>
              <button class="btn btn-primary" onclick="jobsView.openCreateJobModal()">+ Create Job</button>
            </div>
          `;
        }
      } else {
        // Render jobs
        let html = `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Job Title</th>
                  <th>Status</th>
                  <th>Candidates</th>
                  <th>Created</th>
                  <th style="text-align: right;">Action</th>
                </tr>
              </thead>
              <tbody>
        `;

        for (const job of jobs) {
          // Fetch candidates for counts
          let candidates = [];
          try {
            candidates = await api.screening.listJobCandidates(job.id);
          } catch (e) {
            candidates = [];
          }

          totalApps += candidates.length;
          totalScreening += candidates.filter((c) => c.status === "SCREENING" || c.status === "APPLIED").length;
          totalShortlisted += candidates.filter((c) => c.shortlist_status === "SHORTLISTED").length;
          totalInterviews += candidates.filter((c) => c.status === "INTERVIEW").length;
          totalCompleted += candidates.filter((c) => c.status === "INTERVIEW_COMPLETED" || c.status === "ADVANCED" || c.status === "OFFERED" || c.status === "REJECTED").length;

          const statusBadge =
            job.status === "PUBLISHED"
              ? `<span class="badge badge-success"><span class="badge-dot"></span> Active</span>`
              : `<span class="badge badge-warning"><span class="badge-dot"></span> Draft</span>`;

          html += `
            <tr>
              <td>
                <div style="font-weight: 700; color: var(--text-primary); cursor: pointer;" onclick="router.navigate('job-detail', { id: '${job.id}' })">
                  ${job.title}
                </div>
              </td>
              <td>${statusBadge}</td>
              <td>
                <span style="font-weight: 600;">${candidates.length}</span> candidates
              </td>
              <td style="color: var(--text-muted); font-size: 0.85rem;">
                ${new Date(job.created_at).toLocaleDateString()}
              </td>
              <td style="text-align: right;">
                <button class="btn btn-secondary btn-sm" onclick="router.navigate('job-detail', { id: '${job.id}' })">
                  Open Blueprint →
                </button>
              </td>
            </tr>
          `;
        }

        html += `</tbody></table></div>`;
        if (jobsListEl) jobsListEl.innerHTML = html;
      }

      // Update counters
      const appEl = document.getElementById("count-applications");
      const scrEl = document.getElementById("count-screening");
      const shortEl = document.getElementById("count-shortlisted");
      const intEl = document.getElementById("count-interviews");
      const compEl = document.getElementById("count-completed");

      if (appEl) appEl.textContent = totalApps;
      if (scrEl) scrEl.textContent = totalScreening;
      if (shortEl) shortEl.textContent = totalShortlisted;
      if (intEl) intEl.textContent = totalInterviews;
      if (compEl) compEl.textContent = totalCompleted;
    } catch (err) {
      toast.error(`Failed to load dashboard data: ${err.message}`);
    }
  },
};
