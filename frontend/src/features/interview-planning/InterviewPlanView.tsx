import React, { useState } from 'react';
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
  FileSpreadsheet,
} from 'lucide-react';
import {
  interviewPlansApi,
  interviewDatasetsApi,
  applicationsApi,
  interviewSessionsApi,
} from '../../core/api/endpoints';
import { DEMO_MODE } from '../../core/config';
import { PageHeader } from '../../shared/components/PageHeader';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';
import { Modal } from '../../shared/components/Modal';

export const InterviewPlanView: React.FC = () => {
  const { applicationId } = useParams<{ applicationId: string }>();
  const navigate = useNavigate();

  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [isScheduleOpen, setIsScheduleOpen] = useState(false);
  const [scheduleDate, setScheduleDate] = useState(
    new Date(Date.now() + 24 * 3600 * 1000).toISOString().slice(0, 16)
  );
  const [scheduleDuration, setScheduleDuration] = useState(45);
  const [scheduleNotes, setScheduleNotes] = useState('');
  const [scheduling, setScheduling] = useState(false);
  const [scheduledSessionId, setScheduledSessionId] = useState<string | null>(null);
  const [startingInterview, setStartingInterview] = useState(false);

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

  // Latest plan
  const currentPlan = plans && plans.length > 0 ? plans[plans.length - 1] : null;

  const handleGeneratePlan = async () => {
    if (!applicationId) return;
    setIsGenerating(true);
    try {
      await interviewPlansApi.generate(applicationId, selectedDatasetId || undefined);
      await refetchPlans();
    } catch (err: any) {
      alert(err.message || 'Plan generation failed');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApprovePlan = async () => {
    if (!currentPlan) return;
    try {
      await interviewPlansApi.approve(currentPlan.id, 'Plan approved by HR manager');
      await refetchPlans();
      alert('Interview Plan approved and locked for live execution.');
    } catch (err: any) {
      alert(err.message || 'Failed to approve plan');
    }
  };

  const handleScheduleInterview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!applicationId) return;
    setScheduling(true);
    try {
      // 1. Create or ensure session
      const session = await interviewSessionsApi.create(applicationId);
      // 2. Schedule session
      await interviewSessionsApi.schedule(session.id, {
        scheduled_start: new Date(scheduleDate).toISOString(),
        duration_minutes: scheduleDuration,
        invitation_notes: scheduleNotes || undefined,
      });
      setScheduledSessionId(session.id);
      setIsScheduleOpen(false);
      alert('Interview scheduled successfully! Meeting room is active.');
    } catch (err: any) {
      alert(err.message || 'Scheduling failed');
    } finally {
      setScheduling(false);
    }
  };

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

  return (
    <div>
      <PageHeader
        title={DEMO_MODE ? "Candidate Interview Plan & Live Execution" : "Candidate Interview Plan & Scheduling"}
        description="Candidate pre-interview competency targeting, multi-round question sequencing, and human approval."
        actions={
          <>
            <Link
              to={`/candidates/${applicationId}`}
              className="btn btn-secondary"
            >
              Candidate Workspace
            </Link>
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
                  title="Directly launch the live AI interview room without scheduling"
                >
                  <Play size={14} fill="#FFFFFF" />
                  {startingInterview ? 'Opening Room...' : 'Start Interview Now'}
                </button>
              ) : (
                <button
                  onClick={() => setIsScheduleOpen(true)}
                  className="btn btn-primary"
                >
                  <Calendar size={15} />
                  Schedule Interview Session
                </button>
              )
            )}
          </>
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
          {/* Plan Governance Bar */}
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
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
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
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                {currentPlan.status === 'APPROVED'
                  ? `Approved by HR manager on ${new Date(currentPlan.approved_at || currentPlan.updated_at).toLocaleString()}`
                  : 'Requires explicit HR review and approval before scheduling.'}
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              {currentPlan.status !== 'APPROVED' ? (
                <button
                  onClick={handleApprovePlan}
                  className="btn btn-success"
                >
                  <CheckCircle2 size={16} />
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

          {/* Rounds & Questions Accordion / List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {currentPlan.rounds.map((round) => (
              <div key={round.round_number} className="card">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span
                      style={{
                        width: 26,
                        height: 26,
                        borderRadius: '50%',
                        backgroundColor: 'var(--primary-600)',
                        color: '#FFFFFF',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.8125rem',
                        fontWeight: 700,
                      }}
                    >
                      {round.round_number}
                    </span>
                    <h4 style={{ fontSize: '1.05rem' }}>{round.title}</h4>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                    <Clock size={13} />
                    ~{round.estimated_duration_minutes} min
                  </span>
                </div>

                <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  <strong>Objective:</strong> {round.objective}
                </p>

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
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                          Q{q.sequence}: {q.concept}
                        </span>
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

      {/* Schedule Interview Modal (Hidden in DEMO_MODE) */}
      {!DEMO_MODE && (
        <Modal
          isOpen={isScheduleOpen}
          onClose={() => setIsScheduleOpen(false)}
          title="Schedule Live Interview Session"
          subtitle="Generates session meeting room and notifies candidate"
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
