// ==========================================================================
// Gap2Hire - Phase 7 & 8: Live Interview Room + Integrity Signals
// ==========================================================================

const interviewLiveView = {
    pollingInterval: null,
    websocket: null,
    mediaStream: null,
    mediaRecorder: null,
    recordedAudioChunks: [],
    isRecordingAudio: false,
    cameraActive: true,
    micActive: true,
    currentAvatarState: "IDLE",
    activeSessionId: null,

    // Phase 8: Integrity State Tracking
    lastVisibilityState: null,
    lastFullscreenState: false,
    visibilityListener: null,
    fullscreenListener: null,
    hasConnectedOnce: false,

    async render(container, params = {}) {
        if (!container) {
            container = document.getElementById("main-view");
        }
        if (!container) return;

        this.cleanup();

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
                    <h3 style="margin-bottom: 0.5rem;">Initializing Live Interview Session...</h3>
                    <p style="color: var(--text-secondary);">Connecting to Gap2Hire real-time interview engine...</p>
                </div>
            `;

            try {
                const existingSessions = await api.interviews.listSessions(applicationId).catch(() => []);
                let targetSession = null;

                if (existingSessions && existingSessions.length > 0) {
                    targetSession = existingSessions[0];
                } else {
                    targetSession = await api.interviews.createSession(applicationId);
                }

                sessionId = targetSession.id;
                if (window.appState) {
                    window.appState.activeSessionId = sessionId;
                }

                if (targetSession.status === "CREATED" || targetSession.status === "SCHEDULED") {
                    await api.interviews.startSession(sessionId).catch(e => console.warn("Start session notice:", e));
                }
            } catch (err) {
                console.error("Session initialization failed:", err);
                container.innerHTML = `
                    <div class="card" style="text-align: center; padding: 3rem 2rem; max-width: 600px; margin: 2rem auto;">
                        <div style="font-size: 2.5rem; margin-bottom: 1rem;">⚠️</div>
                        <h3 style="margin-bottom: 0.5rem; color: #F87171;">Could Not Launch Interview Room</h3>
                        <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">${err.message || 'Ensure candidate is shortlisted with approved job capabilities.'}</p>
                        <button class="btn btn-primary" onclick="router.navigate('candidate-detail', { id: '${applicationId}' })">
                            ← Back to Candidate Detail
                        </button>
                    </div>
                `;
                return;
            }
        }

        if (!sessionId) {
            container.innerHTML = `
                <div class="card" style="text-align: center; padding: 4rem 2rem; max-width: 600px; margin: 2rem auto;">
                    <div style="font-size: 2.5rem; margin-bottom: 1rem;">👥</div>
                    <h3 style="margin-bottom: 0.5rem;">No Active Interview Session</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">Please select a scheduled candidate from the screening queue to open the live room.</p>
                    <button class="btn btn-primary" onclick="router.navigate('candidates')">
                        Go to Candidates Queue
                    </button>
                </div>
            `;
            return;
        }

        this.activeSessionId = sessionId;

        container.innerHTML = `
            <div style="text-align: center; padding: 4rem 2rem;">
                <div style="font-size: 2.5rem; margin-bottom: 1rem;">⏳</div>
                <h3 style="margin-bottom: 0.5rem;">Entering Live Interview Room...</h3>
                <p style="color: var(--text-secondary);">Checking session authorization and media devices...</p>
            </div>
        `;

        try {
            // Load session authorization & metadata
            let roomData = null;
            try {
                roomData = await api.interviews.getRoom(sessionId);
            } catch (err) {
                // Fallback to snapshot if room endpoint fails
                roomData = await api.interviews.getHrLiveSnapshot(sessionId);
            }

            const candidateName = roomData.candidate_name || "Candidate";
            const jobTitle = roomData.job_title || "Engineering Role";
            const currentStatus = roomData.status || "IN_PROGRESS";
            const roundNumber = roomData.round_number || 1;

            container.innerHTML = `
                <!-- TOP HEADER -->
                <div style="margin-bottom: 1.25rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.35rem;">
                                <span class="badge badge-success" style="box-shadow: 0 0 10px rgba(16, 185, 129, 0.4);">
                                    <span class="badge-dot"></span> LIVE INTERVIEW ROOM
                                </span>
                                <span class="badge badge-info" id="live-round-badge">ROUND ${roundNumber} (TECHNICAL)</span>
                                <span class="badge ${currentStatus === 'COMPLETED' ? 'badge-success' : 'badge-primary'}" id="live-status-badge">
                                    STATUS: ${currentStatus}
                                </span>
                                <span class="badge" id="ws-status-badge" style="background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3);">
                                    🟡 WS: CONNECTING...
                                </span>
                            </div>
                            <h1 style="font-size: 1.75rem; margin: 0.2rem 0;">${candidateName}</h1>
                            <div style="font-size: 0.85rem; color: var(--text-secondary);">
                                Position: <strong>${jobTitle}</strong> &nbsp;|&nbsp;
                                Session: <code style="font-family: var(--font-mono); color: var(--primary-light);">${sessionId.substring(0, 8)}</code>
                            </div>
                        </div>

                        <div style="display: flex; gap: 0.75rem; align-items: center;">
                            <button id="btn-fullscreen-toggle" class="btn btn-secondary btn-sm" onclick="interviewLiveView.toggleFullscreen()">
                                ⛶ Fullscreen
                            </button>
                            <button id="btn-reconnect-ws" class="btn btn-secondary btn-sm" style="display:none;" onclick="interviewLiveView.connectWebSocket('${sessionId}')">
                                🔌 Reconnect Room
                            </button>
                            <button id="btn-view-report-live" class="btn btn-primary btn-sm" onclick="router.navigate('interview-report', { sessionId: '${sessionId}' })" style="${currentStatus === 'COMPLETED' ? 'display:inline-flex;' : 'display:none;'}">
                                📊 View Evaluation Report
                            </button>
                        </div>
                    </div>
                </div>

                <!-- MAIN LIVE GRID: 2 COLUMNS -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; align-items: start;">

                    <!-- LEFT COLUMN: AI AVATAR + CANDIDATE CAMERA STAGE -->
                    <div style="display: flex; flex-direction: column; gap: 1.25rem;">

                        <!-- AI AVATAR CARD -->
                        <div class="card" style="padding: 1.25rem; background: #0F172A; border: 1px solid var(--border-subtle); position: relative; overflow: hidden;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <span style="font-size: 1.25rem;">🤖</span>
                                    <div>
                                        <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-primary);">Gap2Hire AI Interviewer</div>
                                        <div style="font-size: 0.75rem; color: var(--text-secondary);">Adaptive Real-Time Assessment Agent</div>
                                    </div>
                                </div>
                                <span id="avatar-state-badge" class="badge badge-info" style="font-family: var(--font-mono); font-size: 0.75rem;">
                                    IDLE (READY)
                                </span>
                            </div>

                            <!-- Avatar Stage Visual -->
                            <div id="ai-avatar-stage" style="height: 190px; background: radial-gradient(circle at center, #1E293B 0%, #0B0F17 100%); border-radius: var(--radius-md); display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; border: 1px solid rgba(255, 255, 255, 0.05); transition: all 0.3s ease;">

                                <!-- Dynamic Avatar Orb / Visual -->
                                <div id="avatar-orb" style="width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #3B82F6 0%, #6366F1 100%); box-shadow: 0 0 25px rgba(59, 130, 246, 0.4); display: flex; align-items: center; justify-content: center; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);">
                                    <span id="avatar-orb-icon" style="font-size: 2rem;">🧠</span>
                                </div>

                                <!-- State Dynamic Indicator Text -->
                                <div id="avatar-state-text" style="margin-top: 0.85rem; font-size: 0.85rem; color: var(--primary-light); font-weight: 600; letter-spacing: 0.02em;">
                                    AI is ready for candidate response
                                </div>

                                <!-- Speaking / Waveform Animation Bars (Active when SPEAKING/LISTENING) -->
                                <div id="avatar-wave-container" style="display: none; align-items: center; gap: 4px; margin-top: 0.5rem; height: 16px;">
                                    <span class="wave-bar" style="width: 3px; height: 10px; background: #60A5FA; border-radius: 2px; animation: soundWave 0.8s ease-in-out infinite;"></span>
                                    <span class="wave-bar" style="width: 3px; height: 16px; background: #A78BFA; border-radius: 2px; animation: soundWave 0.6s ease-in-out infinite 0.1s;"></span>
                                    <span class="wave-bar" style="width: 3px; height: 12px; background: #34D399; border-radius: 2px; animation: soundWave 0.7s ease-in-out infinite 0.2s;"></span>
                                    <span class="wave-bar" style="width: 3px; height: 14px; background: #60A5FA; border-radius: 2px; animation: soundWave 0.9s ease-in-out infinite 0.15s;"></span>
                                </div>
                            </div>
                        </div>

                        <!-- CANDIDATE CAMERA & MICROPHONE STAGE -->
                        <div class="card" style="padding: 1.25rem; background: #0F172A; border: 1px solid var(--border-subtle);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <span style="font-size: 1.25rem;">🎥</span>
                                    <div>
                                        <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-primary);">Candidate Live Stream</div>
                                        <div style="font-size: 0.75rem; color: var(--text-secondary);">Video Preview & Audio Sensor</div>
                                    </div>
                                </div>
                                <div style="display: flex; gap: 0.4rem; align-items: center;">
                                    <span id="camera-status-badge" class="badge badge-success" style="font-size: 0.7rem;">
                                        📷 CAMERA: LIVE
                                    </span>
                                    <span id="mic-status-badge" class="badge badge-success" style="font-size: 0.7rem;">
                                        🎤 MIC: ACTIVE
                                    </span>
                                </div>
                            </div>

                            <!-- Video Preview Area -->
                            <div style="position: relative; width: 100%; height: 210px; background: #000; border-radius: var(--radius-md); overflow: hidden; display: flex; align-items: center; justify-content: center; border: 1px solid rgba(255, 255, 255, 0.08);">
                                <video id="candidate-live-video" autoplay playsinline muted style="width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1);"></video>

                                <!-- Video Disabled / Fallback Placeholder -->
                                <div id="candidate-video-placeholder" style="display: none; position: absolute; inset: 0; background: #111827; flex-direction: column; align-items: center; justify-content: center; color: var(--text-muted); text-align: center; padding: 1rem;">
                                    <div style="font-size: 2.2rem; margin-bottom: 0.4rem;">📷</div>
                                    <div style="font-weight: 600; color: var(--text-secondary); font-size: 0.9rem;">Camera Disabled / Preview Inactive</div>
                                    <div style="font-size: 0.75rem; margin-top: 0.25rem;">Click "Turn Camera On" or check browser device permissions</div>
                                </div>
                            </div>

                            <!-- Media Controls Toolbar -->
                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem;">
                                <div style="display: flex; gap: 0.5rem;">
                                    <button id="btn-toggle-camera" class="btn btn-secondary btn-sm" onclick="interviewLiveView.toggleCamera()">
                                        📷 Turn Camera Off
                                    </button>
                                    <button id="btn-toggle-mic" class="btn btn-secondary btn-sm" onclick="interviewLiveView.toggleMic()">
                                        🎤 Mute Mic
                                    </button>
                                </div>

                                <div style="display: flex; gap: 0.5rem; align-items: center;">
                                    <button id="btn-voice-talk" class="btn btn-primary btn-sm" style="background: linear-gradient(135deg, #10B981 0%, #059669 100%); border: none;">
                                        🎙️ Speak Answer (PTT)
                                    </button>
                                </div>
                            </div>

                            <!-- Device Permission Notice (if denied) -->
                            <div id="device-perm-alert" style="display: none; margin-top: 0.75rem; padding: 0.6rem 0.85rem; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: var(--radius-sm); font-size: 0.8rem; color: #FCA5A5; display: flex; justify-content: space-between; align-items: center;">
                                <span>⚠️ Camera or Mic access blocked in browser.</span>
                                <button class="btn btn-secondary btn-sm" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="interviewLiveView.initMediaDevices()">Retry Devices</button>
                            </div>
                        </div>
                    </div>

                    <!-- RIGHT COLUMN: LIVE INTERACTION TERMINAL & TRANSCRIPT -->
                    <div style="display: flex; flex-direction: column; gap: 1.25rem;">

                        <div class="card" style="padding: 0; overflow: hidden; background: #080C14; border: 1px solid var(--border-subtle); display: flex; flex-direction: column; height: 535px;">
                            <!-- Terminal Header -->
                            <div style="padding: 0.75rem 1.25rem; background: #0F172A; border-bottom: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
                                <div style="display: flex; gap: 6px; align-items: center;">
                                    <div style="width: 10px; height: 10px; border-radius: 50%; background: #EF4444;"></div>
                                    <div style="width: 10px; height: 10px; border-radius: 50%; background: #F59E0B;"></div>
                                    <div style="width: 10px; height: 10px; border-radius: 50%; background: #10B981;"></div>
                                    <span style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted); margin-left: 8px;">
                                        Real-Time Interview Dialogue & Telemetry
                                    </span>
                                </div>
                                <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);" id="term-round-indicator">
                                    Round ${roundNumber}
                                </span>
                            </div>

                            <!-- Live Chat / Transcript Box -->
                            <div id="live-chat-box" style="padding: 1.25rem; flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 0.85rem;">
                                ${this.renderTranscriptHistory(roomData.transcript_messages || [])}
                            </div>

                            <!-- Input Bar -->
                            <div style="padding: 0.85rem 1.25rem; background: #0F172A; border-top: 1px solid var(--border-subtle);">
                                <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.4rem; display: flex; justify-content: space-between; align-items: center;">
                                    <span>Candidate Response Console</span>
                                    <span id="ai-typing-indicator" style="display:none; color: var(--primary-light); font-weight: 600;">
                                        ⚡ AI evaluating response and generating follow-up...
                                    </span>
                                </div>
                                <div style="display: flex; gap: 0.6rem;">
                                    <textarea id="candidate-live-input" class="form-textarea" rows="2" placeholder="Type your response or click 'Speak Answer' to speak..." style="background: #1E293B; color: #fff; font-size: 0.875rem; resize: none;"></textarea>
                                    <button id="btn-send-message" class="btn btn-primary" style="align-self: flex-end; height: 48px; padding: 0 1.25rem; white-space: nowrap;">
                                        Send ↵
                                    </button>
                                </div>
                            </div>
                        </div>

                    </div>
                </div>

                <style>
                    @keyframes soundWave {
                        0%, 100% { height: 6px; }
                        50% { height: 18px; }
                    }
                </style>
            `;

            // Initialize camera/mic, integrity signal listeners, and websocket connection
            this.initMediaDevices();
            this.setupIntegrityListeners();
            this.connectWebSocket(sessionId);
            this.attachInputHandlers(container, sessionId);

        } catch (err) {
            console.error("Failed to load live interview room:", err);
            container.innerHTML = `
                <div class="card" style="text-align: center; padding: 3rem 2rem; max-width: 600px; margin: 2rem auto;">
                    <div style="font-size: 2.5rem; margin-bottom: 1rem;">⚠️</div>
                    <h3 style="margin-bottom: 0.5rem; color: #F87171;">Access Denied or Connection Error</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">${err.message || 'Could not connect to the live interview room.'}</p>
                    <button class="btn btn-primary" onclick="router.navigate('candidates')">Back to Screening Queue</button>
                </div>
            `;
        }
    },

    // --------------------------------------------------------------------------
    // Phase 8: Observable Integrity Signal Emitter & Listeners
    // --------------------------------------------------------------------------
    sendIntegrityEvent(eventType, metadata = {}) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: "integrity_event",
                event_type: eventType,
                occurred_at: new Date().toISOString(),
                metadata: metadata,
            }));
        }
    },

    setupIntegrityListeners() {
        this.removeIntegrityListeners();

        // 1. Tab Visibility Change Listener
        this.visibilityListener = () => {
            if (document.hidden) {
                if (this.lastVisibilityState !== "hidden") {
                    this.lastVisibilityState = "hidden";
                    this.sendIntegrityEvent("TAB_HIDDEN", { state: "hidden" });
                }
            } else {
                if (this.lastVisibilityState !== "visible") {
                    this.lastVisibilityState = "visible";
                    this.sendIntegrityEvent("TAB_VISIBLE", { state: "visible" });
                }
            }
        };
        document.addEventListener("visibilitychange", this.visibilityListener);

        // 2. Fullscreen Change Listener
        this.fullscreenListener = () => {
            const isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement);
            if (isFullscreen && !this.lastFullscreenState) {
                this.lastFullscreenState = true;
                this.sendIntegrityEvent("FULLSCREEN_ENTER", {});
            } else if (!isFullscreen && this.lastFullscreenState) {
                this.lastFullscreenState = false;
                this.sendIntegrityEvent("FULLSCREEN_EXIT", {});
            }
        };
        document.addEventListener("fullscreenchange", this.fullscreenListener);
        document.addEventListener("webkitfullscreenchange", this.fullscreenListener);
    },

    removeIntegrityListeners() {
        if (this.visibilityListener) {
            document.removeEventListener("visibilitychange", this.visibilityListener);
            this.visibilityListener = null;
        }
        if (this.fullscreenListener) {
            document.removeEventListener("fullscreenchange", this.fullscreenListener);
            document.removeEventListener("webkitfullscreenchange", this.fullscreenListener);
            this.fullscreenListener = null;
        }
    },

    toggleFullscreen() {
        if (!document.fullscreenElement && !document.webkitFullscreenElement) {
            if (document.documentElement.requestFullscreen) {
                document.documentElement.requestFullscreen().catch(e => console.warn("Fullscreen request notice:", e));
            } else if (document.documentElement.webkitRequestFullscreen) {
                document.documentElement.webkitRequestFullscreen();
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen().catch(e => console.warn("Exit fullscreen notice:", e));
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            }
        }
    },

    // --------------------------------------------------------------------------
    // Camera & Microphone Hardware Management
    // --------------------------------------------------------------------------
    async initMediaDevices() {
        const videoEl = document.getElementById("candidate-live-video");
        const placeholderEl = document.getElementById("candidate-video-placeholder");
        const alertEl = document.getElementById("device-perm-alert");
        const camBadge = document.getElementById("camera-status-badge");
        const micBadge = document.getElementById("mic-status-badge");

        if (alertEl) alertEl.style.display = "none";

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.warn("navigator.mediaDevices.getUserMedia is not supported in this environment");
            if (camBadge) {
                camBadge.className = "badge badge-warning";
                camBadge.textContent = "📷 CAMERA: UNAVAILABLE";
            }
            if (micBadge) {
                micBadge.className = "badge badge-warning";
                micBadge.textContent = "🎤 MIC: UNAVAILABLE";
            }
            if (placeholderEl) placeholderEl.style.display = "flex";
            return;
        }

        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 } },
                audio: true,
            });

            if (videoEl) {
                videoEl.srcObject = this.mediaStream;
                videoEl.onloadedmetadata = () => {
                    videoEl.play().catch(e => console.warn("Video autoplay notice:", e));
                };
            }

            this.cameraActive = true;
            this.micActive = true;

            // Track end event listeners
            const videoTracks = this.mediaStream.getVideoTracks();
            if (videoTracks.length > 0) {
                videoTracks[0].onended = () => {
                    this.cameraActive = false;
                    this.sendIntegrityEvent("CAMERA_DISCONNECTED", { reason: "track_ended" });
                    if (camBadge) {
                        camBadge.className = "badge badge-warning";
                        camBadge.textContent = "📷 CAMERA: DISCONNECTED";
                    }
                };
            }

            const audioTracks = this.mediaStream.getAudioTracks();
            if (audioTracks.length > 0) {
                audioTracks[0].onended = () => {
                    this.micActive = false;
                    this.sendIntegrityEvent("MICROPHONE_DISCONNECTED", { reason: "track_ended" });
                    if (micBadge) {
                        micBadge.className = "badge badge-warning";
                        micBadge.textContent = "🎤 MIC: DISCONNECTED";
                    }
                };
            }

            if (camBadge) {
                camBadge.className = "badge badge-success";
                camBadge.textContent = "📷 CAMERA: LIVE";
            }
            if (micBadge) {
                micBadge.className = "badge badge-success";
                micBadge.textContent = "🎤 MIC: ACTIVE";
            }
            if (placeholderEl) placeholderEl.style.display = "none";

            // Emit observable integrity signals
            this.sendIntegrityEvent("CAMERA_CONNECTED");
            this.sendIntegrityEvent("MICROPHONE_CONNECTED");

            this.setupAudioRecording(this.mediaStream);

        } catch (err) {
            console.warn("Media devices permission or hardware warning:", err);
            if (alertEl) alertEl.style.display = "flex";
            if (placeholderEl) placeholderEl.style.display = "flex";

            if (camBadge) {
                camBadge.className = "badge badge-warning";
                camBadge.textContent = "📷 CAMERA: OFF";
            }
            if (micBadge) {
                micBadge.className = "badge badge-warning";
                micBadge.textContent = "🎤 MIC: OFF";
            }
        }
    },

    toggleCamera() {
        const videoEl = document.getElementById("candidate-live-video");
        const placeholderEl = document.getElementById("candidate-video-placeholder");
        const camBadge = document.getElementById("camera-status-badge");
        const btn = document.getElementById("btn-toggle-camera");

        if (!this.mediaStream) {
            this.initMediaDevices();
            return;
        }

        const videoTracks = this.mediaStream.getVideoTracks();
        if (videoTracks.length === 0) return;

        this.cameraActive = !this.cameraActive;
        videoTracks[0].enabled = this.cameraActive;

        if (this.cameraActive) {
            if (camBadge) {
                camBadge.className = "badge badge-success";
                camBadge.textContent = "📷 CAMERA: LIVE";
            }
            if (btn) btn.textContent = "📷 Turn Camera Off";
            if (placeholderEl) placeholderEl.style.display = "none";
            this.sendIntegrityEvent("CAMERA_CONNECTED");
        } else {
            if (camBadge) {
                camBadge.className = "badge badge-warning";
                camBadge.textContent = "📷 CAMERA: DISABLED";
            }
            if (btn) btn.textContent = "📷 Turn Camera On";
            if (placeholderEl) placeholderEl.style.display = "flex";
            this.sendIntegrityEvent("CAMERA_DISCONNECTED");
        }
    },

    toggleMic() {
        const micBadge = document.getElementById("mic-status-badge");
        const btn = document.getElementById("btn-toggle-mic");

        if (!this.mediaStream) {
            this.initMediaDevices();
            return;
        }

        const audioTracks = this.mediaStream.getAudioTracks();
        if (audioTracks.length === 0) return;

        this.micActive = !this.micActive;
        audioTracks[0].enabled = this.micActive;

        if (this.micActive) {
            if (micBadge) {
                micBadge.className = "badge badge-success";
                micBadge.textContent = "🎤 MIC: ACTIVE";
            }
            if (btn) btn.textContent = "🎤 Mute Mic";
            this.sendIntegrityEvent("MICROPHONE_CONNECTED");
        } else {
            if (micBadge) {
                micBadge.className = "badge badge-warning";
                micBadge.textContent = "🔇 MIC: MUTED";
            }
            if (btn) btn.textContent = "🎤 Unmute Mic";
            this.sendIntegrityEvent("MICROPHONE_DISCONNECTED");
        }
    },

    setupAudioRecording(stream) {
        if (!window.MediaRecorder) return;

        try {
            this.mediaRecorder = new MediaRecorder(stream);
            this.recordedAudioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this.recordedAudioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = async () => {
                if (this.recordedAudioChunks.length === 0) return;
                const audioBlob = new Blob(this.recordedAudioChunks, { type: "audio/webm" });
                this.recordedAudioChunks = [];

                // Convert blob to base64 and send over WebSocket
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64Data = reader.result.split(",")[1];
                    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                        this.updateAvatarState("LISTENING");
                        this.websocket.send(JSON.stringify({
                            type: "candidate_audio",
                            audio: base64Data,
                            content_type: "audio/webm",
                        }));
                    }
                };
                reader.readAsDataURL(audioBlob);
            };
        } catch (e) {
            console.warn("MediaRecorder setup notice:", e);
        }
    },

    // --------------------------------------------------------------------------
    // Real-Time WebSocket Connection & State Reflection
    // --------------------------------------------------------------------------
    connectWebSocket(sessionId) {
        if (this.websocket) {
            try { this.websocket.close(); } catch (e) {}
            this.websocket = null;
        }

        const wsStatusBadge = document.getElementById("ws-status-badge");
        const btnReconnect = document.getElementById("btn-reconnect-ws");

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const token = api.getToken();
        const wsUrl = `${protocol}//${window.location.host}/api/v1/interviews/${sessionId}/ws?token=${token}`;

        if (wsStatusBadge) {
            wsStatusBadge.textContent = "🟡 WS: CONNECTING...";
            wsStatusBadge.style.color = "#FBBF24";
        }

        try {
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                if (wsStatusBadge) {
                    wsStatusBadge.textContent = "🟢 WS: LIVE";
                    wsStatusBadge.style.color = "#34D399";
                    wsStatusBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
                }
                if (btnReconnect) btnReconnect.style.display = "none";
                this.updateAvatarState("IDLE");

                if (this.hasConnectedOnce) {
                    this.sendIntegrityEvent("CONNECTION_RESTORED", { reconnect: true });
                } else {
                    this.hasConnectedOnce = true;
                }
            };

            this.websocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketEvent(data);
                } catch (e) {
                    console.error("Failed to parse WebSocket message:", event.data);
                }
            };

            this.websocket.onclose = (event) => {
                if (wsStatusBadge) {
                    wsStatusBadge.textContent = "🔴 WS: DISCONNECTED";
                    wsStatusBadge.style.color = "#F87171";
                    wsStatusBadge.style.borderColor = "rgba(239, 68, 68, 0.4)";
                }
                if (btnReconnect) btnReconnect.style.display = "inline-flex";
            };

            this.websocket.onerror = (error) => {
                console.warn("WebSocket error:", error);
                this.updateAvatarState("ERROR");
            };

        } catch (e) {
            console.error("WebSocket connection creation error:", e);
            if (wsStatusBadge) {
                wsStatusBadge.textContent = "🔴 WS: ERROR";
                wsStatusBadge.style.color = "#F87171";
            }
            if (btnReconnect) btnReconnect.style.display = "inline-flex";
        }
    },

    handleWebSocketEvent(data) {
        const type = data.type;

        // 1. Avatar State Transition Event
        if (type === "avatar_state" && data.state) {
            this.updateAvatarState(data.state);
        }

        // 2. Integrity Event Acknowledgement
        else if (type === "integrity_event_recorded") {
            // Acknowledged without intrusive UI interruption
            console.debug(`Integrity signal acknowledged: ${data.event_type}`);
        }

        // 3. AI Question / Message Response
        else if (type === "ai_message" || (data.role === "AI" || data.role === "assistant")) {
            const content = data.content || data.question || "";
            if (content) {
                this.appendMessageToChat("AI", content);
            }
            const typingIndicator = document.getElementById("ai-typing-indicator");
            if (typingIndicator) typingIndicator.style.display = "none";
        }

        // 4. Candidate Transcript Echo
        else if (type === "transcript" && data.content) {
            this.appendMessageToChat(data.role === "candidate" ? "CANDIDATE" : "SYSTEM", data.content);
        }

        // 5. Synthesized AI Audio
        else if (type === "ai_audio" && data.audio) {
            try {
                const audio = new Audio(`data:${data.content_type || 'audio/mpeg'};base64,${data.audio}`);
                audio.play().catch(e => console.warn("Audio playback notice:", e));
            } catch (e) {
                console.warn("Audio element error:", e);
            }
        }

        // 6. System Events
        else if (type === "system") {
            if (data.event === "error") {
                this.updateAvatarState("ERROR");
                toast.error(data.content || "System notice in live interview session.");
            } else if (data.event === "rate_limit_exceeded") {
                toast.warning("Message limit reached. Please wait a moment.");
            }
        }
    },

    // --------------------------------------------------------------------------
    // AI Avatar Presentation State Machine
    // --------------------------------------------------------------------------
    updateAvatarState(state) {
        this.currentAvatarState = state;
        const badge = document.getElementById("avatar-state-badge");
        const orb = document.getElementById("avatar-orb");
        const orbIcon = document.getElementById("avatar-orb-icon");
        const stateText = document.getElementById("avatar-state-text");
        const waveContainer = document.getElementById("avatar-wave-container");

        if (!badge || !orb) return;

        switch (state) {
            case "LISTENING":
                badge.className = "badge badge-success";
                badge.textContent = "LISTENING (ACTIVE)";
                orb.style.background = "linear-gradient(135deg, #10B981 0%, #059669 100%)";
                orb.style.boxShadow = "0 0 35px rgba(16, 185, 129, 0.6)";
                if (orbIcon) orbIcon.textContent = "👂";
                if (stateText) {
                    stateText.textContent = "AI is listening to your response...";
                    stateText.style.color = "#34D399";
                }
                if (waveContainer) waveContainer.style.display = "flex";
                break;

            case "THINKING":
                badge.className = "badge badge-warning";
                badge.textContent = "THINKING (ANALYZING)";
                orb.style.background = "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)";
                orb.style.boxShadow = "0 0 35px rgba(245, 158, 11, 0.6)";
                if (orbIcon) orbIcon.textContent = "⚡";
                if (stateText) {
                    stateText.textContent = "Analyzing response and formulating follow-up...";
                    stateText.style.color = "#FBBF24";
                }
                if (waveContainer) waveContainer.style.display = "none";
                break;

            case "SPEAKING":
                badge.className = "badge badge-info";
                badge.textContent = "SPEAKING (AI AUDIO)";
                orb.style.background = "linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%)";
                orb.style.boxShadow = "0 0 35px rgba(139, 92, 246, 0.6)";
                if (orbIcon) orbIcon.textContent = "🎙️";
                if (stateText) {
                    stateText.textContent = "AI interviewer is speaking...";
                    stateText.style.color = "#A78BFA";
                }
                if (waveContainer) waveContainer.style.display = "flex";
                break;

            case "ERROR":
                badge.className = "badge badge-danger";
                badge.textContent = "CONNECTION ISSUE";
                orb.style.background = "linear-gradient(135deg, #EF4444 0%, #DC2626 100%)";
                orb.style.boxShadow = "0 0 30px rgba(239, 68, 68, 0.6)";
                if (orbIcon) orbIcon.textContent = "⚠️";
                if (stateText) {
                    stateText.textContent = "Temporary connection interruption.";
                    stateText.style.color = "#F87171";
                }
                if (waveContainer) waveContainer.style.display = "none";
                break;

            case "IDLE":
            default:
                badge.className = "badge badge-info";
                badge.textContent = "IDLE (READY)";
                orb.style.background = "linear-gradient(135deg, #3B82F6 0%, #6366F1 100%)";
                orb.style.boxShadow = "0 0 25px rgba(59, 130, 246, 0.4)";
                if (orbIcon) orbIcon.textContent = "🧠";
                if (stateText) {
                    stateText.textContent = "AI is ready for candidate response";
                    stateText.style.color = "var(--primary-light)";
                }
                if (waveContainer) waveContainer.style.display = "none";
                break;
        }
    },

    // --------------------------------------------------------------------------
    // UI Transcript & Input Handlers
    // --------------------------------------------------------------------------
    renderTranscriptHistory(messages) {
        if (!messages || messages.length === 0) {
            return `
                <div style="background: rgba(59, 130, 246, 0.1); border-left: 3px solid var(--primary); padding: 1rem; border-radius: var(--radius-sm); color: #E2E8F0;">
                    <div style="font-size: 0.75rem; color: var(--primary-light); font-weight: 700; margin-bottom: 0.35rem; font-family: var(--font-mono);">
                        AI INTERVIEWER (GAP2HIRE)
                    </div>
                    <div style="font-size: 0.9rem; line-height: 1.5;">
                        Welcome to your technical verification interview! Please ensure your camera and microphone are connected. When ready, explain your technical experience or submit your first answer below.
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
                <div style="background: ${bgCol}; border-left: 3px solid ${borderCol}; padding: 0.85rem 1rem; border-radius: var(--radius-sm); color: #E2E8F0; margin-left: ${isAi ? '0' : '2rem'}; margin-right: ${isAi ? '2rem' : '0'};">
                    <div style="font-size: 0.72rem; color: ${textColor}; font-weight: 700; margin-bottom: 0.3rem; font-family: var(--font-mono);">
                        ${roleLabel}
                    </div>
                    <div style="font-size: 0.88rem; line-height: 1.45;">
                        ${m.content}
                    </div>
                </div>
            `;
        }).join("");
    },

    appendMessageToChat(role, content) {
        const chatBox = document.getElementById("live-chat-box");
        if (!chatBox) return;

        const isAi = role === "AI" || role === "SYSTEM";
        const roleLabel = role === "AI" ? "AI INTERVIEWER (GAP2HIRE)" : (role === "SYSTEM" ? "SYSTEM" : "CANDIDATE");
        const borderCol = role === "AI" ? "var(--primary)" : (role === "SYSTEM" ? "var(--text-muted)" : "var(--accent-emerald)");
        const bgCol = role === "AI" ? "rgba(59, 130, 246, 0.1)" : (role === "SYSTEM" ? "rgba(255,255,255,0.02)" : "rgba(16, 185, 129, 0.1)");
        const textColor = role === "AI" ? "var(--primary-light)" : (role === "SYSTEM" ? "var(--text-muted)" : "#34D399");

        const msgDiv = document.createElement("div");
        msgDiv.style.cssText = `background: ${bgCol}; border-left: 3px solid ${borderCol}; padding: 0.85rem 1rem; border-radius: var(--radius-sm); color: #E2E8F0; margin-left: ${isAi ? '0' : '2rem'}; margin-right: ${isAi ? '2rem' : '0'};`;
        msgDiv.innerHTML = `
            <div style="font-size: 0.72rem; color: ${textColor}; font-weight: 700; margin-bottom: 0.3rem; font-family: var(--font-mono);">${roleLabel}</div>
            <div style="font-size: 0.88rem; line-height: 1.45;">${content}</div>
        `;

        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    },

    attachInputHandlers(container, sessionId) {
        const btnSend = container.querySelector("#btn-send-message");
        const inputMsg = container.querySelector("#candidate-live-input");
        const btnVoice = container.querySelector("#btn-voice-talk");
        const typingIndicator = container.querySelector("#ai-typing-indicator");

        const sendMessage = () => {
            const text = inputMsg.value.trim();
            if (!text) return;

            this.appendMessageToChat("CANDIDATE", text);
            inputMsg.value = "";

            if (typingIndicator) typingIndicator.style.display = "inline";

            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.updateAvatarState("THINKING");
                this.websocket.send(JSON.stringify({
                    type: "candidate_message",
                    content: text,
                }));
            } else {
                // Fallback to HTTP answer endpoint if WebSocket is not open
                api.post(`/interviews/${sessionId}/answers`, { answer_text: text })
                    .then(res => {
                        if (typingIndicator) typingIndicator.style.display = "none";
                        if (res.ai_response) {
                            this.appendMessageToChat("AI", res.ai_response);
                        }
                    })
                    .catch(() => {
                        if (typingIndicator) typingIndicator.style.display = "none";
                    });
            }
        };

        if (btnSend) btnSend.addEventListener("click", sendMessage);
        if (inputMsg) {
            inputMsg.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }

        // Push to talk handler
        if (btnVoice) {
            btnVoice.addEventListener("mousedown", () => {
                if (this.mediaRecorder && this.mediaRecorder.state === "inactive") {
                    this.recordedAudioChunks = [];
                    this.mediaRecorder.start();
                    this.isRecordingAudio = true;
                    btnVoice.textContent = "🔴 Recording... Release to Send";
                    btnVoice.style.background = "#EF4444";
                    this.updateAvatarState("LISTENING");
                }
            });

            btnVoice.addEventListener("mouseup", () => {
                if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
                    this.mediaRecorder.stop();
                    this.isRecordingAudio = false;
                    btnVoice.textContent = "🎙️ Speak Answer (PTT)";
                    btnVoice.style.background = "linear-gradient(135deg, #10B981 0%, #059669 100%)";
                    this.updateAvatarState("THINKING");
                }
            });
        }
    },

    cleanup() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }

        if (this.websocket) {
            try { this.websocket.close(); } catch (e) {}
            this.websocket = null;
        }

        if (this.mediaStream) {
            try {
                this.mediaStream.getTracks().forEach(t => t.stop());
            } catch (e) {}
            this.mediaStream = null;
        }

        this.removeIntegrityListeners();

        this.mediaRecorder = null;
        this.recordedAudioChunks = [];
        this.isRecordingAudio = false;
        this.lastVisibilityState = null;
        this.lastFullscreenState = false;
    }
};

window.interviewLiveView = interviewLiveView;
window.InterviewLiveView = interviewLiveView;
