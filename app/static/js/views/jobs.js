// ==========================================================================
// Jobs & AI JD Structuring View
// ==========================================================================

const jobsView = {
  currentJob: null,
  capabilities: [],
  suggestedCapabilities: [],

  async renderList() {
    const container = document.getElementById("main-view");
    if (!container) return;

    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2rem;">
        <div>
          <h1 style="font-size: 1.85rem; margin-bottom: 0.25rem;">Job Blueprints & Roles</h1>
          <p style="color: var(--text-secondary);">Define job requirements, structure AI capabilities, and review candidate applications.</p>
        </div>
        <button class="btn btn-primary" onclick="jobsView.openCreateJobModal()">
          <span>+</span> Create Job
        </button>
      </div>

      <div id="jobs-container">
        <p style="color: var(--text-muted); padding: 2rem 0;">Loading jobs...</p>
      </div>
    `;

    try {
      const jobs = await api.jobs.list();
      const jobsContainer = document.getElementById("jobs-container");

      if (!jobs || jobs.length === 0) {
        jobsContainer.innerHTML = `
          <div class="card" style="text-align: center; padding: 4rem 2rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">💼</div>
            <h3 style="margin-bottom: 0.5rem;">No jobs created yet</h3>
            <p style="margin-bottom: 1.5rem;">Create a job blueprint to define required capabilities and screen candidate claims.</p>
            <button class="btn btn-primary" onclick="jobsView.openCreateJobModal()">+ Create Job</button>
          </div>
        `;
        return;
      }

      let html = `<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 1.5rem;">`;
      for (const job of jobs) {
        const isPublished = job.status === "ACTIVE";
        html += `
          <div class="card" style="display: flex; flex-direction: column; justify-content: space-between; cursor: pointer;" onclick="router.navigate('job-detail', { id: '${job.id}' })">
            <div>
              <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1rem;">
                <h3 style="font-size: 1.2rem; color: var(--text-primary);">${job.title}</h3>
                <span class="badge ${isPublished ? "badge-success" : "badge-warning"}">
                  <span class="badge-dot"></span> ${isPublished ? "Active" : "Draft"}
                </span>
              </div>
              <p style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 1.25rem; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
                ${job.description || "No description provided."}
              </p>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--border-subtle); padding-top: 1rem; margin-top: 0.5rem;">
              <span style="font-size: 0.8rem; color: var(--text-muted);">
                Created ${new Date(job.created_at).toLocaleDateString()}
              </span>
              <span style="font-size: 0.85rem; font-weight: 600; color: var(--primary-light);">
                Open Blueprint →
              </span>
            </div>
          </div>
        `;
      }
      html += `</div>`;
      jobsContainer.innerHTML = html;
    } catch (err) {
      toast.error(`Failed to load jobs: ${err.message}`);
    }
  },

  async renderDetail(jobId) {
    const container = document.getElementById("main-view");
    if (!container) return;

    appState.activeJobId = jobId;

    container.innerHTML = `
      <div style="margin-bottom: 2rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
          <a href="javascript:void(0)" onclick="router.navigate('jobs')" style="font-size: 0.875rem; color: var(--text-muted);">← All Jobs</a>
        </div>
        <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <h1 id="job-title" style="font-size: 2rem;">Loading Job...</h1>
              <span id="job-status-badge" class="badge badge-neutral">Draft</span>
            </div>
            <p id="job-meta" style="color: var(--text-muted); font-size: 0.875rem; margin-top: 0.25rem;">ID: ${jobId}</p>
          </div>
          <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
            <button class="btn btn-secondary" onclick="candidatesView.triggerLoadResumesModal('${jobId}')">
              <span>📥</span> Load New Resumes
            </button>
            <button class="btn btn-outline" onclick="router.navigate('interview-setup', { jobId: '${jobId}' })">
              <span>🎯</span> Interview Setup
            </button>
            <button class="btn btn-outline" onclick="router.navigate('candidates', { jobId: '${jobId}' })">
              <span>👥</span> Screening Queue
            </button>
            <button id="btn-publish-job" class="btn btn-success" onclick="jobsView.publishJob('${jobId}')">
              <span>🚀</span> Publish Job
            </button>
          </div>
        </div>
      </div>

      <!-- Application Email Connection Banner -->
      <div class="card" style="margin-bottom: 2rem; background: rgba(59, 130, 246, 0.06); border-color: rgba(59, 130, 246, 0.25); display: flex; align-items: center; justify-content: space-between; gap: 1.5rem; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 1rem;">
          <div style="width: 42px; height: 42px; border-radius: var(--radius-md); background: rgba(59, 130, 246, 0.15); display: flex; align-items: center; justify-content: center; font-size: 1.4rem;">
            📬
          </div>
          <div>
            <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-primary);">
              Connected Application Email Inbox
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary);" id="job-inbox-email">
              Candidates can send their resumes directly to the connected hiring inbox.
            </div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <span class="badge badge-success"><span class="badge-dot"></span> Ingestion Active</span>
        </div>
      </div>

      <!-- Two Column Layout: JD on Left, Capabilities Blueprint on Right -->
      <div style="display: grid; grid-template-columns: 1.1fr 1fr; gap: 2rem; align-items: start;">
        <!-- Left: Job Description & AI Analysis Trigger -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>📄</span> Job Description
            </div>
            <button id="btn-analyze-jd" class="btn btn-primary btn-sm" onclick="jobsView.analyzeJD('${jobId}')">
              <span>⚡</span> Analyze with AI
            </button>
          </div>
          <div id="job-desc-content" style="white-space: pre-wrap; font-size: 0.9rem; line-height: 1.6; color: var(--text-secondary); max-height: 500px; overflow-y: auto; padding-right: 0.5rem;">
            Loading description...
          </div>
        </div>

        <!-- Right: Structured Capabilities Blueprint -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>🧩</span> Capability Blueprint
            </div>
            <button class="btn btn-secondary btn-sm" onclick="jobsView.openAddCapabilityModal('${jobId}')">
              + Add Capability
            </button>
          </div>

          <!-- Suggested Capabilities Pending Review -->
          <div id="ai-suggestions-container" style="display: none; margin-bottom: 1.5rem; background: rgba(139, 92, 246, 0.08); border: 1px solid rgba(139, 92, 246, 0.25); border-radius: var(--radius-md); padding: 1.25rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
              <div style="font-weight: 700; color: #C4B5FD; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem;">
                <span>✨</span> AI Extracted Capabilities (<span id="ai-suggestions-count">0</span>)
              </div>
              <button class="btn btn-primary btn-sm" onclick="jobsView.approveAllSuggestions('${jobId}')">
                Approve All
              </button>
            </div>
            <div id="ai-suggestions-list" style="display: flex; flex-direction: column; gap: 0.75rem;">
              <!-- Suggested pills injected here -->
            </div>
          </div>

          <!-- Approved Capabilities List -->
          <div id="approved-capabilities-container">
            <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.75rem; letter-spacing: 0.04em;">
              Approved Requirements & Weights
            </div>
            <div id="approved-capabilities-list" style="display: flex; flex-direction: column; gap: 0.75rem;">
              <p style="color: var(--text-muted); font-size: 0.875rem;">No capabilities approved yet. Click 'Analyze with AI' to extract from JD.</p>
            </div>
          </div>
        </div>
      </div>
    `;

    await this.loadJobData(jobId);
  },

  async loadJobData(jobId) {
    try {
      this.currentJob = await api.jobs.get(jobId);
      this.capabilities = await api.capabilities.list(jobId);

      // Populate Title & Meta
      const titleEl = document.getElementById("job-title");
      const metaEl = document.getElementById("job-meta");
      const statusBadge = document.getElementById("job-status-badge");
      const descEl = document.getElementById("job-desc-content");
      const publishBtn = document.getElementById("btn-publish-job");

      if (titleEl) titleEl.textContent = this.currentJob.title;
      if (metaEl) metaEl.textContent = `Created ${new Date(this.currentJob.created_at).toLocaleString()}`;
      if (descEl) descEl.textContent = this.currentJob.description || "No description available.";

      const isPublished = this.currentJob.status === "ACTIVE";
      if (statusBadge) {
        statusBadge.className = `badge ${isPublished ? "badge-success" : "badge-warning"}`;
        statusBadge.innerHTML = `<span class="badge-dot"></span> ${isPublished ? "Active" : "Draft"}`;
      }

      if (publishBtn) {
        if (isPublished) {
          publishBtn.style.display = "none";
        } else {
          publishBtn.style.display = "inline-flex";
        }
      }

      // Check email connection
      try {
        const conns = await api.email.listConnections();
        const inboxEl = document.getElementById("job-inbox-email");
        if (inboxEl && conns && conns.length > 0) {
          inboxEl.innerHTML = `Application intake email: <strong style="color: var(--primary-light);">${conns[0].account_email}</strong> (Provider: ${conns[0].provider})`;
        }
      } catch (e) {
        console.log("Could not load connection:", e);
      }

      this.renderApprovedCapabilities();
    } catch (err) {
      toast.error(`Failed to load job details: ${err.message}`);
    }
  },

  renderApprovedCapabilities() {
    const listEl = document.getElementById("approved-capabilities-list");
    if (!listEl) return;

    if (!this.capabilities || this.capabilities.length === 0) {
      listEl.innerHTML = `
        <div style="background: var(--bg-surface-elevated); padding: 1.5rem; border-radius: var(--radius-md); text-align: center;">
          <p style="color: var(--text-muted); font-size: 0.875rem; margin-bottom: 0.75rem;">No capabilities approved for this job yet.</p>
          <p style="color: var(--text-secondary); font-size: 0.8rem;">Click <strong>Analyze with AI</strong> on the left to extract capabilities automatically.</p>
        </div>
      `;
      return;
    }

    let html = "";
    for (const cap of this.capabilities) {
      const impColor =
        cap.importance === "CRITICAL"
          ? "badge-danger"
          : cap.importance === "HIGH"
          ? "badge-warning"
          : "badge-info";

      html += `
        <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 0.9rem 1rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
              <span style="font-weight: 700; color: var(--text-primary); font-size: 0.95rem;">${cap.name}</span>
              <span class="badge ${impColor}">${cap.importance}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-secondary);">${cap.description || ""}</div>
          </div>
          <button class="btn btn-outline btn-sm" style="color: #F87171; border-color: rgba(239, 68, 68, 0.3);" onclick="jobsView.deleteCapability('${cap.id}')">
            Remove
          </button>
        </div>
      `;
    }

    listEl.innerHTML = html;
  },

  async analyzeJD(jobId) {
    const btn = document.getElementById("btn-analyze-jd");
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span>⏳</span> Analyzing JD...`;
    }

    try {
      const res = await api.jobs.analyzeJD(jobId);
      this.suggestedCapabilities = res.suggested_capabilities || [];

      toast.success(`Extracted ${this.suggestedCapabilities.length} capabilities from Job Description!`);

      const container = document.getElementById("ai-suggestions-container");
      const listEl = document.getElementById("ai-suggestions-list");
      const countEl = document.getElementById("ai-suggestions-count");

      if (container && listEl && countEl) {
        countEl.textContent = this.suggestedCapabilities.length;
        container.style.display = "block";

        let html = "";
        this.suggestedCapabilities.forEach((sug, idx) => {
          const impColor =
            sug.importance === "CRITICAL"
              ? "badge-danger"
              : sug.importance === "HIGH"
              ? "badge-warning"
              : "badge-info";

          html += `
            <div id="sug-${idx}" style="background: var(--bg-surface); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: var(--radius-sm); padding: 0.75rem 1rem; display: flex; align-items: center; justify-content: space-between; gap: 0.75rem;">
              <div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                  <strong style="color: var(--text-primary);">${sug.name}</strong>
                  <span class="badge ${impColor}">${sug.importance}</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.2rem;">${sug.description}</div>
              </div>
              <div style="display: flex; gap: 0.5rem;">
                <button class="btn btn-success btn-sm" onclick="jobsView.approveSingleSuggestion('${jobId}', ${idx})">
                  Approve
                </button>
                <button class="btn btn-outline btn-sm" onclick="jobsView.dismissSuggestion(${idx})">
                  ✕
                </button>
              </div>
            </div>
          `;
        });
        listEl.innerHTML = html;
      }
    } catch (err) {
      toast.error(`JD Analysis failed: ${err.message}`);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<span>⚡</span> Analyze with AI`;
      }
    }
  },

  async approveSingleSuggestion(jobId, index) {
    const sug = this.suggestedCapabilities[index];
    if (!sug) return;

    try {
      await api.capabilities.create(jobId, {
        name: sug.name,
        description: sug.description,
        importance: sug.importance,
      });

      toast.success(`Approved capability: ${sug.name}`);
      const el = document.getElementById(`sug-${index}`);
      if (el) el.remove();

      this.capabilities = await api.capabilities.list(jobId);
      this.renderApprovedCapabilities();
    } catch (err) {
      toast.error(`Failed to approve: ${err.message}`);
    }
  },

  dismissSuggestion(index) {
    const el = document.getElementById(`sug-${index}`);
    if (el) el.remove();
  },

  async approveAllSuggestions(jobId) {
    if (!this.suggestedCapabilities || this.suggestedCapabilities.length === 0) return;

    try {
      const payload = this.suggestedCapabilities.map((s) => ({
        name: s.name,
        description: s.description,
        importance: s.importance,
      }));

      await api.capabilities.batchCreate(jobId, payload);
      toast.success(`Approved all ${payload.length} capabilities!`);

      const container = document.getElementById("ai-suggestions-container");
      if (container) container.style.display = "none";

      this.capabilities = await api.capabilities.list(jobId);
      this.renderApprovedCapabilities();
    } catch (err) {
      toast.error(`Failed to batch approve: ${err.message}`);
    }
  },

  async deleteCapability(capId) {
    if (!confirm("Are you sure you want to remove this capability requirement?")) return;
    try {
      await api.capabilities.delete(capId);
      toast.info("Capability removed.");
      if (appState.activeJobId) {
        this.capabilities = await api.capabilities.list(appState.activeJobId);
        this.renderApprovedCapabilities();
      }
    } catch (err) {
      toast.error(`Failed to delete: ${err.message}`);
    }
  },

  async publishJob(jobId) {
    try {
      await api.jobs.publish(jobId);
      toast.success("Job blueprint published! Position is now actively accepting candidate resumes.");
      await this.loadJobData(jobId);
    } catch (err) {
      toast.error(`Failed to publish: ${err.message}`);
    }
  },

  openCreateJobModal() {
    modal.open(`
      <div class="modal-header">
        <h3 class="modal-title">Create New Job Blueprint</h3>
        <button class="btn btn-outline btn-sm" onclick="modal.close()">✕</button>
      </div>
      <form onsubmit="jobsView.handleCreateJobSubmit(event)">
        <div class="form-group">
          <label class="form-label" for="job-input-title">Job Title</label>
          <input class="form-input" id="job-input-title" placeholder="e.g. Senior Backend Engineer" required />
        </div>
        <div class="form-group">
          <label class="form-label" for="job-input-desc">Job Description</label>
          <textarea class="form-textarea" id="job-input-desc" placeholder="Paste full job description requirements here..." rows="8" required></textarea>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline" onclick="modal.close()">Cancel</button>
          <button type="submit" class="btn btn-primary" id="btn-create-job-submit">Create & Open Blueprint</button>
        </div>
      </form>
    `);
  },

  async handleCreateJobSubmit(event) {
    event.preventDefault();
    const btn = document.getElementById("btn-create-job-submit");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Creating...";
    }

    const title = document.getElementById("job-input-title").value.trim();
    const description = document.getElementById("job-input-desc").value.trim();

    try {
      const job = await api.jobs.create(title, description);
      modal.close();
      toast.success(`Job '${job.title}' created successfully.`);
      router.navigate("job-detail", { id: job.id });
    } catch (err) {
      toast.error(`Creation failed: ${err.message}`);
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Create & Open Blueprint";
      }
    }
  },

  openAddCapabilityModal(jobId) {
    modal.open(`
      <div class="modal-header">
        <h3 class="modal-title">Add Capability Requirement</h3>
        <button class="btn btn-outline btn-sm" onclick="modal.close()">✕</button>
      </div>
      <form onsubmit="jobsView.handleAddCapabilitySubmit(event, '${jobId}')">
        <div class="form-group">
          <label class="form-label" for="cap-input-name">Capability Name</label>
          <input class="form-input" id="cap-input-name" placeholder="e.g. FastAPI Microservices" required />
        </div>
        <div class="form-group">
          <label class="form-label" for="cap-input-importance">Importance</label>
          <select class="form-select" id="cap-input-importance">
            <option value="CRITICAL">CRITICAL</option>
            <option value="HIGH" selected>HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label" for="cap-input-desc">Description / Criteria</label>
          <textarea class="form-textarea" id="cap-input-desc" placeholder="Details of capability expected..." rows="3"></textarea>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline" onclick="modal.close()">Cancel</button>
          <button type="submit" class="btn btn-primary">Save Capability</button>
        </div>
      </form>
    `);
  },

  async handleAddCapabilitySubmit(event, jobId) {
    event.preventDefault();
    const name = document.getElementById("cap-input-name").value.trim();
    const importance = document.getElementById("cap-input-importance").value;
    const description = document.getElementById("cap-input-desc").value.trim();

    try {
      await api.capabilities.create(jobId, { name, importance, description });
      modal.close();
      toast.success(`Added capability requirement: ${name}`);
      this.capabilities = await api.capabilities.list(jobId);
      this.renderApprovedCapabilities();
    } catch (err) {
      toast.error(`Failed to add capability: ${err.message}`);
    }
  },
};
