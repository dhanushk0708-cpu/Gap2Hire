import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Calendar,
  Sparkles,
  CheckCircle2,
  Lock,
  Layers,
  Clock,
  Play,
  HelpCircle,
  ShieldCheck,
  Video,
  Edit3,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  RefreshCw,
  Eye,
  AlertTriangle,
  FileText,
  Check,
  X,
  History,
  Sliders,
} from 'lucide-react';
import {
  interviewPlansApi,
  interviewDatasetsApi,
  applicationsApi,
  interviewSessionsApi,
} from '../../core/api/endpoints';
import {
  InterviewPlan,
  InterviewPlanRound,
  InterviewPlanQuestion,
} from '../../core/types';
import { DEMO_MODE } from '../../core/config';
import { PageHeader } from '../../shared/components/PageHeader';
import { Skeleton } from '../../shared/components/Skeleton';
import { Modal } from '../../shared/components/Modal';

export const InterviewPlanView: React.FC = () => {
  const { applicationId } = useParams<{ applicationId: string }>();
  const navigate = useNavigate();

  // Queries
  const [selectedPlanVersionId, setSelectedPlanVersionId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedDatasetId, setSelectedDatasetId] = useState('');

  // Schedule modal state
  const [isScheduleOpen, setIsScheduleOpen] = useState(false);
  const [scheduleDate, setScheduleDate] = useState(
    new Date(Date.now() + 24 * 3600 * 1000).toISOString().slice(0, 16)
  );
  const [scheduleDuration, setScheduleDuration] = useState(45);
  const [scheduleNotes, setScheduleNotes] = useState('');
  const [scheduling, setScheduling] = useState(false);
  const [scheduledSessionId, setScheduledSessionId] = useState<string | null>(null);
  const [startingInterview, setStartingInterview] = useState(false);

  // Editor modal state
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editorRounds, setEditorRounds] = useState<InterviewPlanRound[]>([]);
  const [editorFeedback, setEditorFeedback] = useState('');
  const [editorLockVersion, setEditorLockVersion] = useState<number | undefined>(undefined);
  const [activeRoundIndex, setActiveRoundIndex] = useState(0);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);

  // Question Preview & Manual Add Modal state
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [previewingQuestions, setPreviewingQuestions] = useState(false);
  const [previewResults, setPreviewResults] = useState<InterviewPlanQuestion[]>([]);
  const [selectedPreviewIndices, setSelectedPreviewIndices] = useState<number[]>([]);
  const [targetPreviewRoundIndex, setTargetPreviewRoundIndex] = useState(0);

  // Manual Question Modal state
  const [isQuestionModalOpen, setIsQuestionModalOpen] = useState(false);
  const [editingQuestionRoundIdx, setEditingQuestionRoundIdx] = useState<number>(0);
  const [editingQuestionIdx, setEditingQuestionIdx] = useState<number | null>(null);
  const [qFormText, setQFormText] = useState('');
  const [qFormConcept, setQFormConcept] = useState('');
  const [qFormDifficulty, setQFormDifficulty] = useState('MEDIUM');
  const [qFormType, setQFormType] = useState('PRACTICAL');
  const [qFormPurpose, setQFormPurpose] = useState('');
  const [qFormEvidence, setQFormEvidence] = useState('');

  // Full Plan Preview Modal state
  const [isFullPreviewOpen, setIsFullPreviewOpen] = useState(false);

  // Pre-Analysis Query
  const { data: preAnalysis, isLoading: preLoading } = useQuery({
    queryKey: ['candidatePreAnalysis', applicationId],
    queryFn: () => applicationsApi.getRichPreAnalysis(applicationId!),
    enabled: !!applicationId,
  });

  // Plans List Query
  const {
    data: plans,
    isLoading: plansLoading,
    refetch: refetchPlans,
  } = useQuery({
    queryKey: ['candidatePlans', applicationId],
    queryFn: () => interviewPlansApi.list(applicationId!),
    enabled: !!applicationId,
  });

  // Datasets Query
  const { data: datasets } = useQuery({
    queryKey: ['interviewDatasets'],
    queryFn: interviewDatasetsApi.list,
  });

  // Determine currently viewed plan (selected version or latest)
  const currentPlan = React.useMemo(() => {
    if (!plans || plans.length === 0) return null;
    if (selectedPlanVersionId) {
      const found = plans.find((p) => p.id === selectedPlanVersionId);
      if (found) return found;
    }
    // Default to the highest version or latest
    return plans[0];
  }, [plans, selectedPlanVersionId]);

  // Handle plan generation from scratch
  const handleGeneratePlan = async () => {
    if (!applicationId) return;
    setIsGenerating(true);
    try {
      const created = await interviewPlansApi.generate(applicationId, selectedDatasetId || undefined);
      await refetchPlans();
      setSelectedPlanVersionId(created.id);
    } catch (err: any) {
      alert(err.message || 'Plan generation failed');
    } finally {
      setIsGenerating(false);
    }
  };

  // Open Editor
  const handleOpenEditor = () => {
    if (!currentPlan) return;
    // Deep clone rounds to allow dirty editing
    setEditorRounds(JSON.parse(JSON.stringify(currentPlan.rounds || [])));
    setEditorFeedback(currentPlan.hr_feedback || '');
    setEditorLockVersion(currentPlan.lock_version);
    setActiveRoundIndex(0);
    setEditorError(null);
    setIsEditorOpen(true);
  };

  // Add Round in Editor
  const handleAddRound = () => {
    const nextRoundNumber = editorRounds.length + 1;
    const newRound: InterviewPlanRound = {
      round_number: nextRoundNumber,
      title: `Round ${nextRoundNumber} — Technical Evaluation`,
      objective: 'Evaluate domain competencies and assess practical engineering trade-offs.',
      description: 'Structured interview round targeting technical fundamentals and problem solving.',
      concepts: ['Core Competencies'],
      evaluation_criteria: [
        'Demonstrates practical knowledge of domain best practices.',
        'Articulates clear architectural trade-offs.',
      ],
      expected_evidence: [
        'Examples from recent production projects.',
      ],
      question_generation_mode: 'AI_GENERATED',
      difficulty: 'MEDIUM',
      estimated_duration_minutes: 30,
      required: true,
      sequence: nextRoundNumber,
      questions: [],
    };
    const updated = [...editorRounds, newRound];
    setEditorRounds(updated);
    setActiveRoundIndex(updated.length - 1);
  };

  // Remove Round with confirmation
  const handleRemoveRound = (idx: number) => {
    if (editorRounds.length <= 1) {
      alert('An interview plan must contain at least one round.');
      return;
    }
    if (!window.confirm(`Are you sure you want to remove Round ${editorRounds[idx].round_number} (${editorRounds[idx].title})?`)) {
      return;
    }
    const updated = editorRounds.filter((_, i) => i !== idx).map((r, i) => ({
      ...r,
      round_number: i + 1,
      sequence: i + 1,
    }));
    setEditorRounds(updated);
    setActiveRoundIndex(Math.max(0, idx - 1));
  };

  // Reorder Round Up/Down
  const handleMoveRound = (idx: number, direction: 'up' | 'down') => {
    const targetIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= editorRounds.length) return;
    const updated = [...editorRounds];
    const temp = updated[idx];
    updated[idx] = updated[targetIdx];
    updated[targetIdx] = temp;

    // Renumber sequences
    const reindexed = updated.map((r, i) => ({
      ...r,
      round_number: i + 1,
      sequence: i + 1,
    }));
    setEditorRounds(reindexed);
    setActiveRoundIndex(targetIdx);
  };

  // Save Plan as Draft
  const handleSaveDraft = async () => {
    if (!currentPlan) return;
    setIsSavingDraft(true);
    setEditorError(null);
    try {
      const saved = await interviewPlansApi.update(currentPlan.id, {
        rounds: editorRounds,
        hr_feedback: editorFeedback,
        lock_version: editorLockVersion,
      });
      await refetchPlans();
      setSelectedPlanVersionId(saved.id);
      setIsEditorOpen(false);
      alert(
        saved.version > currentPlan.version
          ? `Original approved plan preserved (v${currentPlan.version}). New draft plan created as v${saved.version}.`
          : 'Interview Plan draft saved successfully.'
      );
    } catch (err: any) {
      setEditorError(err.message || 'Failed to save plan');
    } finally {
      setIsSavingDraft(false);
    }
  };

  // Approve Plan
  const handleApprovePlan = async (planIdToApprove?: string) => {
    const targetId = planIdToApprove || currentPlan?.id;
    if (!targetId) return;
    try {
      const approved = await interviewPlansApi.approve(targetId, 'Plan approved by HR manager');
      await refetchPlans();
      setSelectedPlanVersionId(approved.id);
      if (isEditorOpen) setIsEditorOpen(false);
      if (isFullPreviewOpen) setIsFullPreviewOpen(false);
      alert(`Interview Plan v${approved.version} is now APPROVED and locked for scheduling!`);
    } catch (err: any) {
      alert(err.message || 'Failed to approve plan');
    }
  };

  // Open Preview Questions Modal
  const handleOpenPreviewModal = async (roundIdx: number) => {
    if (!applicationId) return;
    const round = editorRounds[roundIdx];
    setTargetPreviewRoundIndex(roundIdx);
    setIsPreviewModalOpen(true);
    setPreviewingQuestions(true);
    try {
      const questions = await interviewPlansApi.previewQuestions(applicationId, {
        round_title: round.title,
        objective: round.objective,
        description: round.description,
        concepts: round.concepts,
        evaluation_criteria: round.evaluation_criteria,
        expected_evidence: round.expected_evidence,
        difficulty: round.difficulty || 'MEDIUM',
        duration_minutes: round.estimated_duration_minutes,
        question_generation_mode: round.question_generation_mode || 'AI_GENERATED',
        hr_questions: round.questions.filter((q) => q.is_hr_authored),
        target_count: Math.max(2, Math.floor(round.estimated_duration_minutes / 12)),
      });
      setPreviewResults(questions);
      // Select all by default
      setSelectedPreviewIndices(questions.map((_, i) => i));
    } catch (err: any) {
      alert(err.message || 'Failed to generate question preview');
      setIsPreviewModalOpen(false);
    } finally {
      setPreviewingQuestions(false);
    }
  };

  // Accept Selected Preview Questions
  const handleAcceptPreviewQuestions = () => {
    const accepted = previewResults.filter((_, i) => selectedPreviewIndices.includes(i));
    const round = editorRounds[targetPreviewRoundIndex];
    const updatedRound = {
      ...round,
      questions: accepted.map((q, idx) => ({ ...q, sequence: idx + 1 })),
    };
    const updatedRounds = [...editorRounds];
    updatedRounds[targetPreviewRoundIndex] = updatedRound;
    setEditorRounds(updatedRounds);
    setIsPreviewModalOpen(false);
  };

  // Open Manual Question Modal (Create or Edit)
  const handleOpenQuestionModal = (roundIdx: number, qIdx: number | null = null) => {
    setEditingQuestionRoundIdx(roundIdx);
    setEditingQuestionIdx(qIdx);
    if (qIdx !== null) {
      const q = editorRounds[roundIdx].questions[qIdx];
      setQFormText(q.question_text);
      setQFormConcept(q.concept);
      setQFormDifficulty(q.difficulty);
      setQFormType(q.question_type);
      setQFormPurpose(q.purpose || '');
      setQFormEvidence(q.evidence_being_verified || '');
    } else {
      setQFormText('');
      setQFormConcept(editorRounds[roundIdx].concepts[0] || 'Technical Skills');
      setQFormDifficulty(editorRounds[roundIdx].difficulty || 'MEDIUM');
      setQFormType('PRACTICAL');
      setQFormPurpose('');
      setQFormEvidence('');
    }
    setIsQuestionModalOpen(true);
  };

  // Save Manual Question
  const handleSaveQuestion = (e: React.FormEvent) => {
    e.preventDefault();
    if (!qFormText.trim() || !qFormConcept.trim()) return;

    const round = editorRounds[editingQuestionRoundIdx];
    const newQ: InterviewPlanQuestion = {
      id: editingQuestionIdx !== null ? round.questions[editingQuestionIdx].id : undefined,
      question_text: qFormText.trim(),
      concept: qFormConcept.trim(),
      difficulty: qFormDifficulty,
      question_type: qFormType,
      purpose: qFormPurpose.trim() || undefined,
      evidence_being_verified: qFormEvidence.trim() || undefined,
      is_hr_authored: true,
      status: 'APPROVED',
      sequence: editingQuestionIdx !== null ? round.questions[editingQuestionIdx].sequence : round.questions.length + 1,
    };

    let updatedQuestions = [...round.questions];
    if (editingQuestionIdx !== null) {
      updatedQuestions[editingQuestionIdx] = newQ;
    } else {
      updatedQuestions.push(newQ);
    }
    updatedQuestions = updatedQuestions.map((q, i) => ({ ...q, sequence: i + 1 }));

    const updatedRounds = [...editorRounds];
    updatedRounds[editingQuestionRoundIdx] = {
      ...round,
      questions: updatedQuestions,
    };
    setEditorRounds(updatedRounds);
    setIsQuestionModalOpen(false);
  };

  // Remove Question
  const handleRemoveQuestion = (roundIdx: number, qIdx: number) => {
    const round = editorRounds[roundIdx];
    const updatedQuestions = round.questions
      .filter((_, i) => i !== qIdx)
      .map((q, i) => ({ ...q, sequence: i + 1 }));
    const updatedRounds = [...editorRounds];
    updatedRounds[roundIdx] = {
      ...round,
      questions: updatedQuestions,
    };
    setEditorRounds(updatedRounds);
  };

  // Direct Start Live Interview
  const handleDirectStartInterview = async () => {
    if (!applicationId) return;
    setStartingInterview(true);
    try {
      const session = await interviewSessionsApi.create(applicationId);
      navigate(`/interview-room/${session.id}`);
    } catch (err: any) {
      alert(err.message || 'Failed to start interview session');
      setStartingInterview(false);
    }
  };

  // Schedule Session
  const handleScheduleInterview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!applicationId) return;
    setScheduling(true);
    try {
      const session = await interviewSessionsApi.create(applicationId);
      await interviewSessionsApi.schedule(session.id, {
        scheduled_start: new Date(scheduleDate).toISOString(),
        duration_minutes: scheduleDuration,
        invitation_notes: scheduleNotes || undefined,
      });
      setScheduledSessionId(session.id);
      setIsScheduleOpen(false);
      alert('Interview scheduled successfully! Linked to approved plan version.');
    } catch (err: any) {
      alert(err.message || 'Scheduling failed');
    } finally {
      setScheduling(false);
    }
  };

  const currentRoundInEditor = editorRounds[activeRoundIndex] || null;

  return (
    <div>
      <PageHeader
        title={DEMO_MODE ? 'Candidate Interview Plan & Live Execution' : 'Candidate Interview Plan & Scheduling'}
        description="HR-configurable interview rounds, AI-grounded question sequencing, and human approval gate."
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Link to={`/candidates/${applicationId}`} className="btn btn-secondary">
              Candidate Workspace
            </Link>
            <Link to="/interviews" className="btn btn-secondary">
              Interview Scheduler
            </Link>

            {currentPlan && (
              <button onClick={handleOpenEditor} className="btn btn-secondary" style={{ fontWeight: 600 }}>
                <Edit3 size={15} />
                Edit Interview Plan
              </button>
            )}

            {currentPlan && currentPlan.status === 'APPROVED' && (
              DEMO_MODE ? (
                <button
                  onClick={handleDirectStartInterview}
                  disabled={startingInterview}
                  className="btn btn-primary"
                  style={{
                    backgroundColor: '#059669',
                    borderColor: '#059669',
                    color: '#FFFFFF',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                  }}
                  title="Directly launch the live AI interview room"
                >
                  <Play size={14} fill="#FFFFFF" />
                  {startingInterview ? 'Opening Room...' : 'Start Interview Now'}
                </button>
              ) : (
                <button onClick={() => setIsScheduleOpen(true)} className="btn btn-primary">
                  <Calendar size={15} />
                  Schedule Session
                </button>
              )
            )}
          </div>
        }
      />

      {/* Pre-Interview Competency Analysis Summary */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '0.35rem' }}>Pre-Interview Competency Targeting</h3>
        <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
          Distinguishes unverified resume CLAIMS from demonstrated competencies to focus autonomous interview rounds.
        </p>

        {preLoading ? (
          <Skeleton height={80} />
        ) : !preAnalysis ? (
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            No pre-interview analysis available yet.
          </p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
            <div style={{ padding: '0.875rem', backgroundColor: '#ECFDF5', borderRadius: 'var(--radius-md)', border: '1px solid #A7F3D0' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#047857', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                Demonstrated Strengths ({preAnalysis.candidate_strengths.length})
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8125rem', color: '#065F46' }}>
                {preAnalysis.candidate_strengths.slice(0, 3).map((s: any, idx: number) => (
                  <li key={idx}>{s.name || s.capability_name || JSON.stringify(s)}</li>
                ))}
              </ul>
            </div>

            <div style={{ padding: '0.875rem', backgroundColor: '#EFF6FF', borderRadius: 'var(--radius-md)', border: '1px solid #BFDBFE' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#1D4ED8', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                Claims To Validate ({preAnalysis.candidate_claims.length})
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8125rem', color: '#1E40AF' }}>
                {preAnalysis.candidate_claims.slice(0, 3).map((c: any, idx: number) => (
                  <li key={idx}>{c.name || c.capability_name || JSON.stringify(c)}</li>
                ))}
              </ul>
            </div>

            <div style={{ padding: '0.875rem', backgroundColor: '#FFFBEB', borderRadius: 'var(--radius-md)', border: '1px solid #FDE68A' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#B45309', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                Unknown Competencies ({preAnalysis.candidate_unknowns.length})
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8125rem', color: '#92400E' }}>
                {preAnalysis.candidate_unknowns.slice(0, 3).map((u: any, idx: number) => (
                  <li key={idx}>{u.name || u.capability_name || JSON.stringify(u)}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* Plan Status & Generation Header */}
      {!currentPlan ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
          <Sparkles size={36} color="var(--primary-600)" style={{ margin: '0 auto 1rem' }} />
          <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Generate Autonomous Interview Plan</h3>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '480px', margin: '0 auto 1.5rem' }}>
            Assemble targeted interview rounds combining pre-interview gap analysis with verified question datasets.
          </p>

          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
            <select
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              style={{ maxWidth: '300px' }}
            >
              <option value="">-- Standard Question Bank (Default) --</option>
              {datasets?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.total_questions} questions)
                </option>
              ))}
            </select>

            <button
              onClick={handleGeneratePlan}
              disabled={isGenerating}
              className="btn btn-primary"
            >
              <Sparkles size={16} />
              {isGenerating ? 'Synthesizing Plan...' : 'Generate Plan'}
            </button>
          </div>
        </div>
      ) : (
        <div>
          {/* Plan Governance & Versioning Bar */}
          <div
            className="card"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1.5rem',
              backgroundColor: currentPlan.status === 'APPROVED' ? '#F0FDF4' : '#FFFBEB',
              borderColor: currentPlan.status === 'APPROVED' ? '#BBF7D0' : '#FDE68A',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                <h3 style={{ fontSize: '1.1rem' }}>Interview Plan (v{currentPlan.version})</h3>
                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.15rem 0.55rem',
                    borderRadius: '9999px',
                    backgroundColor: currentPlan.status === 'APPROVED' ? '#15803D' : '#B45309',
                    color: '#FFFFFF',
                  }}
                >
                  {currentPlan.status === 'APPROVED' ? 'HR APPROVED' : 'AI DRAFT PLAN'}
                </span>

                {plans && plans.length > 1 && (
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', marginLeft: '0.5rem' }}>
                    <History size={14} color="var(--text-secondary)" />
                    <select
                      value={currentPlan.id}
                      onChange={(e) => setSelectedPlanVersionId(e.target.value)}
                      style={{ fontSize: '0.75rem', padding: '0.15rem 0.45rem' }}
                    >
                      {plans.map((p) => (
                        <option key={p.id} value={p.id}>
                          v{p.version} — {p.status} ({new Date(p.created_at).toLocaleDateString()})
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                {currentPlan.status === 'APPROVED'
                  ? `Approved and locked on ${new Date(currentPlan.approved_at || currentPlan.updated_at).toLocaleString()}`
                  : 'Draft plan. You can edit rounds, configure question generation modes, and preview questions before approving.'}
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <button onClick={() => setIsFullPreviewOpen(true)} className="btn btn-secondary btn-sm">
                <Eye size={14} />
                Preview Full Plan
              </button>

              {currentPlan.status !== 'APPROVED' ? (
                <button onClick={() => handleApprovePlan()} className="btn btn-success btn-sm">
                  <CheckCircle2 size={15} />
                  Approve Plan (HR Gate)
                </button>
              ) : (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8125rem', color: '#15803D', fontWeight: 600 }}>
                  <Lock size={15} />
                  Plan Locked
                </span>
              )}
            </div>
          </div>

          {/* Rounds & Questions List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {currentPlan.rounds.map((round) => (
              <div key={round.round_number} className="card">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: '50%',
                        backgroundColor: 'var(--primary-600)',
                        color: '#FFFFFF',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.875rem',
                        fontWeight: 700,
                      }}
                    >
                      {round.round_number}
                    </span>
                    <div>
                      <h4 style={{ fontSize: '1.05rem', margin: 0 }}>{round.title}</h4>
                      {round.description && (
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                          {round.description}
                        </p>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        padding: '0.15rem 0.5rem',
                        borderRadius: '4px',
                        backgroundColor:
                          round.difficulty === 'HARD'
                            ? '#FEF2F2'
                            : round.difficulty === 'EASY'
                            ? '#ECFDF5'
                            : '#EFF6FF',
                        color:
                          round.difficulty === 'HARD'
                            ? '#991B1B'
                            : round.difficulty === 'EASY'
                            ? '#065F46'
                            : '#1E40AF',
                        border: '1px solid currentColor',
                      }}
                    >
                      {round.difficulty || 'MEDIUM'} DIFFICULTY
                    </span>

                    <span
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        padding: '0.15rem 0.5rem',
                        borderRadius: '4px',
                        backgroundColor: '#F3F4F6',
                        color: '#374151',
                        border: '1px solid #D1D5DB',
                      }}
                    >
                      MODE: {round.question_generation_mode || 'AI_GENERATED'}
                    </span>

                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Clock size={13} />
                      ~{round.estimated_duration_minutes} min
                    </span>
                  </div>
                </div>

                <div style={{ marginBottom: '0.85rem' }}>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                    <strong>Objective:</strong> {round.objective}
                  </div>

                  {round.concepts && round.concepts.length > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap', marginTop: '0.35rem' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>Topics:</span>
                      {round.concepts.map((c, i) => (
                        <span
                          key={i}
                          style={{
                            fontSize: '0.6875rem',
                            padding: '0.1rem 0.45rem',
                            backgroundColor: '#F1F5F9',
                            borderRadius: '4px',
                            border: '1px solid #CBD5E1',
                            color: '#334155',
                          }}
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  )}

                  {round.evaluation_criteria && round.evaluation_criteria.length > 0 && (
                    <div style={{ marginTop: '0.6rem', padding: '0.6rem 0.75rem', backgroundColor: '#F8FAFC', borderRadius: '4px', border: '1px solid #E2E8F0' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>
                        Evaluation Criteria & Expectations
                      </span>
                      <ul style={{ margin: '0.35rem 0 0 0', paddingLeft: '1.2rem', fontSize: '0.75rem', color: '#334155' }}>
                        {round.evaluation_criteria.map((ec, i) => (
                          <li key={i}>{ec}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Question items */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {round.questions.map((q, qIdx) => (
                    <div
                      key={qIdx}
                      style={{
                        padding: '0.875rem',
                        backgroundColor: 'var(--bg-app)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-base)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)' }}>
                            Q{q.sequence}: {q.concept}
                          </span>
                          {q.is_hr_authored && (
                            <span
                              style={{
                                fontSize: '0.625rem',
                                fontWeight: 700,
                                padding: '0.05rem 0.35rem',
                                backgroundColor: '#EFF6FF',
                                color: '#1D4ED8',
                                borderRadius: '4px',
                                border: '1px solid #BFDBFE',
                              }}
                            >
                              HR AUTHORED
                            </span>
                          )}
                        </div>
                        <span style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-base)' }}>
                          {q.question_type} • {q.difficulty}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.35rem' }}>
                        {q.question_text}
                      </div>
                      {q.purpose && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          Target Evidence: {q.purpose}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* FULL HR INTERVIEW PLAN EDITOR MODAL                                      */}
      {/* ========================================================================= */}
      <Modal
        isOpen={isEditorOpen}
        onClose={() => setIsEditorOpen(false)}
        title={`Edit Interview Plan (Drafting v${(currentPlan?.status === 'APPROVED' ? (currentPlan.version + 1) : currentPlan?.version) || 1})`}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', maxHeight: '75vh', overflowY: 'auto', paddingRight: '0.25rem' }}>
          {editorError && (
            <div style={{ padding: '0.75rem', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '4px', color: '#991B1B', fontSize: '0.8125rem' }}>
              <AlertTriangle size={15} style={{ verticalAlign: 'middle', marginRight: '0.4rem' }} />
              {editorError}
            </div>
          )}

          {currentPlan?.status === 'APPROVED' && (
            <div style={{ padding: '0.75rem', backgroundColor: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: '4px', color: '#1E40AF', fontSize: '0.8125rem' }}>
              <ShieldCheck size={16} style={{ verticalAlign: 'middle', marginRight: '0.4rem' }} />
              <strong>Version Preservation:</strong> The existing approved plan (v{currentPlan.version}) will remain unchanged and locked for already scheduled interviews. Your changes will be saved into a new draft version.
            </div>
          )}

          {/* Rounds Tabs & Management */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <label style={{ fontSize: '0.8125rem', fontWeight: 700 }}>
                Interview Rounds ({editorRounds.length})
              </label>
              <button
                type="button"
                onClick={handleAddRound}
                className="btn btn-secondary btn-sm"
              >
                <Plus size={13} />
                Add Round
              </button>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.5rem' }}>
              {editorRounds.map((r, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setActiveRoundIndex(idx)}
                  className={`btn ${activeRoundIndex === idx ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  Round {r.round_number}
                </button>
              ))}
            </div>
          </div>

          {/* Active Round Editor */}
          {currentRoundInEditor && (
            <div style={{ border: '1px solid var(--border-base)', borderRadius: 'var(--radius-md)', padding: '1.25rem', backgroundColor: '#F8FAFC' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                <h4 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>
                  Configuring Round {currentRoundInEditor.round_number}
                </h4>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <button
                    type="button"
                    title="Move Round Earlier"
                    disabled={activeRoundIndex === 0}
                    onClick={() => handleMoveRound(activeRoundIndex, 'up')}
                    className="btn btn-secondary btn-sm"
                  >
                    <ArrowUp size={13} />
                  </button>
                  <button
                    type="button"
                    title="Move Round Later"
                    disabled={activeRoundIndex === editorRounds.length - 1}
                    onClick={() => handleMoveRound(activeRoundIndex, 'down')}
                    className="btn btn-secondary btn-sm"
                  >
                    <ArrowDown size={13} />
                  </button>
                  <button
                    type="button"
                    title="Delete Round"
                    onClick={() => handleRemoveRound(activeRoundIndex)}
                    className="btn btn-secondary btn-sm"
                    style={{ color: '#DC2626' }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              {/* Round Details Form */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                    Round Title *
                  </label>
                  <input
                    type="text"
                    required
                    style={{ width: '100%', fontSize: '0.875rem' }}
                    value={currentRoundInEditor.title}
                    onChange={(e) => {
                      const updated = [...editorRounds];
                      updated[activeRoundIndex].title = e.target.value;
                      setEditorRounds(updated);
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                    Estimated Duration
                  </label>
                  <select
                    style={{ width: '100%', fontSize: '0.875rem' }}
                    value={currentRoundInEditor.estimated_duration_minutes}
                    onChange={(e) => {
                      const updated = [...editorRounds];
                      updated[activeRoundIndex].estimated_duration_minutes = Number(e.target.value);
                      setEditorRounds(updated);
                    }}
                  >
                    <option value={15}>15 Minutes</option>
                    <option value={30}>30 Minutes</option>
                    <option value={45}>45 Minutes</option>
                    <option value={60}>60 Minutes</option>
                    <option value={90}>90 Minutes</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                    Round Difficulty
                  </label>
                  <select
                    style={{ width: '100%', fontSize: '0.875rem' }}
                    value={currentRoundInEditor.difficulty || 'MEDIUM'}
                    onChange={(e) => {
                      const updated = [...editorRounds];
                      updated[activeRoundIndex].difficulty = e.target.value;
                      setEditorRounds(updated);
                    }}
                  >
                    <option value="EASY">EASY</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HARD">HARD</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                    Question Generation Mode
                  </label>
                  <select
                    style={{ width: '100%', fontSize: '0.875rem' }}
                    value={currentRoundInEditor.question_generation_mode || 'AI_GENERATED'}
                    onChange={(e) => {
                      const updated = [...editorRounds];
                      updated[activeRoundIndex].question_generation_mode = e.target.value as any;
                      setEditorRounds(updated);
                    }}
                  >
                    <option value="AI_GENERATED">AI-Generated (Automatic from round context)</option>
                    <option value="HR_DEFINED">HR-Defined (Only manual questions)</option>
                    <option value="HYBRID">Hybrid (Preserve HR + generate complementary)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                    Topics / Concepts (comma-separated)
                  </label>
                  <input
                    type="text"
                    style={{ width: '100%', fontSize: '0.875rem' }}
                    value={(currentRoundInEditor.concepts || []).join(', ')}
                    onChange={(e) => {
                      const updated = [...editorRounds];
                      updated[activeRoundIndex].concepts = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                      setEditorRounds(updated);
                    }}
                  />
                </div>

                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                    Objective *
                  </label>
                  <textarea
                    rows={2}
                    required
                    style={{ width: '100%', fontSize: '0.875rem' }}
                    value={currentRoundInEditor.objective}
                    onChange={(e) => {
                      const updated = [...editorRounds];
                      updated[activeRoundIndex].objective = e.target.value;
                      setEditorRounds(updated);
                    }}
                  />
                </div>

                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                    Evaluation Criteria (one per line)
                  </label>
                  <textarea
                    rows={2}
                    placeholder="Clear differentiation between conceptual definition and implementation..."
                    style={{ width: '100%', fontSize: '0.8125rem' }}
                    value={(currentRoundInEditor.evaluation_criteria || []).join('\n')}
                    onChange={(e) => {
                      const updated = [...editorRounds];
                      updated[activeRoundIndex].evaluation_criteria = e.target.value.split('\n').map((s) => s.trim()).filter(Boolean);
                      setEditorRounds(updated);
                    }}
                  />
                </div>
              </div>

              {/* Questions Section within Active Round */}
              <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <div>
                    <h5 style={{ fontSize: '0.875rem', fontWeight: 700, margin: 0 }}>
                      Round Questions ({currentRoundInEditor.questions.length})
                    </h5>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Author questions manually, or use AI Preview & Regeneration.
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      type="button"
                      onClick={() => handleOpenQuestionModal(activeRoundIndex)}
                      className="btn btn-secondary btn-sm"
                    >
                      <Plus size={13} />
                      Author Question
                    </button>
                    <button
                      type="button"
                      onClick={() => handleOpenPreviewModal(activeRoundIndex)}
                      className="btn btn-primary btn-sm"
                    >
                      <Sparkles size={13} />
                      AI Preview / Regenerate
                    </button>
                  </div>
                </div>

                {currentRoundInEditor.questions.length === 0 ? (
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', textAlign: 'center', padding: '1rem', backgroundColor: '#FFFFFF', borderRadius: '4px' }}>
                    No questions added to this round yet. Click <strong>Author Question</strong> or <strong>AI Preview / Regenerate</strong> to populate.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {currentRoundInEditor.questions.map((q, qIdx) => (
                      <div
                        key={qIdx}
                        style={{
                          backgroundColor: '#FFFFFF',
                          padding: '0.65rem 0.85rem',
                          borderRadius: '4px',
                          border: '1px solid #E2E8F0',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '0.75rem',
                        }}
                      >
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.2rem' }}>
                            <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-muted)' }}>
                              Q{q.sequence} • {q.concept}
                            </span>
                            {q.is_hr_authored && (
                              <span style={{ fontSize: '0.5625rem', fontWeight: 700, padding: '0.05rem 0.3rem', backgroundColor: '#EFF6FF', color: '#1D4ED8', borderRadius: '3px' }}>
                                HR AUTHORED
                              </span>
                            )}
                            <span style={{ fontSize: '0.625rem', color: '#64748B' }}>
                              ({q.difficulty} / {q.question_type})
                            </span>
                          </div>
                          <div style={{ fontSize: '0.8125rem', color: 'var(--text-main)', fontWeight: 500 }}>
                            {q.question_text}
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <button
                            type="button"
                            onClick={() => handleOpenQuestionModal(activeRoundIndex, qIdx)}
                            className="btn btn-secondary btn-sm"
                            title="Edit Question"
                          >
                            <Edit3 size={12} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRemoveQuestion(activeRoundIndex, qIdx)}
                            className="btn btn-secondary btn-sm"
                            style={{ color: '#DC2626' }}
                            title="Remove Question"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* HR Feedback / Notes */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              HR Plan Notes & Governance Remarks
            </label>
            <input
              type="text"
              placeholder="e.g. Added custom system design questions per engineering hiring manager request..."
              style={{ width: '100%', fontSize: '0.875rem' }}
              value={editorFeedback}
              onChange={(e) => setEditorFeedback(e.target.value)}
            />
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem', borderTop: '1px solid var(--border-base)', paddingTop: '1rem' }}>
            <button
              type="button"
              onClick={() => setIsEditorOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isSavingDraft}
              onClick={handleSaveDraft}
              className="btn btn-primary"
            >
              {isSavingDraft ? 'Saving Draft...' : 'Save Changes as Draft'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ========================================================================= */}
      {/* AI QUESTION PREVIEW & REGENERATION MODAL                                  */}
      {/* ========================================================================= */}
      <Modal
        isOpen={isPreviewModalOpen}
        onClose={() => setIsPreviewModalOpen(false)}
        title={`AI Question Preview & Selection (Round ${editorRounds[targetPreviewRoundIndex]?.round_number})`}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            Review candidate-grounded questions synthesized from the round's objective, difficulty ({editorRounds[targetPreviewRoundIndex]?.difficulty}), and evaluation criteria. Select the questions to import into the round.
          </p>

          {previewingQuestions ? (
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              <RefreshCw size={28} className="spin" style={{ margin: '0 auto 0.5rem', color: 'var(--primary-600)' }} />
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Synthesizing targeted questions from round context...
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', maxHeight: '50vh', overflowY: 'auto' }}>
              {previewResults.map((pq, idx) => {
                const isSelected = selectedPreviewIndices.includes(idx);
                return (
                  <div
                    key={idx}
                    onClick={() => {
                      if (isSelected) {
                        setSelectedPreviewIndices(selectedPreviewIndices.filter((i) => i !== idx));
                      } else {
                        setSelectedPreviewIndices([...selectedPreviewIndices, idx]);
                      }
                    }}
                    style={{
                      border: isSelected ? '2px solid var(--primary-600)' : '1px solid var(--border-base)',
                      backgroundColor: isSelected ? '#F0FDF4' : '#FFFFFF',
                      borderRadius: 'var(--radius-md)',
                      padding: '0.75rem',
                      cursor: 'pointer',
                      display: 'flex',
                      gap: '0.75rem',
                      alignItems: 'flex-start',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}}
                      style={{ marginTop: '0.25rem' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.25rem' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)' }}>
                          {pq.concept}
                        </span>
                        <span style={{ fontSize: '0.625rem', padding: '0.05rem 0.35rem', backgroundColor: '#F1F5F9', borderRadius: '3px' }}>
                          {pq.difficulty} • {pq.question_type}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.35rem' }}>
                        {pq.question_text}
                      </div>
                      {pq.purpose && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          Target: {pq.purpose}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
            <button
              type="button"
              disabled={previewingQuestions}
              onClick={() => handleOpenPreviewModal(targetPreviewRoundIndex)}
              className="btn btn-secondary btn-sm"
            >
              <RefreshCw size={13} />
              Regenerate Another Set
            </button>

            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button
                type="button"
                onClick={() => setIsPreviewModalOpen(false)}
                className="btn btn-secondary btn-sm"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={previewingQuestions || selectedPreviewIndices.length === 0}
                onClick={handleAcceptPreviewQuestions}
                className="btn btn-primary btn-sm"
              >
                Accept {selectedPreviewIndices.length} Questions
              </button>
            </div>
          </div>
        </div>
      </Modal>

      {/* ========================================================================= */}
      {/* MANUAL QUESTION AUTHORING / EDIT MODAL                                    */}
      {/* ========================================================================= */}
      <Modal
        isOpen={isQuestionModalOpen}
        onClose={() => setIsQuestionModalOpen(false)}
        title={editingQuestionIdx !== null ? 'Edit Question' : 'Author Question Manually'}
      >
        <form onSubmit={handleSaveQuestion} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Question Text *
            </label>
            <textarea
              required
              rows={3}
              placeholder="e.g. How do you implement idempotent API endpoints using Redis locking?"
              style={{ width: '100%', fontSize: '0.875rem' }}
              value={qFormText}
              onChange={(e) => setQFormText(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Technical Concept / Skill *
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Concurrency, PostgreSQL"
                style={{ width: '100%', fontSize: '0.875rem' }}
                value={qFormConcept}
                onChange={(e) => setQFormConcept(e.target.value)}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Difficulty
              </label>
              <select
                style={{ width: '100%', fontSize: '0.875rem' }}
                value={qFormDifficulty}
                onChange={(e) => setQFormDifficulty(e.target.value)}
              >
                <option value="EASY">EASY</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HARD">HARD</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Question Type
              </label>
              <select
                style={{ width: '100%', fontSize: '0.875rem' }}
                value={qFormType}
                onChange={(e) => setQFormType(e.target.value)}
              >
                <option value="CONCEPTUAL">CONCEPTUAL</option>
                <option value="PRACTICAL">PRACTICAL</option>
                <option value="SYSTEM_DESIGN">SYSTEM_DESIGN</option>
                <option value="BEHAVIORAL">BEHAVIORAL</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Target Purpose / Claim Probed
              </label>
              <input
                type="text"
                placeholder="Verify distributed locking knowledge"
                style={{ width: '100%', fontSize: '0.875rem' }}
                value={qFormPurpose}
                onChange={(e) => setQFormPurpose(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsQuestionModalOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              {editingQuestionIdx !== null ? 'Update Question' : 'Add Question'}
            </button>
          </div>
        </form>
      </Modal>

      {/* ========================================================================= */}
      {/* FULL PLAN PREVIEW MODAL BEFORE APPROVAL                                  */}
      {/* ========================================================================= */}
      <Modal
        isOpen={isFullPreviewOpen}
        onClose={() => setIsFullPreviewOpen(false)}
        title={`Complete Interview Plan Preview • v${currentPlan?.version}`}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxHeight: '70vh', overflowY: 'auto' }}>
          <div style={{ padding: '0.75rem', backgroundColor: '#F8FAFC', borderRadius: '4px', border: '1px solid #E2E8F0', fontSize: '0.8125rem' }}>
            <div style={{ fontWeight: 700, marginBottom: '0.2rem' }}>Plan Governance Summary</div>
            <div>Total Rounds: <strong>{currentPlan?.rounds.length}</strong></div>
            <div>Status: <strong>{currentPlan?.status}</strong></div>
            {currentPlan?.hr_feedback && <div>HR Notes: {currentPlan.hr_feedback}</div>}
          </div>

          {currentPlan?.rounds.map((round) => (
            <div key={round.round_number} style={{ border: '1px solid #CBD5E1', borderRadius: 'var(--radius-md)', padding: '0.875rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                  Round {round.round_number}: {round.title}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#64748B' }}>
                  ~{round.estimated_duration_minutes} min • {round.difficulty} • {round.question_generation_mode}
                </span>
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                {round.objective}
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {round.questions.map((q, idx) => (
                  <div key={idx} style={{ fontSize: '0.8125rem', padding: '0.4rem 0.6rem', backgroundColor: '#F1F5F9', borderRadius: '4px' }}>
                    <strong>Q{q.sequence} ({q.concept}):</strong> {q.question_text}
                  </div>
                ))}
              </div>
            </div>
          ))}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button onClick={() => setIsFullPreviewOpen(false)} className="btn btn-secondary">
              Close Preview
            </button>
            {currentPlan?.status !== 'APPROVED' && (
              <button onClick={() => handleApprovePlan()} className="btn btn-success">
                <CheckCircle2 size={15} />
                Approve & Lock Plan
              </button>
            )}
          </div>
        </div>
      </Modal>

      {/* Schedule Interview Modal (Hidden in DEMO_MODE) */}
      {!DEMO_MODE && (
        <Modal
          isOpen={isScheduleOpen}
          onClose={() => setIsScheduleOpen(false)}
          title="Schedule Live Interview Session"
        >
          <form onSubmit={handleScheduleInterview} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Scheduled Date & Time *
              </label>
              <input
                type="datetime-local"
                required
                style={{ width: '100%' }}
                value={scheduleDate}
                onChange={(e) => setScheduleDate(e.target.value)}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Session Duration (minutes)
              </label>
              <input
                type="number"
                min={15}
                max={180}
                style={{ width: '100%' }}
                value={scheduleDuration}
                onChange={(e) => setScheduleDuration(Number(e.target.value))}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Invitation Notes for Candidate
              </label>
              <textarea
                rows={3}
                placeholder="Instructions regarding microphone, camera, or preparation..."
                style={{ width: '100%' }}
                value={scheduleNotes}
                onChange={(e) => setScheduleNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                onClick={() => setIsScheduleOpen(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={scheduling}
                className="btn btn-primary"
              >
                {scheduling ? 'Scheduling...' : 'Confirm Schedule'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Post-schedule confirmation box */}
      {scheduledSessionId && (
        <div
          className="card"
          style={{
            marginTop: '1.5rem',
            backgroundColor: '#EFF6FF',
            borderColor: '#BFDBFE',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1D4ED8' }}>
              Interview Session Created!
            </div>
            <div style={{ fontSize: '0.8125rem', color: '#1E40AF', marginTop: '0.2rem' }}>
              Session ID: {scheduledSessionId}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <Link
              to={`/interview-room/${scheduledSessionId}`}
              className="btn btn-primary btn-sm"
              target="_blank"
            >
              <Video size={14} />
              Candidate Live Room
            </Link>
            <Link
              to={`/interviews/${scheduledSessionId}/observer`}
              className="btn btn-secondary btn-sm"
              target="_blank"
            >
              HR Live Observer
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};
