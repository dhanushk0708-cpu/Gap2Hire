// ==========================================================================
// Gap2Hire Unified API Client
// ==========================================================================

const api = {
  baseUrl: "/api/v1",

  getToken() {
    return localStorage.getItem("gap2hire_token") || "";
  },

  setToken(token) {
    if (token) {
      localStorage.setItem("gap2hire_token", token);
    } else {
      localStorage.removeItem("gap2hire_token");
    }
  },

  getHeaders() {
    const headers = {
      "Content-Type": "application/json",
    };
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  },

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith("http") ? endpoint : `${this.baseUrl}${endpoint}`;
    const headers = { ...this.getHeaders(), ...(options.headers || {}) };
    if (options.body instanceof FormData) {
      delete headers["Content-Type"];
    }
    
    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (response.status === 401) {
        // Token expired or invalid
        this.setToken("");
        window.location.hash = "#auth";
        throw new Error("Session expired. Please log in again.");
      }

      if (response.status === 204) {
        return null;
      }

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        const errorMsg = (data && (data.detail || data.message)) || `Request failed with status ${response.status}`;
        throw new Error(typeof errorMsg === "string" ? errorMsg : JSON.stringify(errorMsg));
      }

      return data;
    } catch (err) {
      console.error(`API Error [${options.method || "GET"} ${endpoint}]:`, err);
      throw err;
    }
  },

  // HTTP Helpers
  get(endpoint) {
    return this.request(endpoint, { method: "GET" });
  },

  post(endpoint, body) {
    return this.request(endpoint, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  postForm(endpoint, formData) {
    return this.request(endpoint, {
      method: "POST",
      body: formData,
    });
  },

  patch(endpoint, body) {
    return this.request(endpoint, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  delete(endpoint) {
    return this.request(endpoint, { method: "DELETE" });
  },

  // Auth APIs
  auth: {
    login(email, password) {
      return api.post("/auth/login", { email, password });
    },
    register(fullName, organizationName, email, password) {
      return api.post("/auth/register", {
        full_name: fullName,
        organization_name: organizationName,
        email,
        password,
      });
    },
    getMe() {
      return api.get("/auth/me");
    },
  },

  // Jobs APIs
  jobs: {
    list() {
      return api.get("/jobs");
    },
    get(jobId) {
      return api.get(`/jobs/${jobId}`);
    },
    create(title, description, shortlistSize = 5) {
      return api.post("/jobs", { title, description, shortlist_size: shortlistSize });
    },
    update(jobId, data) {
      return api.patch(`/jobs/${jobId}`, data);
    },
    publish(jobId) {
      return api.patch(`/jobs/${jobId}`, { status: "ACTIVE" });
    },
    analyzeJD(jobId) {
      return api.post(`/jobs/${jobId}/analyze`);
    },
  },

  // Capabilities Blueprint APIs
  capabilities: {
    list(jobId) {
      return api.get(`/jobs/${jobId}/capabilities`);
    },
    create(jobId, data) {
      return api.post(`/jobs/${jobId}/capabilities`, data);
    },
    batchCreate(jobId, capabilitiesList) {
      return api.post(`/jobs/${jobId}/capabilities/batch`, { capabilities: capabilitiesList });
    },
    delete(capabilityId) {
      return api.delete(`/capabilities/${capabilityId}`);
    },
  },

  // Email & Resumes Ingestion APIs
  email: {
    loadNewResumes(limit = 10, targetJobId = null) {
      let query = `?limit=${limit}`;
      if (targetJobId) query += `&target_job_id=${targetJobId}`;
      return api.post(`/email/sync${query}`);
    },
    listConnections() {
      return api.get("/email-connections");
    },
  },

  // Candidate Screening & Shortlisting APIs
  screening: {
    listJobCandidates(jobId) {
      return api.get(`/jobs/${jobId}/candidates`);
    },
    getScreeningReport(applicationId) {
      return api.get(`/applications/${applicationId}/screening`);
    },
    getScreeningProfile(applicationId) {
      return api.get(`/applications/${applicationId}/screening-profile`);
    },
    runScreening(applicationId) {
      return api.post(`/applications/${applicationId}/run-screening`);
    },
    runJobScreening(jobId) {
      return api.post(`/jobs/${jobId}/screening/run`);
    },
    getJobTopN(jobId) {
      return api.get(`/jobs/${jobId}/screening/top-n`);
    },
    updateShortlistSize(jobId, shortlistSize) {
      return api.put(`/jobs/${jobId}/shortlist-size`, { shortlist_size: shortlistSize });
    },
    shortlistCandidate(applicationId, decision, reason = "") {
      return api.patch(`/applications/${applicationId}/shortlist`, {
        decision,
        reason,
      });
    },
  },

  // Demo Ingestion APIs
  demo: {
    importResumes(jobId, file) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("job_id", jobId);
      return api.postForm("/demo/import-resumes", formData);
    },
  },

  // Interview Setup & Rounds APIs
  interviewSetup: {
    listRounds(jobId) {
      return api.get(`/jobs/${jobId}/interview-rounds`);
    },
    createRound(jobId, roundData) {
      return api.post(`/jobs/${jobId}/interview-rounds`, roundData);
    },
    listQuestionTemplates(roundId) {
      return api.get(`/interview-rounds/${roundId}/question-templates`);
    },
    createQuestionTemplate(roundId, templateData) {
      return api.post(`/interview-rounds/${roundId}/question-templates`, templateData);
    },
    suggestQuestions(jobId) {
      return api.post(`/jobs/${jobId}/suggest-questions`);
    },
  },

  // Interviews & Live Observer APIs
  interviews: {
    listSessions(applicationId) {
      return api.get(`/applications/${applicationId}/interviews`);
    },
    createSession(applicationId) {
      return api.post(`/applications/${applicationId}/interviews`);
    },
    startSession(sessionId) {
      return api.patch(`/interviews/${sessionId}/start`);
    },
    getHrLiveSnapshot(sessionId) {
      return api.get(`/interviews/${sessionId}/hr-live`);
    },
    getReport(sessionId) {
      return api.get(`/interviews/${sessionId}/report`);
    },
    generateNextQuestion(sessionId) {
      return api.post(`/interviews/${sessionId}/questions`);
    },
    submitAnswer(sessionId, questionId, answerText) {
      return api.post(`/interviews/${sessionId}/answers`, {
        question_id: questionId,
        answer_text: answerText,
      });
    },
    applyFinalDecision(applicationId, status, notes = "") {
      return api.patch(`/applications/${applicationId}`, {
        status,
      });
    },
  },

  // Global compatibility aliases
  getApplicationDetail(id) {
    return api.get(`/applications/${id}`);
  },
  getJob(id) {
    return api.jobs.get(id);
  },
  getInterviewRounds(jobId) {
    return api.interviewSetup.listRounds(jobId);
  },
  getJobCapabilities(jobId) {
    return api.capabilities.list(jobId);
  },
  generateAIQuestions(jobId) {
    return api.interviewSetup.suggestQuestions(jobId);
  },
  getInterviewReport(sessionId) {
    return api.interviews.getReport(sessionId);
  },
  getHRLiveObservation(sessionId) {
    return api.interviews.getHrLiveSnapshot(sessionId);
  },
  async startInterviewSession(applicationId) {
    const s = await api.interviews.createSession(applicationId);
    await api.interviews.startSession(s.id).catch(() => {});
    return s;
  },
};

window.api = api;
window.ApiClient = api;


