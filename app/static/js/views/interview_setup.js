// Gap2Hire - Interview Setup View (Rounds, HR Questions, AI Question Suggestions)
window.InterviewSetupView = {
    async render(container, params = {}) {
        const jobId = params.jobId || window.AppState.activeJobId;
        const applicationId = params.applicationId || window.AppState.activeApplicationId;

        if (!jobId && !applicationId) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No Job or Candidate Selected</h3>
                    <p>Please select a shortlisted candidate or a job to configure interviews.</p>
                    <a href="#candidates" class="btn btn-primary">Go to Candidate Screening</a>
                </div>
            `;
            return;
        }

        container.innerHTML = `<div class="loading-spinner">Loading interview configuration...</div>`;

        try {
            let app = null;
            let currentJobId = jobId;

            if (applicationId) {
                app = await window.ApiClient.getApplicationDetail(applicationId);
                currentJobId = app.job_id || jobId;
                window.AppState.activeJobId = currentJobId;
            }

            const job = await window.ApiClient.getJob(currentJobId);
            const rounds = await window.ApiClient.getInterviewRounds(currentJobId).catch(() => []);
            const capabilities = await window.ApiClient.getJobCapabilities(currentJobId).catch(() => []);

            const approvedCaps = capabilities.filter(c => c.review_status === 'APPROVED');

            container.innerHTML = `
                <div class="interview-setup-header" style="margin-bottom: 24px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span class="badge badge-info" style="margin-bottom: 8px;">INTERVIEW CONFIGURATION</span>
                            <h2>${job.title}</h2>
                            <p style="color: var(--text-muted); font-size: 0.9rem;">
                                Configure interview rounds, curated HR question datasets, and AI-suggested questions for approved capabilities.
                            </p>
                            ${app ? `
                                <div style="margin-top: 8px; padding: 8px 12px; background: rgba(59, 130, 246, 0.1); border-left: 3px solid var(--primary); border-radius: 4px; font-size: 0.88rem;">
                                    <strong>Candidate Target:</strong> ${app.candidate_name || 'Candidate'} (${app.candidate_email}) &nbsp;|&nbsp;
                                    <strong>Status:</strong> <span class="badge ${app.shortlist_status === 'SHORTLISTED' ? 'badge-success' : 'badge-warning'}">${app.shortlist_status || 'PENDING'}</span>
                                </div>
                            ` : ''}
                        </div>
                        <div style="display: flex; gap: 12px;">
                            ${app && app.shortlist_status === 'SHORTLISTED' ? `
                                <button id="btn-start-candidate-interview" class="btn btn-success" style="box-shadow: 0 0 15px rgba(16, 185, 129, 0.4);">
                                    🚀 Start AI Interview
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>

                <div class="grid-2-col" style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
                    <!-- LEFT COLUMN: Rounds & HR Question Datasets -->
                    <div>
                        <div class="card" style="margin-bottom: 24px;">
                            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin-bottom: 16px;">
                                <div>
                                    <h3 style="font-size: 1.1rem; margin: 0;">1. Interview Rounds</h3>
                                    <span style="font-size: 0.8rem; color: var(--text-muted);">Configured multi-round pipeline</span>
                                </div>
                                <button id="btn-add-round-modal" class="btn btn-secondary btn-sm">+ Add Round</button>
                            </div>

                            <div id="rounds-list-container">
                                ${rounds.length === 0 ? `
                                    <div style="text-align: center; padding: 20px; color: var(--text-muted); font-size: 0.88rem;">
                                        No custom rounds defined yet. Default: Round 1 (Technical Screening).
                                    </div>
                                ` : `
                                    <div class="rounds-list" style="display: flex; flex-direction: column; gap: 12px;">
                                        ${rounds.map((r, idx) => `
                                            <div style="padding: 12px 16px; border-radius: 8px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                                                <div>
                                                    <span style="font-weight: 600; color: var(--primary);">Round ${r.round_number || (idx + 1)}: ${r.round_name || r.name || 'Technical'}</span>
                                                    <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">
                                                        ${r.description || 'General capability and problem solving verification.'}
                                                    </div>
                                                </div>
                                                <span class="badge badge-info">${r.intent || 'TECHNICAL'}</span>
                                            </div>
                                        `).join('')}
                                    </div>
                                `}
                            </div>
                        </div>

                        <!-- HR Question Dataset -->
                        <div class="card">
                            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin-bottom: 16px;">
                                <div>
                                    <h3 style="font-size: 1.1rem; margin: 0;">2. HR Question Dataset</h3>
                                    <span style="font-size: 0.8rem; color: var(--text-muted);">Curated questions added by HR / Hiring Team</span>
                                </div>
                                <button id="btn-add-hr-question" class="btn btn-secondary btn-sm">+ Add Question</button>
                            </div>

                            <div id="hr-questions-container" style="display: flex; flex-direction: column; gap: 12px;">
                                <div style="padding: 12px; border-radius: 8px; background: rgba(59, 130, 246, 0.05); border: 1px dashed var(--primary);">
                                    <div style="font-weight: 500; font-size: 0.9rem; color: var(--text-primary); margin-bottom: 4px;">
                                        "Explain how you would design a FastAPI backend with PostgreSQL for a high-traffic system."
                                    </div>
                                    <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: var(--text-muted);">
                                        <span>Target: <strong>System Design</strong></span>
                                        <span class="badge badge-info">SYSTEM_DESIGN</span>
                                    </div>
                                </div>
                                <div style="padding: 12px; border-radius: 8px; background: rgba(59, 130, 246, 0.05); border: 1px dashed var(--primary);">
                                    <div style="font-weight: 500; font-size: 0.9rem; color: var(--text-primary); margin-bottom: 4px;">
                                        "Describe a production debugging scenario where you diagnosed a database connection leak."
                                    </div>
                                    <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: var(--text-muted);">
                                        <span>Target: <strong>Debugging & PostgreSQL</strong></span>
                                        <span class="badge badge-info">TECHNICAL</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- RIGHT COLUMN: AI Suggested Questions for Approved Capabilities -->
                    <div>
                        <div class="card" style="height: 100%;">
                            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin-bottom: 16px;">
                                <div>
                                    <h3 style="font-size: 1.1rem; margin: 0;">3. AI Suggested Questions</h3>
                                    <span style="font-size: 0.8rem; color: var(--text-muted);">Generated to explore capability blueprints & gaps</span>
                                </div>
                                <button id="btn-generate-ai-questions" class="btn btn-primary btn-sm">
                                    ✨ Generate AI Questions
                                </button>
                            </div>

                            <div id="ai-questions-list" style="display: flex; flex-direction: column; gap: 12px;">
                                ${approvedCaps.length === 0 ? `
                                    <div style="text-align: center; padding: 30px; color: var(--text-muted);">
                                        <p>No approved capabilities found for this job yet.</p>
                                        <a href="#job-detail?id=${currentJobId}" class="btn btn-secondary btn-sm" style="margin-top: 8px;">
                                            Approve Capabilities First
                                        </a>
                                    </div>
                                ` : `
                                    <div style="padding: 12px; border-radius: 8px; background: rgba(255,255,255,0.02); border: 1px solid var(--border-color);">
                                        <p style="font-size: 0.85rem; color: var(--text-muted); margin: 0 0 8px 0;">
                                            AI questions will target <strong>${approvedCaps.length} approved capabilities</strong> (${approvedCaps.slice(0, 3).map(c => c.name).join(', ')}${approvedCaps.length > 3 ? '...' : ''}).
                                        </p>
                                        <p style="font-size: 0.82rem; color: var(--text-secondary); margin: 0;">
                                            Click <strong>"Generate AI Questions"</strong> to structure questions for probe depth, live evaluation, and gap detection.
                                        </p>
                                    </div>
                                `}
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Wire event handlers
            this.attachEventListeners(container, currentJobId, applicationId, approvedCaps);

        } catch (err) {
            console.error(err);
            container.innerHTML = `
                <div class="empty-state">
                    <h3>Error loading interview setup</h3>
                    <p>${err.message}</p>
                    <a href="#candidates" class="btn btn-secondary">Back to Candidates</a>
                </div>
            `;
        }
    },

    attachEventListeners(container, jobId, applicationId, approvedCaps) {
        // Generate AI Questions button
        const btnGenAi = container.querySelector('#btn-generate-ai-questions');
        if (btnGenAi) {
            btnGenAi.addEventListener('click', async () => {
                const listContainer = container.querySelector('#ai-questions-list');
                listContainer.innerHTML = `
                    <div style="text-align: center; padding: 20px;">
                        <div class="loading-spinner" style="margin: 0 auto 10px;"></div>
                        <span style="font-size: 0.85rem; color: var(--text-muted);">Generating targeted questions for ${approvedCaps.length} capabilities...</span>
                    </div>
                `;

                try {
                    const result = await window.ApiClient.generateAIQuestions(jobId);
                    const questions = result.questions || result.suggested_questions || [];

                    if (questions.length === 0) {
                        listContainer.innerHTML = `<div style="text-align: center; padding: 20px; color: var(--text-muted);">No suggestions generated. Ensure capabilities are approved.</div>`;
                        return;
                    }

                    listContainer.innerHTML = questions.map((q, idx) => `
                        <div class="card" style="padding: 14px; margin-bottom: 0; background: rgba(255,255,255,0.03); border-left: 3px solid #8b5cf6;">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                                <div style="font-weight: 500; font-size: 0.88rem; color: var(--text-primary);">
                                    ${q.question || q.text || q}
                                </div>
                                <span class="badge badge-primary" style="font-size: 0.72rem; white-space: nowrap;">AI SUGGESTED</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; font-size: 0.78rem; color: var(--text-muted);">
                                <span>Capability: <strong style="color: var(--text-secondary);">${q.capability_name || q.capability || 'Core Tech'}</strong></span>
                                <span class="badge badge-info">${q.intent || 'TECHNICAL'}</span>
                            </div>
                        </div>
                    `).join('');

                    window.AppState.toast('AI questions generated successfully!', 'success');
                } catch (err) {
                    listContainer.innerHTML = `<div style="color: var(--danger); padding: 12px; font-size: 0.85rem;">Failed to generate AI questions: ${err.message}</div>`;
                    window.AppState.toast(err.message, 'error');
                }
            });
        }

        // Add HR Question button
        const btnAddHrQ = container.querySelector('#btn-add-hr-question');
        if (btnAddHrQ) {
            btnAddHrQ.addEventListener('click', () => {
                window.AppState.modal(`
                    <h3>Add HR Question</h3>
                    <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px;">
                        Add a custom verified question to the interview question dataset.
                    </p>
                    <div class="form-group" style="margin-bottom: 14px;">
                        <label>Question Prompt</label>
                        <textarea id="modal-hr-q-text" class="form-control" rows="3" placeholder="e.g. Explain how you would implement redis caching to prevent database overload."></textarea>
                    </div>
                    <div class="form-group" style="margin-bottom: 14px;">
                        <label>Target Capability</label>
                        <select id="modal-hr-q-cap" class="form-control">
                            ${approvedCaps.length > 0 ? approvedCaps.map(c => `<option value="${c.name}">${c.name} (${c.importance || 'IMPORTANT'})</option>`).join('') : '<option value="General">General Technical</option>'}
                        </select>
                    </div>
                    <div class="form-group" style="margin-bottom: 20px;">
                        <label>Intent / Round Type</label>
                        <select id="modal-hr-q-intent" class="form-control">
                            <option value="TECHNICAL">TECHNICAL</option>
                            <option value="SYSTEM_DESIGN">SYSTEM_DESIGN</option>
                            <option value="PROBLEM_SOLVING">PROBLEM_SOLVING</option>
                            <option value="BEHAVIORAL">BEHAVIORAL</option>
                        </select>
                    </div>
                    <div style="display: flex; justify-content: flex-end; gap: 12px;">
                        <button class="btn btn-secondary" onclick="window.AppState.closeModal()">Cancel</button>
                        <button id="btn-save-hr-q" class="btn btn-primary">Add Question</button>
                    </div>
                `);

                document.getElementById('btn-save-hr-q').addEventListener('click', () => {
                    const text = document.getElementById('modal-hr-q-text').value.trim();
                    const cap = document.getElementById('modal-hr-q-cap').value;
                    const intent = document.getElementById('modal-hr-q-intent').value;

                    if (!text) {
                        alert('Please enter a question');
                        return;
                    }

                    const hrContainer = container.querySelector('#hr-questions-container');
                    const qCard = document.createElement('div');
                    qCard.style.cssText = 'padding: 12px; border-radius: 8px; background: rgba(59, 130, 246, 0.05); border: 1px dashed var(--primary);';
                    qCard.innerHTML = `
                        <div style="font-weight: 500; font-size: 0.9rem; color: var(--text-primary); margin-bottom: 4px;">
                            "${text}"
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: var(--text-muted);">
                            <span>Target: <strong>${cap}</strong></span>
                            <span class="badge badge-info">${intent}</span>
                        </div>
                    `;
                    hrContainer.appendChild(qCard);
                    window.AppState.closeModal();
                    window.AppState.toast('HR Question added to dataset', 'success');
                });
            });
        }

        // Add Round Modal
        const btnAddRound = container.querySelector('#btn-add-round-modal');
        if (btnAddRound) {
            btnAddRound.addEventListener('click', () => {
                window.AppState.modal(`
                    <h3>Configure Interview Round</h3>
                    <div class="form-group" style="margin-bottom: 14px;">
                        <label>Round Name</label>
                        <input type="text" id="modal-round-name" class="form-control" placeholder="e.g. System Architecture & Scalability">
                    </div>
                    <div class="form-group" style="margin-bottom: 14px;">
                        <label>Round Intent</label>
                        <select id="modal-round-intent" class="form-control">
                            <option value="TECHNICAL">TECHNICAL</option>
                            <option value="SYSTEM_DESIGN">SYSTEM_DESIGN</option>
                            <option value="PROBLEM_SOLVING">PROBLEM_SOLVING</option>
                        </select>
                    </div>
                    <div class="form-group" style="margin-bottom: 20px;">
                        <label>Description / Focus</label>
                        <input type="text" id="modal-round-desc" class="form-control" placeholder="Evaluate distributed systems, caching, and data modeling.">
                    </div>
                    <div style="display: flex; justify-content: flex-end; gap: 12px;">
                        <button class="btn btn-secondary" onclick="window.AppState.closeModal()">Cancel</button>
                        <button id="btn-save-round" class="btn btn-primary">Save Round</button>
                    </div>
                `);

                document.getElementById('btn-save-round').addEventListener('click', async () => {
                    const name = document.getElementById('modal-round-name').value.trim();
                    const intent = document.getElementById('modal-round-intent').value;
                    const desc = document.getElementById('modal-round-desc').value.trim();

                    if (!name) {
                        alert('Please enter a round name');
                        return;
                    }

                    try {
                        await window.ApiClient.createInterviewRound(jobId, {
                            round_name: name,
                            intent: intent,
                            description: desc,
                            round_number: 2
                        });
                        window.AppState.closeModal();
                        window.AppState.toast('Interview round configured!', 'success');
                        this.render(container, { jobId, applicationId });
                    } catch (err) {
                        alert('Error saving round: ' + err.message);
                    }
                });
            });
        }

        // Start Candidate Interview button
        const btnStart = container.querySelector('#btn-start-candidate-interview');
        if (btnStart) {
            btnStart.addEventListener('click', async () => {
                if (!confirm('Start the AI Interview session for this candidate now?')) return;

                btnStart.disabled = true;
                btnStart.innerText = 'Initializing LangGraph Engine...';

                try {
                    const session = await window.ApiClient.startInterviewSession(applicationId);
                    window.AppState.activeSessionId = session.id || session.session_id;
                    window.AppState.toast('Interview session initialized!', 'success');
                    window.location.hash = `#interview-live?sessionId=${window.AppState.activeSessionId}&applicationId=${applicationId}`;
                } catch (err) {
                    btnStart.disabled = false;
                    btnStart.innerText = '🚀 Start AI Interview';
                    window.AppState.toast('Failed to start interview: ' + err.message, 'error');
                }
            });
        }
    }
};

window.interviewSetupView = window.InterviewSetupView;
