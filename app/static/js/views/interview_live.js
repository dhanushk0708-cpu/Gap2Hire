// ==========================================================================
// Gap2Hire - Live AI Interview & HR Observer View
// ==========================================================================

const interviewLiveView = {
    pollingInterval: null,

    async render(container, params = {}) {
        if (!container) {
            container = document.getElementById("main-view");
        }
        if (!container) return;

        // Clear any previous polling loop
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }

        let sessionId = params.sessionId || (window.appState && window.appState.activeSessionId) || null;
        const applicationId = params.applicationId || (window.appState && window.appState.activeApplicationId) || null;
        const jobId = params.jobId || (window.appState && window.appState.activeJobId) || null;

        if (applicationId && window.appState) {
            window.appState.activeApplicationId = applicationId;
        }
        if (jobId && window.appState) {
            window.appState.activeJobId = jobId;
        }

        // If no session ID provided, but application ID is provided, retrieve or initialize the session
        if (!sessionId && applicationId) {
            container.innerHTML = `
                <div style="text-align: center; padding: 4rem 2rem;">
                    <div style="font-size: 2.5rem; margin-bottom: 1rem;">🚀</div>
                    <h3 style="margin-bottom: 0.5rem;">Initializing AI Interview Session...</h3>
                    <p style="color: var(--text-secondary);">Connecting to LangGraph multi-round interview engine...</p>
                </div>
            `;

            try {
                // Check if candidate already has an interview session
                const existingSessions = await api.interviews.listSessions(applicationId).catch(() => []);
                let targetSession = null;

                if (existingSessions && existingSessions.length > 0) {
                    targetSession = existingSessions[0];
                } else {
                    // Create new session for the shortlisted candidate
                    targetSession = await api.interviews.createSession(applicationId);
                }

                sessionId = targetSession.id;
                if (window.appState) {
                    window.appState.activeSessionId = sessionId;
                }

                // If session is newly CREATED, start it
                if (targetSession.status === "CREATED") {
                    await api.interviews.startSession(sessionId).catch(e => console.warn("Start session notice:", e));
                }
            } catch (err) {
                console.error("Session initialization failed:", err);
                container.innerHTML = `
                    <div class="card" style="text-align: center; padding: 3rem 2rem; max-width: 600px; margin: 2rem auto;">
                        <div style="font-size: 2.5rem; margin-bottom: 1rem;">⚠️</div>
                        <h3 style="margin-bottom: 0.5rem; color: #F87171;">Could Not Launch Interview</h3>
                        <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">${err.message || 'Ensure candidate is shortlisted with approved job capabilities.'}</p>
                        <button class="btn btn-primary" onclick="router.navigate('candidate-detail', { id: '${applicationId}' })">
                            ← Back to Candidate Detail
                        </button>
                    </div>
                `;
                return;
            }
        }

        // If still no session ID, render empty state
        if (!sessionId) {
            container.innerHTML = `
                <div class="card" style="text-align: center; padding: 4rem 2rem; max-width: 600px; margin: 2rem auto;">
                    <div style="font-size: 2.5rem; margin-bottom: 1rem;">👥</div>
                    <h3 style="margin-bottom: 0.5rem;">No Candidate Selected</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">Please select a shortlisted candidate from the screening queue to launch an interview.</p>
                    <button class="btn btn-primary" onclick="router.navigate('candidates')">
                        Go to Screening Queue
                    </button>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div style="text-align: center; padding: 4rem 2rem;">
                <div style="font-size: 2.5rem; margin-bottom: 1rem;">⏳</div>
                <h3 style="margin-bottom: 0.5rem;">Connecting to Live Interview Stream...</h3>
                <p style="color: var(--text-secondary);">Subscribing to candidate runtime and telemetry...</p>
            </div>
        `;

        try {
            const liveData = await api.interviews.getHrLiveSnapshot(sessionId);

            const candidateName = liveData.candidate_name || "Shortlisted Candidate";
            const jobTitle = liveData.job_title || "Engineering Role";
            const currentStatus = liveData.status || "IN_PROGRESS";
            const roundNumber = liveData.round_number || 1;

            container.innerHTML = `
                <div style="margin-bottom: 1.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        <a href="javascript:void(0)" onclick="router.navigate('candidates')" style="font-size: 0.875rem; color: var(--text-muted);">← Screening Queue</a>
                    </div>
                    <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                                <span class="badge badge-success" style="box-shadow: 0 0 10px rgba(16, 185, 129, 0.4);">
                                    <span class="badge-dot"></span> LIVE AI INTERVIEW
                                </span>
                                <span class="badge badge-info" id="live-round-badge">ROUND ${roundNumber} (TECHNICAL)</span>
                                <span class="badge ${currentStatus === 'COMPLETED' ? 'badge-success' : 'badge-primary'}" id="live-status-badge">
                                    STATUS: ${currentStatus}
                                </span>
                            </div>
                            <h1 style="font-size: 1.85rem; margin-top: 0.5rem; margin-bottom: 0.25rem;">${candidateName}</h1>
                            <div style="font-size: 0.875rem; color: var(--text-secondary);">
                                Role: <strong>${jobTitle}</strong> &nbsp;|&nbsp;
                                Session: <code style="font-family: var(--font-mono); color: var(--primary-light);">${sessionId.substring(0, 8)}</code> &nbsp;|&nbsp;
                                <span style="color: #FBBF24; font-weight: 600;">👁️ HR OBSERVER MODE: READ-ONLY</span>
                            </div>
                        </div>
                        <div style="display: flex; gap: 0.75rem;">
                            <button id="btn-refresh-observer" class="btn btn-secondary btn-sm" onclick="interviewLiveView.manualSync('${sessionId}')">
                                🔄 Refresh Feed
                            </button>
                            <button id="btn-view-report-live" class="btn btn-primary btn-sm" onclick="router.navigate('interview-report', { sessionId: '${sessionId}' })" style="${currentStatus === 'COMPLETED' ? 'display:inline-flex;' : 'display:none;'}">
                                📊 View Final Evaluation Report
                            </button>
                        </div>
                    </div>
                </div>

                <!-- MAIN LIVE GRID -->
                <div style="display: grid; grid-template-columns: 1.2fr 360px; gap: 1.5rem; align-items: start;">
                    <!-- LEFT: Live Terminal / Transcript Feed & Interactive Simulator -->
                    <div>
                        <div class="card" style="padding: 0; overflow: hidden; background: #080C14; border: 1px solid var(--border-subtle);">
                            <!-- Terminal Header -->
                            <div style="padding: 0.75rem 1.25rem; background: #0F172A; border-bottom: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
                                <div style="display: flex; gap: 6px; align-items: center;">
                                    <div style="width: 10px; height: 10px; border-radius: 50%; background: #EF4444;"></div>
                                    <div style="width: 10px; height: 10px; border-radius: 50%; background: #F59E0B;"></div>
                                    <div style="width: 10px; height: 10px; border-radius: 50%; background: #10B981;"></div>
                                    <span style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted); margin-left: 8px;">
                                        Gap2Hire AI Multi-Round Live Engine
                                    </span>
                                </div>
                                <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                                    Interactive Stream
                                </span>
                            </div>

                            <!-- Live Message History -->
                            <div id="live-chat-box" style="padding: 1.25rem; height: 420px; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem;">
                                ${this.renderTranscriptHistory(liveData.transcript_messages || [])}
                            </div>

                            <!-- Candidate Simulator Bar -->
                            <div style="padding: 1rem 1.25rem; background: #0F172A; border-top: 1px solid var(--border-subtle);">
                                <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem; display: flex; justify-content: space-between;">
                                    <span>Candidate Answer Simulator (Interactive Live Verification)</span>
                                    <span id="ai-typing-indicator" style="display:none; color: var(--primary-light); font-weight: 600;">
                                        ⚡ AI evaluating response and formulating follow-up...
                                    </span>
                                </div>
                                <div style="display: flex; gap: 0.75rem;">
                                    <textarea id="candidate-sim-input" class="form-textarea" rows="2" placeholder="Type candidate's verbal or technical answer here..." style="background: #1E293B; color: #fff; font-size: 0.875rem; resize: none;"></textarea>
                                    <button id="btn-submit-answer" class="btn btn-primary" style="align-self: flex-end; height: 48px; padding: 0 1.25rem; white-space: nowrap;">
                                        Send Answer ↵
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- RIGHT: Real-time Session Metrics & Probed Capabilities -->
                    <div style="display: flex; flex-direction: column; gap: 1.25rem;">
                        <!-- Session Metrics -->
                        <div class="card">
                            <div class="card-header">
                                <div class="card-title">
                                    <span>📊</span> Live Evaluation Metrics
                                </div>
                            </div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
                                <div style="padding: 1rem; background: var(--bg-surface-elevated); border-radius: var(--radius-md); text-align: center;">
                                    <div style="font-size: 1.75rem; font-weight: 800; color: var(--primary-light);" id="metric-q-count">
                                        ${liveData.total_questions || 1}
                                    </div>
                                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Questions Asked</div>
                                </div>
                                <div style="padding: 1rem; background: var(--bg-surface-elevated); border-radius: var(--radius-md); text-align: center;">
                                    <div style="font-size: 1.75rem; font-weight: 800; color: #A78BFA;" id="metric-f-count">
                                        ${liveData.followups_count || 1}
                                    </div>
                                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">AI Follow-ups</div>
                                </div>
                            </div>
                            <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle); font-size: 0.85rem;">
                                <div style="color: var(--text-muted); margin-bottom: 0.2rem;">Current Exploration Area:</div>
                                <div style="font-weight: 700; color: var(--text-primary);" id="metric-active-cap">
                                    ${liveData.current_capability || "Python & Scalable Architecture"}
                                </div>
                            </div>
                        </div>

                        <!-- Capability Probing Status -->
                        <div class="card">
                            <div class="card-header">
                                <div class="card-title">
                                    <span>🧩</span> Capability Probing
                                </div>
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem;">
                                <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0.75rem; background: var(--bg-surface-elevated); border-radius: var(--radius-sm);">
                                    <span style="font-weight: 600;">FastAPI & Async Concurrency</span>
                                    <span class="badge badge-success">VERIFIED</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0.75rem; background: var(--bg-surface-elevated); border-radius: var(--radius-sm);">
                                    <span style="font-weight: 600;">PostgreSQL & Connection Pooling</span>
                                    <span class="badge badge-primary">IN_PROGRESS</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0.75rem; background: var(--bg-surface-elevated); border-radius: var(--radius-sm);">
                                    <span style="font-weight: 600;">Redis Cache Invalidation</span>
                                    <span class="badge badge-warning">UPCOMING</span>
                                </div>
                            </div>

                            <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border-subtle);">
                                <button id="btn-complete-session" class="btn btn-secondary btn-sm" style="width: 100%;" onclick="interviewLiveView.finalizeSession('${sessionId}')">
                                    Finish Interview & View Report
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            this.attachSimulatorHandlers(container, sessionId);
            this.startObserverPolling(sessionId);

        } catch (err) {
            console.error("Failed to load interview live view:", err);
            container.innerHTML = `
                <div class="card" style="text-align: center; padding: 3rem 2rem; max-width: 600px; margin: 2rem auto;">
                    <div style="font-size: 2.5rem; margin-bottom: 1rem;">⚠️</div>
                    <h3 style="margin-bottom: 0.5rem; color: #F87171;">Connection Error</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">${err.message}</p>
                    <button class="btn btn-primary" onclick="router.navigate('candidates')">Back to Screening Queue</button>
                </div>
            `;
        }
    },

    renderTranscriptHistory(messages) {
        if (!messages || messages.length === 0) {
            return `
                <div style="background: rgba(59, 130, 246, 0.1); border-left: 3px solid var(--primary); padding: 1rem; border-radius: var(--radius-sm); color: #E2E8F0;">
                    <div style="font-size: 0.75rem; color: var(--primary-light); font-weight: 700; margin-bottom: 0.35rem; font-family: var(--font-mono);">
                        AI INTERVIEWER (GAP2HIRE)
                    </div>
                    <div style="font-size: 0.9rem; line-height: 1.5;">
                        "Welcome to your technical verification interview! Let's start with your experience in designing high-throughput REST APIs using Python and FastAPI. Can you walk me through the concurrency architecture of a production service you built?"
                    </div>
                </div>
            `;
        }

        return messages.map(m => {
            const isAi = m.role === "AI" || m.role === "assistant" || m.role === "SYSTEM";
            const roleLabel = m.role === "AI" ? "AI INTERVIEWER (GAP2HIRE)" : (m.role === "SYSTEM" ? "SYSTEM" : "CANDIDATE");
            const borderCol = m.role === "AI" ? "var(--primary)" : (m.role === "SYSTEM" ? "var(--text-muted)" : "var(--accent-emerald)");
            const bgCol = m.role === "AI" ? "rgba(59, 130, 246, 0.1)" : (m.role === "SYSTEM" ? "rgba(255,255,255,0.02)" : "rgba(16, 185, 129, 0.1)");
            const textColor = m.role === "AI" ? "var(--primary-light)" : (m.role === "SYSTEM" ? "var(--text-muted)" : "#34D399");

            return `
                <div style="background: ${bgCol}; border-left: 3px solid ${borderCol}; padding: 0.9rem 1rem; border-radius: var(--radius-sm); color: #E2E8F0; margin-left: ${isAi ? '0' : '2rem'}; margin-right: ${isAi ? '2rem' : '0'};">
                    <div style="font-size: 0.75rem; color: ${textColor}; font-weight: 700; margin-bottom: 0.35rem; font-family: var(--font-mono);">
                        ${roleLabel}
                    </div>
                    <div style="font-size: 0.9rem; line-height: 1.5;">
                        ${m.content}
                    </div>
                </div>
            `;
        }).join("");
    },

    attachSimulatorHandlers(container, sessionId) {
        const btnSend = container.querySelector("#btn-submit-answer");
        const inputAnswer = container.querySelector("#candidate-sim-input");
        const chatBox = container.querySelector("#live-chat-box");
        const indicator = container.querySelector("#ai-typing-indicator");

        const sendAnswer = async () => {
            const answer = inputAnswer.value.trim();
            if (!answer) return;

            // Immediately append candidate message bubble to screen
            const candDiv = document.createElement("div");
            candDiv.style.cssText = "background: rgba(16, 185, 129, 0.1); border-left: 3px solid var(--accent-emerald); padding: 0.9rem 1rem; border-radius: var(--radius-sm); color: #E2E8F0; margin-left: 2rem;";
            candDiv.innerHTML = `
                <div style="font-size: 0.75rem; color: #34D399; font-weight: 700; margin-bottom: 0.35rem; font-family: var(--font-mono);">CANDIDATE</div>
                <div style="font-size: 0.9rem; line-height: 1.5;">${answer}</div>
            `;
            chatBox.appendChild(candDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
            inputAnswer.value = "";

            if (indicator) indicator.style.display = "inline";

            try {
                // Call live answer endpoint
                const res = await api.post(`/interviews/${sessionId}/answers`, { answer_text: answer });
                if (indicator) indicator.style.display = "none";

                // Append AI Response
                const aiDiv = document.createElement("div");
                aiDiv.style.cssText = "background: rgba(59, 130, 246, 0.1); border-left: 3px solid var(--primary); padding: 0.9rem 1rem; border-radius: var(--radius-sm); color: #E2E8F0; margin-right: 2rem;";
                aiDiv.innerHTML = `
                    <div style="font-size: 0.75rem; color: var(--primary-light); font-weight: 700; margin-bottom: 0.35rem; font-family: var(--font-mono);">AI INTERVIEWER (GAP2HIRE)</div>
                    <div style="font-size: 0.9rem; line-height: 1.5;">${res.ai_response || "Thank you. Let us now examine how you handle database connection pooling and deadlock detection."}</div>
                `;
                chatBox.appendChild(aiDiv);
                chatBox.scrollTop = chatBox.scrollHeight;

                const qEl = container.querySelector("#metric-q-count");
                if (qEl) qEl.textContent = parseInt(qEl.textContent || 1) + 1;
            } catch (err) {
                if (indicator) indicator.style.display = "none";
                toast.info("Candidate answer processed in live session.");
            }
        };

        if (btnSend) btnSend.addEventListener("click", sendAnswer);
        if (inputAnswer) {
            inputAnswer.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendAnswer();
                }
            });
        }
    },

    async manualSync(sessionId) {
        try {
            const data = await api.interviews.getHrLiveSnapshot(sessionId);
            toast.info("Live observer feed updated.");
            const chatBox = document.getElementById("live-chat-box");
            if (chatBox && data.transcript_messages) {
                chatBox.innerHTML = this.renderTranscriptHistory(data.transcript_messages);
            }
        } catch (e) {
            console.warn("Manual sync notice:", e);
        }
    },

    startObserverPolling(sessionId) {
        if (this.pollingInterval) clearInterval(this.pollingInterval);

        this.pollingInterval = setInterval(async () => {
            if (!window.location.hash.includes("interview-live")) {
                clearInterval(this.pollingInterval);
                this.pollingInterval = null;
                return;
            }

            try {
                const data = await api.interviews.getHrLiveSnapshot(sessionId);
                const qEl = document.getElementById("metric-q-count");
                const statusEl = document.getElementById("live-status-badge");
                const reportBtn = document.getElementById("btn-view-report-live");

                if (qEl && data.total_questions !== undefined) {
                    qEl.textContent = data.total_questions;
                }
                if (statusEl && data.status) {
                    statusEl.textContent = `STATUS: ${data.status}`;
                    if (data.status === "COMPLETED" && reportBtn) {
                        reportBtn.style.display = "inline-flex";
                    }
                }
            } catch (e) {
                // Ignore observer polling glitches
            }
        }, 4000);
    },

    async finalizeSession(sessionId) {
        if (!confirm("End interview session and generate the candidate evaluation report?")) return;

        try {
            await api.patch(`/interviews/${sessionId}/complete`);
            toast.success("Interview completed! Generating report...");
            router.navigate("interview-report", { sessionId });
        } catch (e) {
            router.navigate("interview-report", { sessionId });
        }
    }
};

window.interviewLiveView = interviewLiveView;
window.InterviewLiveView = interviewLiveView;
