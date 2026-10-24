export type UserRole =
  | 'COMPANY_ADMIN'
  | 'RECRUITER'
  | 'HIRING_MANAGER'
  | 'CANDIDATE'
  | 'PLATFORM_ADMIN';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  organization_id: string;
  is_active: boolean;
}

export type JobStatus = 'DRAFT' | 'ACTIVE' | 'PAUSED' | 'CLOSED' | 'ARCHIVED';

export interface Job {
  id: string;
  organization_id: string;
  title: string;
  description: string;
  status: JobStatus;
  shortlist_size: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export type CapabilityImportance = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export interface Capability {
  id: string;
  job_id: string;
  name: string;
  description: string | null;
  importance: CapabilityImportance;
  created_at: string;
  updated_at: string;
}

export interface JDAnalysisResponse {
  job_id: string;
  suggested_capabilities: Array<{
    name: string;
    description: string;
    importance: CapabilityImportance;
  }>;
}

export type ApplicationStatus =
  | 'RECEIVED'
  | 'SCREENING'
  | 'APPLIED'
  | 'IN_REVIEW'
  | 'VERIFICATION'
  | 'SHORTLISTED'
  | 'NOT_SHORTLISTED'
  | 'HOLD'
  | 'INTERVIEW'
  | 'INTERVIEW_COMPLETED'
  | 'HIRED'
  | 'REJECTED'
  | 'WITHDRAWN';

export interface Application {
  id: string;
  candidate_id: string;
  job_id: string;
  status: ApplicationStatus;
  shortlist_status?: string | null;
  shortlist_reason?: string | null;
  screening_status?: string | null;
  resume_path: string | null;
  resume_text?: string | null;
  applied_at: string;
  created_at: string;
  updated_at: string;
}

export interface Candidate {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  created_at: string;
  updated_at: string;
}

export type EvidenceState =
  | 'DEMONSTRATED'
  | 'CLAIM'
  | 'VERIFIED'
  | 'UNKNOWN'
  | 'INSUFFICIENT'
  | 'VERIFICATION_NEEDED';

export type EvidenceStrength = 'STRONG' | 'MODERATE' | 'WEAK' | 'INSUFFICIENT';

export type EvidenceProvenance =
  | 'CLAIM'
  | 'CORROBORATED'
  | 'VERIFIED'
  | 'DEMONSTRATED'
  | 'PERFORMANCE';

export interface CapabilityEvidenceSummary {
  capability_id: string;
  name: string;
  state: 'KNOWN' | 'UNKNOWN';
  strength: EvidenceStrength;
  provenance: EvidenceProvenance;
  evidence: string | null;
  candidate_source_id: string | null;
  source_id: string | null;
}

export interface ApplicationEvidenceSummary {
  application_id: string;
  capabilities: CapabilityEvidenceSummary[];
}

export interface RequirementEvaluation {
  requirement_name: string;
  requirement_type: string;
  status: string;
  evidence_found: string | null;
  provenance: string | null;
  strength: string | null;
  reason: string;
  source_type: string | null;
  source_url: string | null;
  verification_needed: boolean;
  verification_status: string;
  next_step: string;
}

export interface CandidateScreeningResult {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  job_id: string;
  job_title: string;
  eligibility_status: string;
  screening_status: string;
  shortlist_status: string;
  shortlist_reason: string | null;
  requirements_evaluated: RequirementEvaluation[];
  claims_summary: string[];
  unknowns_summary: string[];
  missing_information: string[];
  summary_explanation: string;
  verified_count: number;
  demonstrated_count: number;
  claims_count: number;
  unknown_count: number;
  insufficient_count: number;
  verification_needed_count: number;
  supported_count: number;
  total_requirements_count: number;
  evaluated_at: string;
}

export interface JobCandidateListItem {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  status: string;
  screening_status: string;
  shortlist_status: string;
  shortlist_reason: string | null;
  applied_at: string;
  has_resume: boolean;
  is_interview_ready: boolean;
  is_demo: boolean;
}

export interface TopNCandidateItem {
  rank: number;
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  shortlist_status: string;
  hard_requirements_met: number;
  total_hard_requirements: number;
  preferred_requirements_met: number;
  demonstrated_evidence_count: number;
  strong_evidence_count: number;
  unknown_count: number;
  summary_explanation: string;
  selection_reason: string;
}

export interface JobTopNResult {
  job_id: string;
  job_title: string;
  shortlist_size: number;
  total_candidates_evaluated: number;
  top_n_candidates: TopNCandidateItem[];
  cutoff_candidate: TopNCandidateItem | null;
  excluded_candidates: TopNCandidateItem[];
  selection_log: string[];
}

export interface CandidateScreeningProfile {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  job_id: string;
  job_title: string;
  screening_status: string;
  shortlist_status: string;
  rank: number | null;
  capability_results: Array<{
    capability_id: string;
    capability_name: string;
    importance: string;
    is_required: boolean;
    status: string;
    evidence_ids: string[];
    evidence_strength: string | null;
    provenance: string | null;
    content: string | null;
    source_url: string | null;
    source_type: string | null;
    unknown_reason: string | null;
    verification_needed: boolean;
  }>;
  hard_requirement_coverage: Record<string, any>;
  relevant_project_evidence: string[];
  relevant_resume_evidence: string[];
  unknown_capabilities: string[];
  insufficient_capabilities: string[];
  verification_needed: string[];
  summary_explanation: string;
  applied_at: string;
  evaluated_at: string;
}

export interface CandidateInterviewPreAnalysis {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  job_id: string;
  job_title: string;
  candidate_strengths: Array<Record<string, any>>;
  candidate_claims: Array<Record<string, any>>;
  candidate_unknowns: Array<Record<string, any>>;
  verification_targets: Array<Record<string, any>>;
  relevant_concepts: string[];
  recommended_focus: Array<Record<string, any>>;
  existing_evidence_references: Array<Record<string, any>>;
  grounded_summary: string;
  created_at: string;
}

export interface InterviewPlanQuestion {
  id?: string;
  dataset_question_id?: string | null;
  question_text: string;
  concept: string;
  difficulty: string;
  question_type: string;
  purpose?: string | null;
  evidence_being_verified?: string | null;
  is_hr_authored?: boolean;
  status?: string;
  sequence: number;
}

export interface InterviewPlanRound {
  id?: string;
  round_number: number;
  title: string;
  objective: string;
  description?: string | null;
  concepts: string[];
  evaluation_criteria?: string[];
  expected_evidence?: string[];
  question_generation_mode?: 'AI_GENERATED' | 'HR_DEFINED' | 'HYBRID';
  difficulty?: string;
  estimated_duration_minutes: number;
  required: boolean;
  reasoning?: string | null;
  sequence: number;
  questions: InterviewPlanQuestion[];
}

export interface InterviewPlan {
  id: string;
  application_id: string;
  job_id: string;
  dataset_file_id: string | null;
  version: number;
  lock_version?: number;
  status: 'DRAFT' | 'APPROVED' | 'SUPERSEDED' | 'REJECTED';
  candidate_strengths_summary: string | null;
  verification_targets_summary: string | null;
  hr_feedback: string | null;
  created_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  rounds: InterviewPlanRound[];
}

export interface RoundQuestionGeneratePreviewRequest {
  round_title: string;
  objective: string;
  description?: string | null;
  concepts: string[];
  evaluation_criteria?: string[];
  expected_evidence?: string[];
  difficulty?: string;
  duration_minutes?: number;
  question_generation_mode?: 'AI_GENERATED' | 'HR_DEFINED' | 'HYBRID';
  hr_questions?: InterviewPlanQuestion[];
  target_count?: number;
}

export interface DatasetQuestionItem {
  id: string;
  dataset_id: string;
  question_text: string;
  concept: string;
  difficulty: string;
  question_type: string;
  expected_topics?: string[] | null;
}

export interface QuestionDatasetItem {
  id: string;
  name: string;
  concept: string;
  description: string | null;
  question_count: number;
  questions: DatasetQuestionItem[];
}

export interface InterviewDatasetFile {
  id: string;
  filename: string;
  job_id: string | null;
  total_questions: number;
  dataset_count: number;
  datasets: QuestionDatasetItem[];
  created_at: string;
  updated_at: string;
}

export interface InterviewScheduleResponse {
  id: string;
  session_id: string;
  organization_id: string;
  application_id: string;
  interviewer_id?: string | null;
  interviewer_name?: string | null;
  scheduled_start: string;
  scheduled_end: string;
  timezone: string;
  duration_minutes: number;
  calendar_event_id: string | null;
  meeting_url: string | null;
  status: string;
  interview_type: string;
  interview_reference?: string | null;
  location?: string | null;
  cancellation_reason?: string | null;
  booking_token?: string | null;
  candidate_email_sent: boolean;
  candidate_email_id?: string | null;
  invitation_notes: string | null;
  candidate_id?: string | null;
  candidate_name: string | null;
  candidate_email: string | null;
  job_id?: string | null;
  job_title: string | null;
  created_at: string;
  updated_at?: string;
}

export interface InterviewerItem {
  id: string;
  full_name: string;
  email: string;
  role: string;
}

export interface SimulatedNotificationItem {
  id: string;
  organization_id: string;
  interview_schedule_id?: string | null;
  recipient: string;
  recipient_name?: string | null;
  subject: string;
  body: string;
  interview_reference: string;
  notification_type: string;
  delivery_mode: string;
  delivery_status: string;
  demo_banner: string;
  created_at: string;
}

export interface BookingSlotItem {
  id: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  interview_type: string;
  location?: string | null;
  is_booked: boolean;
  interviewer_name?: string | null;
}

export interface CandidateBookingView {
  booking_token: string;
  job_title: string;
  organization_name: string;
  candidate_name: string;
  interview_type: string;
  duration_minutes: number;
  slots: BookingSlotItem[];
  current_booking?: InterviewScheduleResponse | null;
}


export type AvatarState = 'IDLE' | 'LISTENING' | 'THINKING' | 'SPEAKING' | 'ERROR';

export interface InterviewMessage {
  id?: string;
  role: 'system' | 'ai' | 'candidate';
  content: string;
  sequence_number?: number;
  created_at?: string;
}

export interface IntegrityEvent {
  event_type: string;
  occurred_at: string;
  metadata?: Record<string, any>;
}

export interface InterviewReport {
  id?: string;
  session_id: string;
  application_id: string;
  candidate_name?: string | null;
  candidate_email?: string | null;
  job_id?: string | null;
  job_title?: string | null;
  status: string;
  report_status?: string | null;
  generated_at?: string | null;
  generation_source: string;
  summary?: string | null;
  executive_summary?: string | null;
  strengths: Array<Record<string, any>>;
  demonstrated_capabilities: Array<Record<string, any>>;
  claimed_capabilities: Array<Record<string, any>>;
  unknown_capabilities: Array<Record<string, any>>;
  verification_needed: Array<Record<string, any>>;
  evidence_findings: Array<Record<string, any>>;
  round_summaries: Array<Record<string, any>>;
  question_findings: Array<Record<string, any>>;
  follow_up_findings: Array<Record<string, any>>;
  integrity_summary: {
    total_events?: number;
    observations?: Array<{ event_type: string; count: number; summary: string }>;
    raw_event_count_by_type?: Record<string, number>;
    summary_text?: string;
  };
  unresolved_areas: Array<Record<string, any>>;
  recommendations_for_human_review: Array<Record<string, any>>;
  total_questions: number;
  total_messages: number;
  completed_at?: string | null;
  created_at?: string | null;
  completion_reason?: string | null;
  configured_duration_minutes?: number | null;
  started_at?: string | null;
  ended_at?: string | null;
  plan_version?: number | null;
  transcript?: Array<{
    id?: string;
    role: string;
    content: string;
    sequence_number?: number;
    created_at?: string | null;
    latency_ms?: number | null;
  }>;
  unanswered_questions?: Array<{
    id?: string;
    round_number?: number;
    sequence?: number;
    question_text: string;
    category?: string;
    target_competency?: string;
    reason?: string;
  }>;
  media_events?: Array<{
    event_type: string;
    timestamp: string;
    details?: any;
  }>;
  scorecard_data?: Record<string, any> | null;
  failure_reason?: string | null;
}

export type HiringDecisionType = 'SELECTED' | 'REJECTED' | 'ON_HOLD';

export interface HiringDecisionResponse {
  id: string;
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email?: string | null;
  job_id: string;
  job_title: string;
  decision: HiringDecisionType;
  decision_reason: string;
  decided_by: string;
  decided_by_name: string;
  decided_by_email?: string | null;
  decided_at: string;
  report_id?: string | null;
  application_status: string;
  created_at: string;
}

export interface HiringDecisionHistoryResponse {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  current_decision: HiringDecisionResponse | null;
  history: HiringDecisionResponse[];
  total_decisions: number;
}

export interface DecisionReplayResponse {
  application_id: string;
  job_id: string;
  candidate_id: string;
  reconstructed_at: string;
  decision_context: {
    application_id: string;
    candidate_id: string;
    candidate_name: string;
    candidate_email?: string | null;
    job_id: string;
    job_title: string;
    decision: string;
    decision_reason: string;
    decided_by_id: string;
    decided_by_name: string;
    decided_at: string;
    application_status: string;
    report_id?: string | null;
  };
  screening_context: {
    screening_status: string;
    screening_notes?: string | null;
    shortlist_status: string;
    shortlist_reason?: string | null;
    hard_requirement_coverage?: number | null;
    strengths: string[];
    gaps: string[];
    unknowns: string[];
    verification_needs: string[];
  };
  evidence_context: Array<{
    capability_id?: string | null;
    capability_name: string;
    state: string;
    source_type?: string | null;
    source_url?: string | null;
    evidence_excerpt?: string | null;
    confidence?: string | null;
    provenance_summary?: string | null;
  }>;
  interview_context?: {
    report_id?: string | null;
    session_id?: string | null;
    interview_status?: string | null;
    report_summary?: string | null;
    demonstrated_capabilities: string[];
    claimed_capabilities: string[];
    unknown_capabilities: string[];
    verification_needed: string[];
    unresolved_areas: string[];
    question_count: number;
    round_count: number;
    integrity_events_count: number;
  } | null;
  unresolved_areas: string[];
  decision_history: Array<Record<string, any>>;
  limitations: string[];
}

export type OutcomeStatus =
  | 'MEETS_EXPECTATION'
  | 'PARTIALLY_MEETS_EXPECTATION'
  | 'NEEDS_DEVELOPMENT'
  | 'INSUFFICIENT_OBSERVATION';

export interface PostHireOutcomeResponse {
  id: string;
  application_id: string;
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  recorded_by: string;
  recorded_by_name: string;
  recorded_at: string;
  outcome_period: string;
  capability_id?: string | null;
  capability_name: string;
  expected_capability_description?: string | null;
  observed_outcome_description: string;
  outcome_status: OutcomeStatus;
  manager_notes?: string | null;
  evidence_reference?: string | null;
  created_at: string;
}

export interface PostHireOutcomeListResponse {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  outcomes: PostHireOutcomeResponse[];
  total_outcomes: number;
}

export interface CapabilityOutcomeComparison {
  capability_name: string;
  pre_hire_evidence_state: string;
  interview_demonstration_state: string;
  post_hire_outcome_status?: string | null;
  outcome_delta_observation: string;
}

export interface AutopsyFinding {
  category: string;
  finding_text: string;
  affected_capability: string;
  grounded_facts: string[];
}

export interface AIImprovementSuggestion {
  suggestion_id: string;
  affected_capability: string;
  observed_pattern: string;
  suggested_improvement: string;
  action_type: string;
  confidence_strength: string;
  supporting_records: string[];
  is_advisory_only: boolean;
}

export interface HiringAutopsyResponse {
  application_id: string;
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  decision_summary: Record<string, any>;
  decision_replay_summary: Record<string, any>;
  post_hire_outcomes: PostHireOutcomeResponse[];
  capability_comparison: CapabilityOutcomeComparison[];
  findings: AutopsyFinding[];
  ai_improvement_suggestions: AIImprovementSuggestion[];
  limitations: string[];
}

export interface DemoImportResult {
  imported_count: number;
  skipped_count: number;
  failed_count: number;
  job_id: string;
  message: string;
  imported_candidates: Array<{
    candidate_id: string;
    application_id: string;
    full_name: string;
    email: string;
    is_demo: boolean;
  }>;
  errors: string[];
}

export interface EmailConnectionResponse {
  id: string;
  organization_id: string;
  provider: string;
  account_email: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface BatchEmailSyncResponse {
  emails_fetched: number;
  candidate_emails: number;
  irrelevant_emails: number;
  possible_applications: number;
  resumes_found: number;
  resumes_processed: number;
  duplicates_skipped: number;
  failures: number;
  details: Array<{
    email_id: string;
    classification: string;
    candidate_email?: string | null;
    candidate_name?: string | null;
    intake_status: string;
    reason: string;
  }>;
}

export type IntegrityEventType =
  | 'TAB_HIDDEN'
  | 'TAB_VISIBLE'
  | 'FULLSCREEN_ENTER'
  | 'FULLSCREEN_EXIT'
  | 'CAMERA_CONNECTED'
  | 'CAMERA_DISCONNECTED'
  | 'CAMERA_MUTED'
  | 'MICROPHONE_CONNECTED'
  | 'MICROPHONE_DISCONNECTED'
  | 'MICROPHONE_MUTED'
  | 'MEDIA_RECOVERY_STARTED'
  | 'MEDIA_RECOVERY_FAILED'
  | 'DETECTOR_UNAVAILABLE'
  | 'CONNECTION_INTERRUPTED'
  | 'CONNECTION_RESTORED'
  | 'PHONE_DETECTED'
  | 'MULTIPLE_PERSONS_DETECTED';

export interface IntegrityObservationEvent {
  type: 'integrity_observation';
  event_type: IntegrityEventType;
  alert_title: string;
  alert_message: string;
  event_id: string;
  evidence_reference?: string;
  evidence_url?: string;
  confidence?: number;
  occurred_at: string;
  metadata?: Record<string, any>;
}

export interface IntegrityAlert {
  id: string;
  eventType: IntegrityEventType;
  title: string;
  message: string;
  occurredAt: string;
  evidenceUrl?: string;
  evidenceReference?: string;
}

export type PreInterviewCapabilityStatus =
  | 'SUPPORTED'
  | 'PARTIAL'
  | 'UNKNOWN'
  | 'CONTRADICTORY';

export type PreInterviewConfidenceLevel =
  | 'HIGH'
  | 'MEDIUM'
  | 'LOW'
  | 'NONE';

export interface ScorecardEvidenceItem {
  id: string;
  source_type: string;
  source_reference?: string | null;
  excerpt?: string | null;
  source_location?: string | null;
  provenance: string;
  strength: string;
  created_at?: string | null;
  limitations?: string | null;
}

export interface ScorecardVerificationRecommendation {
  action_type: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  guidance: string;
}

export interface TargetedInterviewQuestion {
  question_text: string;
  intent: string;
  difficulty: string;
  expected_signals: string;
  source: string;
}

export interface CapabilityScorecardItem {
  capability_id: string;
  capability_name: string;
  requirement_description?: string | null;
  importance?: string | null;
  status: PreInterviewCapabilityStatus;
  status_rationale: string;
  confidence: PreInterviewConfidenceLevel;
  confidence_justification: string;
  supporting_evidence: ScorecardEvidenceItem[];
  recommended_verification: ScorecardVerificationRecommendation;
  targeted_questions: TargetedInterviewQuestion[];
}

export interface PreInterviewScorecard {
  application_id: string;
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  assessment_timestamp: string;
  scorecard_version: number;
  evidence_readiness_score: number;
  score_explanation: string;
  executive_summary: string;
  total_capabilities: number;
  supported_count: number;
  partial_count: number;
  unknown_count: number;
  contradictory_count: number;
  critical_verification_needs: string[];
  human_review_notice: string;
  capabilities: CapabilityScorecardItem[];
}

export type PostInterviewChangeType =
  | 'STRENGTHENED'
  | 'CONFIRMED'
  | 'UNVERIFIED_CLAIM'
  | 'REMAINED_UNKNOWN'
  | 'CONTRADICTORY';

export interface InterviewEvidenceItem {
  session_id: string;
  question_id?: string | null;
  question_text: string;
  candidate_answer_excerpt?: string | null;
  evaluation_summary?: string | null;
  evaluation_quality?: string | null;
  source_timestamp?: string | null;
  limitations?: string | null;
}

export interface PostInterviewCapabilityScorecardItem {
  capability_id: string;
  capability_name: string;
  requirement_description?: string | null;
  importance?: string | null;
  original_status: PreInterviewCapabilityStatus;
  original_confidence: PreInterviewConfidenceLevel;
  original_rationale: string;
  original_evidence: ScorecardEvidenceItem[];
  original_verification_guidance?: string | null;
  updated_status: PreInterviewCapabilityStatus;
  updated_confidence: PreInterviewConfidenceLevel;
  updated_rationale: string;
  interview_evidence: InterviewEvidenceItem[];
  remaining_uncertainties?: string | null;
  recommended_follow_up?: ScorecardVerificationRecommendation | null;
  change_type: PostInterviewChangeType;
  change_summary: string;
}

export interface PostInterviewScorecard {
  application_id: string;
  job_id: string;
  job_title: string;
  candidate_id: string;
  candidate_name: string;
  interview_session_id: string;
  assessment_timestamp: string;
  scorecard_version: number;
  baseline_scorecard_id: string;
  baseline_assessment_timestamp: string;
  baseline_readiness_score: number;
  post_interview_readiness_score: number;
  readiness_change_delta: number;
  score_explanation: string;
  executive_summary: string;
  total_capabilities: number;
  supported_count: number;
  partial_count: number;
  unknown_count: number;
  contradictory_count: number;
  capabilities_strengthened_count: number;
  capabilities_unverified_count: number;
  critical_verification_needs: string[];
  human_review_notice: string;
  capabilities: PostInterviewCapabilityScorecardItem[];
}

// ==========================================
// Feature 3: Hiring Quality Intelligence Types
// ==========================================

export interface AggregatedFinding {
  capability_name?: string | null;
  category: string;
  summary: string;
  count: number;
  application_ids: string[];
  job_ids: string[];
  outcome_ids: string[];
  evidence_ids: string[];
}

export interface AggregatedRecommendation {
  capability_name?: string | null;
  suggestion_text: string;
  count: number;
  application_ids: string[];
  supporting_records: string[];
  confidence_strength?: string | null;
  action_type?: string | null;
}

export interface HiringIntelligenceResponse {
  total_applications: number;
  applications_with_outcomes: number;
  applications_without_outcomes: number;
  total_outcome_records: number;
  findings: AggregatedFinding[];
  recommendations: AggregatedRecommendation[];
  limitations: string[];
  message?: string | null;
}

// ==========================================
// Feature 4: Hiring Intelligence Chat & RAG Types
// ==========================================

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface HiringChatRequest {
  message: string;
  history?: ChatMessage[];
  application_id?: string | null;
  job_id?: string | null;
}

export interface HiringChatCitation {
  chunk_id: string;
  source_type: string;
  application_id?: string | null;
  job_id?: string | null;
  candidate_name?: string | null;
  job_title?: string | null;
  capability_name?: string | null;
  excerpt: string;
}

export interface RetrievedChunk {
  chunk_id: string;
  source_type: string;
  application_id?: string | null;
  job_id?: string | null;
  candidate_name?: string | null;
  job_title?: string | null;
  capability_name?: string | null;
  text: string;
  relevance_score: number;
  semantic_score?: number | null;
  keyword_score?: number | null;
}

export interface HiringChatResponse {
  answer: string;
  citations: HiringChatCitation[];
  retrieved_chunks: RetrievedChunk[];
  is_advisory_only: boolean;
  context_scope: string;
  limitations: string[];
  generated_at: string;
}

export interface IndexSyncResponse {
  status: string;
  organization_id: string;
  created: number;
  updated: number;
  unchanged: number;
  total_processed: number;
  synced_at: string;
}


