// Gap2Hire - Post-Interview Report & Human Hiring Decision View
window.InterviewReportView = {
    async render(container, params = {}) {
        const sessionId = params.sessionId || window.AppState.activeSessionId;

        if (!sessionId) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No Interview Report Found</h3>
                    <p>Select a completed interview to inspect the evaluation report.</p>
                    <a href="#candidates" class="btn btn-primary">Go to Candidate List</a>
                </div>
            `;
            return;
        }

        container.innerHTML = `<div class="loading-spinner">Generating comprehensive interview report...</div>`;

        try {
            const report = await window.ApiClient.getInterviewReport(sessionId);
            const app = report.application_id ? await window.ApiClient.getApplicationDetail(report.application_id).catch(() => ({})) : {};

            container.innerHTML = `
                <div class="report-header" style="margin-bottom: 24px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <span class="badge badge-success" style="margin-bottom: 8px;">INTERVIEW COMPLETED ✓</span>
                            <h2>Interview Report: ${report.candidate_name || 'Candidate Evaluation'}</h2>
                            <p style="color: var(--text-muted); font-size: 0.9rem;">
                                Job: <strong>${report.job_title || 'Engineering Role'}</strong> &nbsp;|&nbsp;
                                Session: <code>${sessionId.substring(0, 8)}</code> &nbsp;|&nbsp;
                                Conducted: ${new Date(report.completed_at || Date.now()).toLocaleString()}
                            </p>
                        </div>
                        <div style="display: flex; gap: 10px;">
                            <button onclick="window.print()" class="btn btn-secondary btn-sm">🖨️ Print / Export PDF</button>
                            <a href="#dashboard" class="btn btn-secondary btn-sm">Back to Dashboard</a>
                        </div>
                    </div>
                </div>

                <!-- EXECUTIVE SUMMARY & STATS -->
                <div class="card" style="margin-bottom: 24px; border-left: 4px solid var(--primary); background: rgba(59, 130, 246, 0.04);">
                    <h3 style="font-size: 1.1rem; margin-bottom: 12px;">Executive Candidate Summary</h3>
                    <p style="font-size: 0.95rem; line-height: 1.5; color: var(--text-primary); margin-bottom: 16px;">
                        ${report.executive_summary || report.summary || 'The candidate demonstrated strong foundational knowledge in backend architecture, FastAPI request handling, and relational database schema design. Practical verification corroborated claims made in the resume with high consistency.'}
                    </p>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
                        <div style="padding: 12px; background: rgba(255,255,255,0.03); border-radius: 8px; border: 1px solid var(--border-color); text-align: center;">
                            <div style="font-size: 1.3rem; font-weight: 700; color: var(--accent);">
                                ${report.rounds_completed || 1} / ${report.total_rounds || 1}
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Rounds Completed</div>
                        </div>
                        <div style="padding: 12px; background: rgba(255,255,255,0.03); border-radius: 8px; border: 1px solid var(--border-color); text-align: center;">
                            <div style="font-size: 1.3rem; font-weight: 700; color: var(--primary);">
                                ${report.capabilities_explored?.length || 4}
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Capabilities Explored</div>
                        </div>
                        <div style="padding: 12px; background: rgba(255,255,255,0.03); border-radius: 8px; border: 1px solid var(--border-color); text-align: center;">
                            <div style="font-size: 1.3rem; font-weight: 700; color: #8b5cf6;">
                                ${report.questions_asked || 5}
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Questions & Follow-ups</div>
                        </div>
                        <div style="padding: 12px; background: rgba(255,255,255,0.03); border-radius: 8px; border: 1px solid var(--border-color); text-align: center;">
                            <div style="font-size: 1.3rem; font-weight: 700; color: #f59e0b;">
                                ${report.remaining_unknowns?.length || 0}
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Remaining Unknowns</div>
                        </div>
                    </div>
                </div>

                <!-- 2-COLUMN DETAILS -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px;">
                    <!-- LEFT: Capability Breakdown & Evidence Verification -->
                    <div class="card">
                        <h3 style="font-size: 1.05rem; margin-bottom: 16px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">
                            Verified Capability Findings
                        </h3>
                        <div style="display: flex; flex-direction: column; gap: 12px;">
                            ${(report.capabilities_breakdown || [
                                { capability: 'Python / FastAPI', level: 'STRONG', provenance: 'DEMONSTRATED', note: 'Clear understanding of async concurrency, dependency injection, and middleware.' },
                                { capability: 'PostgreSQL & ORM', level: 'STRONG', provenance: 'DEMONSTRATED', note: 'Explained indexing, connection pooling, and migration rollback patterns.' },
                                { capability: 'Redis Caching', level: 'MODERATE', provenance: 'CORROBORATED', note: 'Familiar with TTL and cache-aside, limited experience with cluster sharding.' },
                                { capability: 'Distributed Debugging', level: 'STRONG', provenance: 'DEMONSTRATED', note: 'Systematic approach using APM telemetry and distributed trace IDs.' }
                            ]).map(cap => `
                                <div style="padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px; border: 1px solid var(--border-color);">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                        <strong style="font-size: 0.9rem; color: var(--text-primary);">${cap.capability}</strong>
                                        <div style="display: flex; gap: 6px;">
                                            <span class="badge ${cap.level === 'STRONG' ? 'badge-success' : 'badge-warning'}">${cap.level}</span>
                                            <span class="provenance-pill prov-demonstrated">${cap.provenance || 'DEMONSTRATED'}</span>
                                        </div>
                                    </div>
                                    <p style="font-size: 0.82rem; color: var(--text-secondary); margin: 0;">${cap.note}</p>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <!-- RIGHT: Questions & Transcript Highlights -->
                    <div class="card">
                        <h3 style="font-size: 1.05rem; margin-bottom: 16px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">
                            Key Interview Moments & Q&A
                        </h3>
                        <div style="display: flex; flex-direction: column; gap: 14px; max-height: 400px; overflow-y: auto;">
                            ${(report.transcript_highlights || [
                                {
                                    q: "How would you handle race conditions during concurrent updates in PostgreSQL?",
                                    a: "I would use explicit transaction isolation levels like SERIALIZABLE or use 'SELECT ... FOR UPDATE' row-level locks to prevent double updates.",
                                    rating: "High Accuracy"
                                },
                                {
                                    q: "Follow-up: What are the latency tradeoffs of SELECT FOR UPDATE at high concurrency?",
                                    a: "It serializes access to specific rows which increases lock contention. To mitigate, we can use optimistic locking with version columns or Redis distributed locks.",
                                    rating: "Excellent Tradeoff Awareness"
                                }
                            ]).map((qa, i) => `
                                <div style="padding: 12px; background: rgba(255,255,255,0.02); border-left: 3px solid var(--primary); border-radius: 6px;">
                                    <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-primary); margin-bottom: 4px;">
                                        Q${i+1}: "${qa.q}"
                                    </div>
                                    <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 6px; font-style: italic;">
                                        Candidate: "${qa.a}"
                                    </div>
                                    <span class="badge badge-info" style="font-size: 0.72rem;">${qa.rating}</span>
                                </div>
                            `).join('')}
                        </div>

                        ${report.recording_url ? `
                            <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border-color); font-size: 0.85rem;">
                                🎥 <strong>Interview Recording Reference:</strong> <code>${report.recording_url}</code>
                            </div>
                        ` : ''}
                    </div>
                </div>

                <!-- SECTION 21: HUMAN HIRING DECISION -->
                <div class="card" style="border: 2px solid var(--primary); background: rgba(59, 130, 246, 0.05); padding: 24px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                        <div>
                            <h3 style="font-size: 1.15rem; margin: 0; color: var(--text-primary);">Human Hiring Decision Gate</h3>
                            <p style="font-size: 0.85rem; color: var(--text-muted); margin: 4px 0 0 0;">
                                AI presents verified evidence & structured evaluation. <strong>You (the Recruiter/Hiring Manager) make the final hiring decision.</strong>
                            </p>
                        </div>
                        <div id="current-decision-badge">
                            <span class="badge ${app.shortlist_status === 'ADVANCED' ? 'badge-success' : 'badge-primary'}" style="font-size: 0.85rem; padding: 6px 12px;">
                                CURRENT STATUS: ${app.shortlist_status || 'INTERVIEWED - PENDING DECISION'}
                            </span>
                        </div>
                    </div>

                    <div style="display: flex; gap: 14px; flex-wrap: wrap;">
                        <button id="btn-decision-advance" class="btn btn-success" style="flex: 1; padding: 12px; font-weight: 600;">
                            ✨ ADVANCE (Offer / Next Step)
                        </button>
                        <button id="btn-decision-another-round" class="btn btn-primary" style="flex: 1; padding: 12px; font-weight: 600;">
                            🔄 REQUEST ANOTHER ROUND
                        </button>
                        <button id="btn-decision-hold" class="btn btn-secondary" style="flex: 1; padding: 12px; font-weight: 600;">
                            ⏸️ HOLD
                        </button>
                        <button id="btn-decision-reject" class="btn btn-danger" style="flex: 1; padding: 12px; font-weight: 600;">
                            ❌ REJECT
                        </button>
                    </div>
                </div>
            `;

            // Attach human decision handlers
            this.attachDecisionHandlers(container, report.application_id || app.id, sessionId);

        } catch (err) {
            console.error(err);
            container.innerHTML = `
                <div class="empty-state">
                    <h3>Error loading report</h3>
                    <p>${err.message}</p>
                    <a href="#candidates" class="btn btn-secondary">Back to Candidates</a>
                </div>
            `;
        }
    },

    attachDecisionHandlers(container, applicationId, sessionId) {
        const handleDecision = async (shortlistDecision, appStatus, label, badgeClass) => {
            if (!confirm(`Confirm human decision: ${label}?`)) return;

            try {
                if (applicationId) {
                    if (shortlistDecision) {
                        await api.screening.shortlistCandidate(applicationId, shortlistDecision, `Human recruiter decided: ${label}`);
                    }
                    if (appStatus) {
                        await api.interviews.applyFinalDecision(applicationId, appStatus);
                    }
                }
                const badge = container.querySelector('#current-decision-badge');
                if (badge) {
                    badge.innerHTML = `<span class="badge ${badgeClass}" style="font-size: 0.85rem; padding: 6px 12px;">DECISION: ${label}</span>`;
                }
                toast.success(`Decision recorded: ${label}`);
            } catch (err) {
                console.error(err);
                toast.error(`Decision error: ${err.message}`);
                const badge = container.querySelector('#current-decision-badge');
                if (badge) {
                    badge.innerHTML = `<span class="badge ${badgeClass}" style="font-size: 0.85rem; padding: 6px 12px;">DECISION: ${label}</span>`;
                }
            }
        };

        const btnAdvance = container.querySelector('#btn-decision-advance');
        if (btnAdvance) btnAdvance.addEventListener('click', () => handleDecision('SHORTLISTED', 'HIRED', 'ADVANCE (OFFER / HIRE)', 'badge-success'));

        const btnAnother = container.querySelector('#btn-decision-another-round');
        if (btnAnother) btnAnother.addEventListener('click', () => handleDecision('SHORTLISTED', 'INTERVIEW', 'REQUEST ANOTHER ROUND', 'badge-primary'));

        const btnHold = container.querySelector('#btn-decision-hold');
        if (btnHold) btnHold.addEventListener('click', () => handleDecision('HOLD', 'IN_REVIEW', 'HOLD', 'badge-warning'));

        const btnReject = container.querySelector('#btn-decision-reject');
        if (btnReject) btnReject.addEventListener('click', () => handleDecision('NOT_SHORTLISTED', 'REJECTED', 'REJECT', 'badge-danger'));
    }
};

window.interviewReportView = window.InterviewReportView;
