import { apiClient } from './client';
import type {
  User,
  Job,
  Capability,
  JDAnalysisResponse,
  Application,
  Candidate,
  ApplicationEvidenceSummary,
  JobCandidateListItem,
  JobTopNResult,
  CandidateScreeningResult,
  CandidateScreeningProfile,
  CandidateInterviewPreAnalysis,
  InterviewPlan,
  InterviewPlanRound,
  InterviewPlanQuestion,
  RoundQuestionGeneratePreviewRequest,
  InterviewDatasetFile,
  InterviewScheduleResponse,
  InterviewReport,
  HiringDecisionResponse,
  HiringDecisionHistoryResponse,
  DecisionReplayResponse,
  PostHireOutcomeResponse,
  PostHireOutcomeListResponse,
  HiringAutopsyResponse,
  DemoImportResult,
  EmailConnectionResponse,
  BatchEmailSyncResponse,
  HiringDecisionType,
  OutcomeStatus,
  PreInterviewScorecard,
  PostInterviewScorecard,
  HiringIntelligenceResponse,
  HiringChatRequest,
  HiringChatResponse,
  IndexSyncResponse,
  InterviewerItem,
  SimulatedNotificationItem,
  BookingSlotItem,
  CandidateBookingView,
} from '../types';

export const authApi = {
  login: (data: { email: string; password: string }) =>
    apiClient<{ access_token: string; token_type: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  register: (data: {
    email: string;
    password: string;
    full_name: string;
    organization_name: string;
  }) =>
    apiClient<{ access_token: string; token_type: string }>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getMe: () => apiClient<User>('/api/v1/auth/me'),
};

export const jobsApi = {
  list: () => apiClient<Job[]>('/api/v1/jobs'),

  get: (jobId: string) => apiClient<Job>(`/api/v1/jobs/${jobId}`),

  create: (data: { title: string; description: string; shortlist_size?: number }) =>
    apiClient<Job>('/api/v1/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (jobId: string, data: Partial<Job>) =>
    apiClient<Job>(`/api/v1/jobs/${jobId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  analyzeJD: (jobId: string) =>
    apiClient<JDAnalysisResponse>(`/api/v1/jobs/${jobId}/analyze`, {
      method: 'POST',
    }),

  getCapabilities: (jobId: string) =>
    apiClient<Capability[]>(`/api/v1/jobs/${jobId}/capabilities`),

  addCapability: (
    jobId: string,
    data: { name: string; description?: string; importance?: string }
  ) =>
    apiClient<Capability>(`/api/v1/jobs/${jobId}/capabilities`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  addCapabilitiesBatch: (
    jobId: string,
    capabilities: Array<{ name: string; description?: string; importance?: string }>
  ) =>
    apiClient<Capability[]>(`/api/v1/jobs/${jobId}/capabilities/batch`, {
      method: 'POST',
      body: JSON.stringify({ capabilities }),
    }),

  updateCapability: (
    capabilityId: string,
    data: { name?: string; description?: string; importance?: string }
  ) =>
    apiClient<Capability>(`/api/v1/capabilities/${capabilityId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteCapability: (capabilityId: string) =>
    apiClient<void>(`/api/v1/capabilities/${capabilityId}`, {
      method: 'DELETE',
    }),

  updateShortlistSize: (jobId: string, shortlist_size: number) =>
    apiClient<Job>(`/api/v1/jobs/${jobId}/shortlist-size`, {
      method: 'PUT',
      body: JSON.stringify({ shortlist_size }),
    }),
};

export const screeningApi = {
  getJobCandidates: (jobId: string) =>
    apiClient<JobCandidateListItem[]>(`/api/v1/jobs/${jobId}/candidates`),

  getJobScreeningQueue: (jobId: string) =>
    apiClient<JobCandidateListItem[]>(`/api/v1/jobs/${jobId}/screening-queue`),

  runJobScreening: (jobId: string) =>
    apiClient<JobTopNResult>(`/api/v1/jobs/${jobId}/screening/run`, {
      method: 'POST',
    }),

  getJobTopN: (jobId: string) =>
    apiClient<JobTopNResult>(`/api/v1/jobs/${jobId}/screening/top-n`),

  runCandidateScreening: (applicationId: string) =>
    apiClient<CandidateScreeningResult>(
      `/api/v1/applications/${applicationId}/run-screening`,
      { method: 'POST' }
    ),

  getCandidateScreening: (applicationId: string) =>
    apiClient<CandidateScreeningResult>(`/api/v1/applications/${applicationId}/screening`),

  getCandidateScreeningProfile: (applicationId: string) =>
    apiClient<CandidateScreeningProfile>(
      `/api/v1/applications/${applicationId}/screening-profile`
    ),

  shortlistCandidate: (
    applicationId: string,
    decision: 'SHORTLISTED' | 'NOT_SHORTLISTED' | 'HOLD',
    reason?: string
  ) =>
    apiClient<{
      application_id: string;
      status: string;
      screening_status: string;
      shortlist_status: string;
      shortlist_reason?: string;
      is_interview_ready: boolean;
    }>(`/api/v1/applications/${applicationId}/shortlist`, {
      method: 'PATCH',
      body: JSON.stringify({ decision, reason }),
    }),
};

export const applicationsApi = {
  list: (jobId?: string) =>
    apiClient<Application[]>('/api/v1/applications', {
      params: { job_id: jobId },
    }),

  get: (applicationId: string) =>
    apiClient<Application>(`/api/v1/applications/${applicationId}`),

  getEvidence: (applicationId: string) =>
    apiClient<ApplicationEvidenceSummary>(
      `/api/v1/applications/${applicationId}/evidence`
    ),

  analyzeEvidence: (applicationId: string) =>
    apiClient<ApplicationEvidenceSummary>(
      `/api/v1/applications/${applicationId}/analyze-evidence`,
      { method: 'POST' }
    ),

  uploadResume: (applicationId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient<Application>(`/api/v1/applications/${applicationId}/resume`, {
      method: 'POST',
      body: formData,
    });
  },

  processResume: (applicationId: string) =>
    apiClient<Application>(`/api/v1/applications/${applicationId}/process-resume`, {
      method: 'POST',
    }),

  getPreInterviewAnalysis: (applicationId: string) =>
    apiClient<any>(`/api/v1/applications/${applicationId}/pre-interview-analysis`),

  getPreInterviewScorecard: (applicationId: string) =>
    apiClient<PreInterviewScorecard>(
      `/api/v1/applications/${applicationId}/pre-interview-scorecard`
    ),

  refreshPreInterviewScorecard: (applicationId: string) =>
    apiClient<PreInterviewScorecard>(
      `/api/v1/applications/${applicationId}/pre-interview-scorecard/refresh`,
      { method: 'POST' }
    ),

  getPostInterviewScorecard: (applicationId: string) =>
    apiClient<PostInterviewScorecard>(
      `/api/v1/applications/${applicationId}/post-interview-scorecard`
    ),

  refreshPostInterviewScorecard: (applicationId: string) =>
    apiClient<PostInterviewScorecard>(
      `/api/v1/applications/${applicationId}/post-interview-scorecard/refresh`,
      { method: 'POST' }
    ),

  getRichPreAnalysis: (applicationId: string) =>
    apiClient<CandidateInterviewPreAnalysis>(
      `/api/v1/applications/${applicationId}/interview/rich-pre-analysis`
    ),

  // Hiring Decision
  recordHiringDecision: (
    applicationId: string,
    data: { decision: HiringDecisionType; decision_reason: string }
  ) =>
    apiClient<HiringDecisionResponse>(
      `/api/v1/applications/${applicationId}/hiring-decision`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),

  getLatestHiringDecision: (applicationId: string) =>
    apiClient<HiringDecisionResponse>(
      `/api/v1/applications/${applicationId}/hiring-decision`
    ),

  getHiringDecisionHistory: (applicationId: string) =>
    apiClient<HiringDecisionHistoryResponse>(
      `/api/v1/applications/${applicationId}/hiring-decisions`
    ),

  // Decision Replay
  getDecisionReplay: (applicationId: string) =>
    apiClient<DecisionReplayResponse>(
      `/api/v1/applications/${applicationId}/decision-replay`
    ),

  // Post-Hire Outcomes
  recordPostHireOutcome: (
    applicationId: string,
    data: {
      capability_name: string;
      capability_id?: string | null;
      outcome_period?: string;
      expected_capability_description?: string;
      observed_outcome_description: string;
      outcome_status: OutcomeStatus;
      manager_notes?: string;
      evidence_reference?: string;
    }
  ) =>
    apiClient<PostHireOutcomeResponse>(
      `/api/v1/applications/${applicationId}/post-hire-outcomes`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),

  listPostHireOutcomes: (applicationId: string) =>
    apiClient<PostHireOutcomeListResponse>(
      `/api/v1/applications/${applicationId}/post-hire-outcomes`
    ),

  // Hiring Autopsy
  getHiringAutopsy: (applicationId: string) =>
    apiClient<HiringAutopsyResponse>(
      `/api/v1/applications/${applicationId}/hiring-autopsy`
    ),

  // Hiring Quality Intelligence (Feature 3)
  getHiringIntelligence: () =>
    apiClient<HiringIntelligenceResponse>('/api/v1/applications/hiring-intelligence'),
};

export const hiringIntelligenceApi = {
  get: () => apiClient<HiringIntelligenceResponse>('/api/v1/applications/hiring-intelligence'),
};

export const interviewDatasetsApi = {
  list: () => apiClient<InterviewDatasetFile[]>('/api/v1/interview-datasets'),

  get: (fileId: string) =>
    apiClient<InterviewDatasetFile>(`/api/v1/interview-datasets/${fileId}`),

  upload: (file: File, jobId?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (jobId) {
      formData.append('job_id', jobId);
    }
    return apiClient<{
      file_id: string;
      filename: string;
      total_questions: number;
      datasets: any[];
      warnings: string[];
    }>('/api/v1/interview-datasets/upload', {
      method: 'POST',
      body: formData,
    });
  },
};

export const interviewPlansApi = {
  list: (applicationId: string) =>
    apiClient<InterviewPlan[]>(
      `/api/v1/applications/${applicationId}/interview/plans`
    ),

  generate: (applicationId: string, datasetFileId?: string) =>
    apiClient<InterviewPlan>(
      `/api/v1/applications/${applicationId}/interview/plans`,
      {
        method: 'POST',
        body: JSON.stringify({ dataset_file_id: datasetFileId || null }),
      }
    ),

  get: (planId: string) =>
    apiClient<InterviewPlan>(`/api/v1/interview-plans/${planId}`),

  update: (
    planId: string,
    data: { rounds: InterviewPlanRound[]; hr_feedback?: string; lock_version?: number }
  ) =>
    apiClient<InterviewPlan>(`/api/v1/interview-plans/${planId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  previewQuestions: (
    applicationId: string,
    data: RoundQuestionGeneratePreviewRequest
  ) =>
    apiClient<InterviewPlanQuestion[]>(
      `/api/v1/applications/${applicationId}/interview/plans/preview-questions`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),

  approve: (planId: string, notes?: string) =>
    apiClient<InterviewPlan>(`/api/v1/interview-plans/${planId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    }),
};

export const interviewSessionsApi = {
  create: (applicationId: string) =>
    apiClient<any>(`/api/v1/applications/${applicationId}/interviews`, {
      method: 'POST',
    }),

  listByApplication: (applicationId: string) =>
    apiClient<any[]>(`/api/v1/applications/${applicationId}/interviews`),

  getRoomContext: (sessionId: string) =>
    apiClient<{
      session_id: string;
      status: string;
      candidate_name: string;
      job_title: string;
      round_number: number;
      avatar: any;
      transcript_messages: Array<{
        id: string;
        role: string;
        content: string;
        sequence_number: number;
        created_at: string | null;
      }>;
      ws_path: string;
    }>(`/api/v1/interviews/${sessionId}/room`),

  getHRObserverContext: (sessionId: string) =>
    apiClient<{
      session_id: string;
      candidate_name: string;
      candidate_email: string;
      job_title: string;
      status: string;
      round_number: number;
      current_question: string | null;
      candidate_answer: string | null;
      total_questions: number;
      transcript_messages: Array<{
        role: string;
        content: string;
        sequence: number;
        created_at: string | null;
      }>;
      graph_state: any;
      is_read_only: boolean;
      observer_user_id: string;
    }>(`/api/v1/interviews/${sessionId}/hr-live`),

  schedule: (
    sessionId: string,
    data: {
      scheduled_start: string;
      timezone?: string;
      duration_minutes?: number;
      invitation_notes?: string;
    }
  ) =>
    apiClient<InterviewScheduleResponse>(
      `/api/v1/interviews/${sessionId}/schedule`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),

  getSchedule: (sessionId: string) =>
    apiClient<InterviewScheduleResponse>(
      `/api/v1/interviews/${sessionId}/schedule`
    ),

  getReport: (sessionId: string) =>
    apiClient<InterviewReport>(`/api/v1/interviews/${sessionId}/report`),

  generateReport: (sessionId: string) =>
    apiClient<InterviewReport>(`/api/v1/interviews/${sessionId}/report`, {
      method: 'POST',
    }),

  retryReport: (sessionId: string) =>
    apiClient<InterviewReport>(`/api/v1/interviews/${sessionId}/report/retry`, {
      method: 'POST',
    }),

  start: (
    sessionId: string,
    data?: { duration_minutes?: number; media_verified?: boolean }
  ) =>
    apiClient<any>(`/api/v1/interviews/${sessionId}/start`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  complete: (sessionId: string, data?: { reason?: string }) =>
    apiClient<any>(`/api/v1/interviews/${sessionId}/complete`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  getExecutionState: (sessionId: string) =>
    apiClient<{
      session_id: string;
      interview_status: string;
      current_question_index: number;
      total_questions: number;
      duration_minutes?: number | null;
      deadline_at?: string | null;
      remaining_seconds?: number | null;
      completion_reason?: string | null;
      report_status?: string | null;
    }>(`/api/v1/interviews/${sessionId}/state`),

  getIntegrityEvents: (sessionId: string) =>
    apiClient<{
      session_id: string;
      total_events: number;
      events: Array<{
        id: string;
        interview_session_id: string;
        event_type: string;
        occurred_at: string;
        metadata_json?: any;
        created_at: string;
      }>;
    }>(`/api/v1/interviews/${sessionId}/integrity-events`),
};

export const demoApi = {
  importResumes: (file: File, jobId: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('job_id', jobId);
    return apiClient<DemoImportResult>('/api/v1/demo/import-resumes', {
      method: 'POST',
      body: formData,
    });
  },
};

export const emailApi = {
  listConnections: () =>
    apiClient<EmailConnectionResponse[]>('/api/v1/email-connections'),

  createConnection: (data: {
    provider?: string;
    account_email: string;
    status?: string;
  }) =>
    apiClient<EmailConnectionResponse>('/api/v1/email-connections', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  deleteConnection: (connectionId: string) =>
    apiClient<void>(`/api/v1/email-connections/${connectionId}`, {
      method: 'DELETE',
    }),

  getGoogleAuthUrl: (state?: string) =>
    apiClient<{ authorization_url: string }>('/api/v1/email-connections/oauth/google/url', {
      params: state ? { state } : undefined,
    }),

  sync: (limit = 10, targetJobId?: string) =>
    apiClient<BatchEmailSyncResponse>('/api/v1/email/sync', {
      method: 'POST',
      params: { limit, target_job_id: targetJobId },
    }),
};

export const hiringChatApi = {
  chat: (data: HiringChatRequest) =>
    apiClient<HiringChatResponse>('/api/v1/hiring-intelligence/chat', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  syncIndex: (params?: { job_id?: string; application_id?: string }) =>
    apiClient<IndexSyncResponse>('/api/v1/hiring-intelligence/sync-index', {
      method: 'POST',
      params,
    }),
};

export const interviewSchedulerApi = {
  list: (params?: {
    status?: string;
    candidate?: string;
    interviewer_id?: string;
    application_id?: string;
    date?: string;
  }) =>
    apiClient<InterviewScheduleResponse[]>('/api/v1/interviews/schedules', {
      params,
    }),

  get: (scheduleId: string) =>
    apiClient<InterviewScheduleResponse>(`/api/v1/interviews/schedules/${scheduleId}`),

  schedule: (data: {
    application_id: string;
    interviewer_id?: string;
    scheduled_start: string;
    timezone?: string;
    duration_minutes?: number;
    interview_type?: string;
    location?: string;
    invitation_notes?: string;
  }) =>
    apiClient<InterviewScheduleResponse>('/api/v1/interviews/schedules', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  reschedule: (
    scheduleId: string,
    data: {
      scheduled_start?: string;
      duration_minutes?: number;
      timezone?: string;
      interviewer_id?: string;
      interview_type?: string;
      location?: string;
      invitation_notes?: string;
      reschedule_reason?: string;
    }
  ) =>
    apiClient<InterviewScheduleResponse>(
      `/api/v1/interviews/schedules/${scheduleId}/reschedule`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),

  cancel: (scheduleId: string, reason: string) =>
    apiClient<InterviewScheduleResponse>(
      `/api/v1/interviews/schedules/${scheduleId}/cancel`,
      {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }
    ),

  complete: (scheduleId: string) =>
    apiClient<InterviewScheduleResponse>(
      `/api/v1/interviews/schedules/${scheduleId}/complete`,
      {
        method: 'POST',
      }
    ),

  getNotifications: (params?: { schedule_id?: string; interview_reference?: string }) =>
    apiClient<SimulatedNotificationItem[]>('/api/v1/interviews/notifications', {
      params,
    }),

  getInterviewers: () =>
    apiClient<InterviewerItem[]>('/api/v1/interviews/interviewers'),

  publishSlots: (
    applicationId: string,
    data: {
      interviewer_id: string;
      slots: Array<{ start_time: string; duration_minutes?: number }>;
      interview_type?: string;
      location?: string;
    }
  ) =>
    apiClient<{
      booking_token: string;
      booking_url: string;
      total_slots: number;
      slots: BookingSlotItem[];
    }>(`/api/v1/applications/${applicationId}/booking-slots`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

export const candidateBookingApi = {
  getView: (token: string) =>
    apiClient<CandidateBookingView>(`/api/v1/booking/${token}/slots`),

  book: (token: string, slotId: string) =>
    apiClient<InterviewScheduleResponse>(`/api/v1/booking/${token}/book`, {
      method: 'POST',
      body: JSON.stringify({ slot_id: slotId }),
    }),

  reschedule: (token: string, slotId: string, reason?: string) =>
    apiClient<InterviewScheduleResponse>(`/api/v1/booking/${token}/reschedule`, {
      method: 'POST',
      body: JSON.stringify({ slot_id: slotId, reason }),
    }),

  cancel: (token: string, reason?: string) =>
    apiClient<InterviewScheduleResponse>(`/api/v1/booking/${token}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
};
