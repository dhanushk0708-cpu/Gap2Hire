// ==========================================================================
// Gap2Hire Phase 10 - Post-Interview Analysis & Evidence Report
// Evidence over scores • Zero AI cheating accusations • Human hiring decision gate
// ==========================================================================

window.InterviewReportView = {
    async render(container, params = {}) {
        const sessionId = params.sessionId || (window.appState && window.appState.activeSessionId);

        if (!sessionId) {
            container.innerHTML = `
                <div class="empty-state" style="text-align: center; padding: 3rem; background: var(--bg-surface); border-radius: var(--radius-lg); border: 1px solid var(--border-color); max-width: 600px; margin: 2rem auto;">
                    <div style="font-size: 2.5rem; margin-bottom: 1rem;">📋</div>
                    <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">No Interview Session Selected</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 1.5rem; font-size: 0.95rem;">Select a completed interview from the candidate list or screening queue to inspect its structured evidence report.</p>
                    <a href="#candidates" class="btn btn-primary">Go to Candidate Screening Queue</a>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div style="text-align: center; padding: 4rem;">
                <div class="loading-spinner" style="margin: 0 auto 1rem;"></div>
                <h4 style="color: var(--text-primary); margin-bottom: 0.25rem;">Synthesizing Post-Interview Evidence Report...</h4>
                <p style="color: var(--text-secondary); font-size: 0.85rem;">Correlating resume claims with live Q&A verification and integrity telemetry...</p>
            </div>
        `;

        try {
            const report = await window.ApiClient.getInterviewReport(sessionId);
            const app = report.application_id ? await window.ApiClient.getApplicationDetail(report.application_id).catch(() => ({})) : {};

            const demonstratedCaps = report.demonstrated_capabilities || [];
            const claimedCaps = report.claimed_capabilities || [];
            const unknownCaps = report.unknown_capabilities || [];
            const verNeededCaps = report.verification_needed || [];
            const questionFindings = report.question_findings || [];
            const roundSummaries = report.round_summaries || [];
            const integSummary = report.integrity_summary || {};
            const recommendations = report.recommendations_for_human_review || [];

            container.innerHTML = `
                <div style="padding: 1.5rem 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <!-- HEADER -->
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.75rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1.25rem;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.4rem;">
                                <span class="badge badge-success" style="font-size: 0.75rem; font-weight: 700; padding: 3px 8px;">
                                    ✓ INTERVIEW COMPLETED
                                </span>
                                <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">
                                    Session: ${sessionId.substring(0, 8)}
                                </span>
                            </div>
                            <h1 style="font-size: 1.6rem; font-weight: 700; color: var(--text-primary); margin: 0;">
                                Post-Interview Evidence Report: ${report.candidate_name || 'Candidate Evaluation'}
                            </h1>
                            <p style="color: var(--text-secondary); font-size: 0.88rem; margin-top: 0.25rem;">
                                Target Job: <strong>${report.job_title || 'Engineering Role'}</strong> &nbsp;•&nbsp;
                                Evaluated: ${new Date(report.completed_at || report.generated_at || Date.now()).toLocaleDateString(undefined, { dateStyle: 'long' })}
                            </p>
                        </div>
                        <div style="display: flex; gap: 0.5rem;">
                            <button onclick="window.print()" class="btn btn-secondary btn-sm">🖨️ Export PDF</button>
                            <a href="#candidates" class="btn btn-secondary btn-sm">← Back to Queue</a>
                        </div>
                    </div>

                    <!-- 1. EXECUTIVE EVIDENCE SUMMARY & STATS -->
                    <div class="card" style="margin-bottom: 1.75rem; border-left: 4px solid var(--primary-color); background: rgba(37, 99, 235, 0.04); padding: 1.25rem 1.5rem;">
                        <h3 style="font-size: 1.05rem; font-weight: 700; margin-bottom: 0.5rem; color: var(--text-primary);">
                            Structured Executive Evidence Summary
                        </h3>
                        <p style="font-size: 0.92rem; line-height: 1.55; color: var(--text-primary); margin-bottom: 1.25rem;">
                            ${report.summary || report.executive_summary || 'Evidence analysis complete. See below for detailed capability verification findings.'}
                        </p>
                        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem;">
                            <div style="padding: 0.85rem; background: var(--bg-surface); border-radius: var(--radius-md); border: 1px solid var(--border-color); text-align: center;">
                                <div style="font-size: 1.35rem; font-weight: 700; color: #10B981;">
                                    ${demonstratedCaps.length}
                                </div>
                                <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Demonstrated Skills</div>
                            </div>
                            <div style="padding: 0.85rem; background: var(--bg-surface); border-radius: var(--radius-md); border: 1px solid var(--border-color); text-align: center;">
                                <div style="font-size: 1.35rem; font-weight: 700; color: #3B82F6;">
                                    ${claimedCaps.length}
                                </div>
                                <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Retained Claims</div>
                            </div>
                            <div style="padding: 0.85rem; background: var(--bg-surface); border-radius: var(--radius-md); border: 1px solid var(--border-color); text-align: center;">
                                <div style="font-size: 1.35rem; font-weight: 700; color: #F59E0B;">
                                    ${verNeededCaps.length}
                                </div>
                                <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Verification Needed</div>
                            </div>
                            <div style="padding: 0.85rem; background: var(--bg-surface); border-radius: var(--radius-md); border: 1px solid var(--border-color); text-align: center;">
                                <div style="font-size: 1.35rem; font-weight: 700; color: var(--text-muted);">
                                    ${unknownCaps.length}
                                </div>
                                <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Remaining Unknowns</div>
                            </div>
                        </div>
                    </div>

                    <!-- 2. CAPABILITY EVIDENCE SYNTHESIS (PRE VS POST INTERVIEW) -->
                    <div class="card" style="margin-bottom: 1.75rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.75rem;">
                            <div>
                                <h3 style="font-size: 1.05rem; font-weight: 700; color: var(--text-primary); margin: 0;">
                                    Capability Evidence Synthesis (Pre-Interview vs. Post-Interview)
                                </h3>
                                <p style="font-size: 0.8rem; color: var(--text-muted); margin: 2px 0 0 0;">
                                    Traceable progression from resume claims to live interview verification without score fabrication.
                                </p>
                            </div>
                        </div>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem;">
                            ${(report.evidence_findings || []).map(cap => `
                                <div style="padding: 1rem; background: var(--bg-surface-elevated); border-radius: var(--radius-md); border: 1px solid var(--border-color);">
                                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                                        <strong style="font-size: 0.95rem; color: var(--text-primary);">${cap.capability_name}</strong>
                                        <div style="display: flex; gap: 0.35rem;">
                                            <span class="badge ${cap.post_interview_provenance === 'DEMONSTRATED' ? 'badge-success' : cap.post_interview_provenance === 'VERIFICATION_NEEDED' ? 'badge-warning' : 'badge-neutral'}" style="font-size: 0.7rem;">
                                                ${cap.post_interview_provenance}
                                            </span>
                                        </div>
                                    </div>
                                    <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                                        Pre-Interview: <span style="font-weight: 600;">${cap.pre_interview_provenance}</span> &nbsp;→&nbsp;
                                        Post-Interview: <span style="font-weight: 700; color: ${cap.is_verified_in_interview ? '#10B981' : 'var(--text-secondary)'};">${cap.post_interview_provenance}</span>
                                    </div>
                                    <p style="font-size: 0.825rem; color: var(--text-secondary); margin: 0 0 0.5rem 0; line-height: 1.4;">
                                        ${cap.observation}
                                    </p>
                                    <div style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono); border-top: 1px dashed var(--border-color); padding-top: 0.35rem;">
                                        Trace Sources: ${(cap.source_references || []).map(s => s.type).join(', ') || 'Direct Assessment'}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <!-- 3. QUESTION-LEVEL FINDINGS & REASONING -->
                    <div class="card" style="margin-bottom: 1.75rem;">
                        <h3 style="font-size: 1.05rem; font-weight: 700; color: var(--text-primary); margin-bottom: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.75rem;">
                            Live Q&A Evidence & Probing Findings (${questionFindings.length} Questions Evaluated)
                        </h3>
                        <div style="display: flex; flex-direction: column; gap: 1rem;">
                            ${questionFindings.map((qf, idx) => `
                                <div style="padding: 1rem; background: var(--bg-surface-elevated); border-left: 3px solid var(--primary-color); border-radius: 0 var(--radius-md) var(--radius-md) 0; border: 1px solid var(--border-color); border-left-width: 3px;">
                                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                                        <div style="font-weight: 700; font-size: 0.9rem; color: var(--text-primary);">
                                            Q${idx + 1}. "${qf.question_text}"
                                        </div>
                                        <div style="display: flex; gap: 0.35rem; white-space: nowrap;">
                                            ${qf.concept ? `<span class="badge badge-info" style="font-size: 0.68rem;">${qf.concept}</span>` : ''}
                                            <span class="badge ${qf.answer_quality === 'SUFFICIENT' ? 'badge-success' : qf.answer_quality === 'PARTIAL' ? 'badge-warning' : 'badge-neutral'}" style="font-size: 0.68rem;">
                                                ${qf.answer_quality || 'Evaluated'}
                                            </span>
                                        </div>
                                    </div>
                                    ${qf.candidate_answer ? `
                                        <div style="font-size: 0.83rem; color: var(--text-secondary); background: var(--bg-surface); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); margin-bottom: 0.5rem; font-style: italic;">
                                            "${qf.candidate_answer}"
                                        </div>
                                    ` : ''}
                                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; font-size: 0.78rem; padding-top: 0.35rem; border-top: 1px solid var(--border-color);">
                                        <div>
                                            <span style="color: #059669; font-weight: 600;">✓ Demonstrated:</span>
                                            <span style="color: var(--text-secondary);">${qf.what_was_demonstrated || 'Competency verified'}</span>
                                        </div>
                                        <div>
                                            <span style="color: #D97706; font-weight: 600;">🔍 Uncertain/Unresolved:</span>
                                            <span style="color: var(--text-secondary);">${qf.what_remains_uncertain || 'None noted'}</span>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <!-- 4. TWO-COLUMN: INTEGRITY OBSERVATIONS & HUMAN RECOMMENDATIONS -->
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.75rem;">
                        <!-- INTEGRITY OBSERVATIONS (Factual, non-accusatory telemetry) -->
                        <div class="card">
                            <h3 style="font-size: 1.05rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.75rem;">
                                🛡️ Session Integrity Telemetry
                            </h3>
                            <p style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 1rem;">
                                Observable client-side browser telemetry. Telemetry represents factual observations and does not classify candidate intent.
                            </p>
                            <div style="padding: 0.75rem 1rem; background: var(--bg-surface-elevated); border-radius: var(--radius-md); border: 1px solid var(--border-color); margin-bottom: 1rem;">
                                <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.25rem;">
                                    ${integSummary.summary_text || 'No integrity anomalies recorded.'}
                                </div>
                                <div style="font-size: 0.78rem; color: var(--text-muted);">
                                    Total Recorded Observations: <strong>${integSummary.total_events || 0}</strong>
                                </div>
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 200px; overflow-y: auto;">
                                ${(integSummary.observations || []).map(obs => `
                                    <div style="padding: 0.5rem 0.75rem; background: var(--bg-surface); border-radius: 4px; border: 1px solid var(--border-color); font-size: 0.8rem; display: flex; justify-content: space-between; align-items: center;">
                                        <span><code>${obs.event_type}</code></span>
                                        <span class="badge badge-neutral" style="font-size: 0.7rem;">${obs.count} event(s)</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>

                        <!-- RECOMMENDATIONS FOR HUMAN REVIEW -->
                        <div class="card">
                            <h3 style="font-size: 1.05rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.75rem;">
                                💡 Focus Areas for Human Review
                            </h3>
                            <p style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 1rem;">
                                Key technical highlights and unresolved evidence areas for the recruiting team's deliberation.
                            </p>
                            <div style="display: flex; flex-direction: column; gap: 0.75rem; max-height: 280px; overflow-y: auto;">
                                ${recommendations.map(rec => `
                                    <div style="padding: 0.75rem; background: var(--bg-surface-elevated); border-radius: var(--radius-md); border: 1px solid var(--border-color);">
                                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                                            <strong style="font-size: 0.85rem; color: var(--text-primary);">${rec.topic}</strong>
                                            <span class="badge ${rec.category === 'STRENGTH' ? 'badge-success' : rec.category === 'VERIFICATION_SUGGESTION' ? 'badge-warning' : 'badge-info'}" style="font-size: 0.65rem;">
                                                ${rec.category}
                                            </span>
                                        </div>
                                        <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.4;">
                                            ${rec.detail}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </div>

                    <!-- 5. HUMAN HIRING DECISION GATE & AUDIT TRAIL -->
                    <div class="card" style="border: 2px solid var(--primary-color); background: rgba(37, 99, 235, 0.03); padding: 1.5rem; border-radius: var(--radius-lg);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem;">
                            <div>
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <h3 style="font-size: 1.15rem; font-weight: 700; margin: 0; color: var(--text-primary);">
                                        Human Hiring Decision Gate
                                    </h3>
                                    <span style="background: #E0E7FF; color: #3730A3; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase;">
                                        Human-Controlled
                                    </span>
                                </div>
                                <p style="font-size: 0.825rem; color: var(--text-muted); margin: 3px 0 0 0;">
                                    AI synthesizes evidence & observations. <strong>Authorized human recruiters/hiring managers own the final hiring decision.</strong>
                                </p>
                            </div>
                            <div id="current-decision-badge">
                                <span class="badge ${app.shortlist_status === 'SELECTED' ? 'badge-success' : app.shortlist_status === 'REJECTED' ? 'badge-danger' : app.shortlist_status === 'ON_HOLD' ? 'badge-warning' : 'badge-primary'}" style="font-size: 0.85rem; padding: 6px 14px;">
                                    CURRENT STATUS: ${app.status || app.shortlist_status || 'INTERVIEW COMPLETED'}
                                </span>
                            </div>
                        </div>

                        <!-- Decision Input & Rationale -->
                        <div style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1.25rem; margin-bottom: 1.25rem;">
                            <label style="display: block; font-size: 0.85rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.4rem;">
                                Human Decision Rationale & Justification <span style="color: #EF4444;">*</span>
                            </label>
                            <textarea id="hiring-decision-reason" rows="3" placeholder="State human rationale based on evaluated interview evidence (e.g., 'Demonstrated strong async PostgreSQL & system design skills; live answers confirmed resume claims...')" style="width: 100%; border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.75rem; font-size: 0.85rem; background: var(--bg-surface); color: var(--text-primary); font-family: inherit; resize: vertical; line-height: 1.4;"></textarea>
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.35rem;">
                                <small style="color: var(--text-muted); font-size: 0.75rem;">Minimum 5 characters required. Reasons are permanently audited for compliance.</small>
                            </div>

                            <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 1rem;">
                                <button id="btn-decision-selected" class="btn btn-success" style="flex: 1; padding: 0.75rem; font-weight: 600; min-width: 140px; border-radius: 6px;">
                                    ✅ SELECTED
                                </button>
                                <button id="btn-decision-on-hold" class="btn btn-secondary" style="flex: 1; padding: 0.75rem; font-weight: 600; min-width: 140px; border-radius: 6px; background: #F59E0B; color: #FFFFFF; border: none;">
                                    ⏸️ ON HOLD
                                </button>
                                <button id="btn-decision-rejected" class="btn btn-danger" style="flex: 1; padding: 0.75rem; font-weight: 600; min-width: 140px; border-radius: 6px;">
                                    ❌ REJECTED
                                </button>
                            </div>
                        </div>

                        <!-- Decision History / Audit Trail -->
                        <div id="hiring-decision-history-container" style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1.25rem;">
                            <h4 style="font-size: 0.9rem; font-weight: 700; color: var(--text-primary); margin: 0 0 0.75rem 0; display: flex; align-items: center; gap: 0.5rem;">
                                <span>📋</span> Auditable Decision History
                            </h4>
                            <div id="decision-history-list" style="font-size: 0.825rem; color: var(--text-muted);">
                                Loading decision audit trail...
                            </div>
                        </div>
                    </div>
                </div>
            `;

            const targetAppId = report.application_id || app.id;
            this.attachDecisionHandlers(container, targetAppId, sessionId);
            this.loadDecisionHistory(container, targetAppId);

        } catch (err) {
            console.error(err);
            container.innerHTML = `
                <div class="empty-state" style="text-align: center; padding: 3rem; background: var(--bg-surface); border-radius: var(--radius-lg); border: 1px solid var(--border-color); max-width: 600px; margin: 2rem auto;">
                    <h3 style="color: #EF4444; margin-bottom: 0.5rem;">Could not load interview report</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 1.5rem; font-size: 0.95rem;">${err.message}</p>
                    <a href="#candidates" class="btn btn-secondary">Back to Candidates</a>
                </div>
            `;
        }
    },

    async loadDecisionHistory(container, applicationId) {
        const listEl = container.querySelector('#decision-history-list');
        if (!listEl || !applicationId) return;

        try {
            const resp = await api.hiringDecisions.getHistory(applicationId);
            if (!resp.history || resp.history.length === 0) {
                listEl.innerHTML = '<div style="font-style: italic; color: var(--text-muted); padding: 0.5rem 0;">No human hiring decision recorded yet. Decision remains pending.</div>';
                return;
            }

            listEl.innerHTML = `
                <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                    ${resp.history.map((item, idx) => {
                        const badgeColor = item.decision === 'SELECTED' ? 'badge-success' : item.decision === 'REJECTED' ? 'badge-danger' : 'badge-warning';
                        return `
                            <div style="padding: 0.75rem; background: var(--bg-surface-secondary); border-radius: var(--radius-sm); border-left: 3px solid ${item.decision === 'SELECTED' ? '#10B981' : item.decision === 'REJECTED' ? '#EF4444' : '#F59E0B'};">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap; gap: 0.5rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                                        <span class="badge ${badgeColor}" style="font-size: 0.75rem; font-weight: 700;">${item.decision}</span>
                                        <span style="font-weight: 600; color: var(--text-primary); font-size: 0.8rem;">Decided by: ${item.decided_by_name || 'Authorized Recruiter'}</span>
                                    </div>
                                    <span style="font-size: 0.75rem; color: var(--text-muted);">${new Date(item.decided_at).toLocaleString()}</span>
                                </div>
                                <div style="color: var(--text-secondary); font-size: 0.825rem; line-height: 1.4;">
                                    "${item.decision_reason}"
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;
        } catch (err) {
            console.error("Failed to load decision history:", err);
            listEl.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem;">Unable to load decision audit trail.</div>';
        }
    },

    attachDecisionHandlers(container, applicationId, sessionId) {
        const handleDecision = async (decision, label, badgeClass) => {
            const reasonInput = container.querySelector('#hiring-decision-reason');
            const reason = reasonInput ? reasonInput.value.trim() : '';

            if (!reason || reason.length < 5) {
                alert('Please enter a meaningful human rationale for this decision (at least 5 characters).');
                if (reasonInput) reasonInput.focus();
                return;
            }

            if (!confirm(`Confirm HUMAN decision: ${label}?\n\nRationale:\n"${reason}"\n\nThis decision will be audited with your user identity.`)) {
                return;
            }

            try {
                if (applicationId) {
                    const result = await api.hiringDecisions.submitDecision(applicationId, decision, reason);
                    const badge = container.querySelector('#current-decision-badge');
                    if (badge) {
                        badge.innerHTML = `<span class="badge ${badgeClass}" style="font-size: 0.85rem; padding: 6px 14px;">DECISION: ${decision}</span>`;
                    }
                    if (reasonInput) reasonInput.value = '';
                    toast.success(`Hiring decision recorded: ${decision}`);
                    await this.loadDecisionHistory(container, applicationId);
                }
            } catch (err) {
                console.error(err);
                toast.error(`Decision error: ${err.message}`);
            }
        };

        const btnSelected = container.querySelector('#btn-decision-selected');
        if (btnSelected) btnSelected.addEventListener('click', () => handleDecision('SELECTED', 'SELECTED (HIRE)', 'badge-success'));

        const btnHold = container.querySelector('#btn-decision-on-hold');
        if (btnHold) btnHold.addEventListener('click', () => handleDecision('ON_HOLD', 'ON HOLD (REVIEW)', 'badge-warning'));

        const btnRejected = container.querySelector('#btn-decision-rejected');
        if (btnRejected) btnRejected.addEventListener('click', () => handleDecision('REJECTED', 'REJECTED', 'badge-danger'));
    }
};

window.interviewReportView = window.InterviewReportView;
window.InterviewReportView = window.InterviewReportView;
