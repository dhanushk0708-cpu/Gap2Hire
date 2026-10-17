import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  User,
  FileText,
  ShieldCheck,
  RotateCcw,
  Sparkles,
  ClipboardList,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Clock,
  Layers,
  ChevronRight,
  Gavel,
  History,
  TrendingUp,
  Brain,
  Play,
  Star,
  Award,
} from 'lucide-react';
import {
  applicationsApi,
  screeningApi,
  interviewSessionsApi,
} from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { EvidenceBadge } from '../../shared/components/EvidenceBadge';
import { EvidenceDrawer, EvidenceDrawerItem } from '../../shared/components/EvidenceDrawer';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';
import { Modal } from '../../shared/components/Modal';
import { PreInterviewScorecardTab } from './PreInterviewScorecardTab';
import { PostInterviewScorecardTab } from './PostInterviewScorecardTab';
import type {
  HiringDecisionType,
  OutcomeStatus,
} from '../../core/types';

export const CandidateWorkspaceView: React.FC = () => {
  const { applicationId } = useParams<{ applicationId: string }>();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<
    'scorecard' | 'post_scorecard' | 'screening' | 'evidence' | 'resume' | 'replay' | 'outcomes' | 'autopsy'
  >('scorecard');

  // Evidence Drawer state
  const [drawerEvidence, setDrawerEvidence] = useState<EvidenceDrawerItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Human Hiring Decision Modal State
  const [isDecisionModalOpen, setIsDecisionModalOpen] = useState(false);
  const [decisionType, setDecisionType] = useState<HiringDecisionType>('SELECTED');
  const [decisionReason, setDecisionReason] = useState('');
  const [decisionSubmitting, setDecisionSubmitting] = useState(false);

  // Post-Hire Outcome Form Modal State
  const [isOutcomeModalOpen, setIsOutcomeModalOpen] = useState(false);
  const [outcomeCapName, setOutcomeCapName] = useState('');
  const [outcomePeriod, setOutcomePeriod] = useState('90_DAYS');
  const [outcomeStatus, setOutcomeStatus] = useState<OutcomeStatus>('MEETS_EXPECTATION');
  const [observedDesc, setObservedDesc] = useState('');
  const [managerNotes, setManagerNotes] = useState('');
  const [outcomeSubmitting, setOutcomeSubmitting] = useState(false);

  // Resume upload state
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeUploading, setResumeUploading] = useState(false);

  // Direct interview & shortlist state
  const [startingInterview, setStartingInterview] = useState(false);
  const [shortlistProcessing, setShortlistProcessing] = useState(false);

  // Load Application core details
  const {
    data: application,
    isLoading: appLoading,
    refetch: refetchApp,
  } = useQuery({
    queryKey: ['application', applicationId],
    queryFn: () => applicationsApi.get(applicationId!),
    enabled: !!applicationId,
  });

  // Load Screening Profile
  const {
    data: screeningProfile,
    isLoading: screeningLoading,
    refetch: refetchScreening,
  } = useQuery({
    queryKey: ['screeningProfile', applicationId],
    queryFn: () => screeningApi.getCandidateScreeningProfile(applicationId!),
    enabled: !!applicationId && activeTab === 'screening',
  });

  // Load Structured Evidence
  const {
    data: evidenceSummary,
    isLoading: evidenceLoading,
    refetch: refetchEvidence,
  } = useQuery({
    queryKey: ['applicationEvidence', applicationId],
    queryFn: () => applicationsApi.getEvidence(applicationId!),
    enabled: !!applicationId && activeTab === 'evidence',
  });

  // Load Decision Replay
  const {
    data: decisionReplay,
    isLoading: replayLoading,
    refetch: refetchReplay,
  } = useQuery({
    queryKey: ['decisionReplay', applicationId],
    queryFn: () => applicationsApi.getDecisionReplay(applicationId!),
    enabled: !!applicationId && activeTab === 'replay',
  });

  // Load Post Hire Outcomes
  const {
    data: outcomesList,
    isLoading: outcomesLoading,
    refetch: refetchOutcomes,
  } = useQuery({
    queryKey: ['postHireOutcomes', applicationId],
    queryFn: () => applicationsApi.listPostHireOutcomes(applicationId!),
    enabled: !!applicationId && activeTab === 'outcomes',
  });

  // Load Hiring Autopsy
  const {
    data: hiringAutopsy,
    isLoading: autopsyLoading,
    refetch: refetchAutopsy,
  } = useQuery({
    queryKey: ['hiringAutopsy', applicationId],
    queryFn: () => applicationsApi.getHiringAutopsy(applicationId!),
    enabled: !!applicationId && activeTab === 'autopsy',
  });

  // Load Candidate Interview Sessions (to link to report if exists)
  const { data: interviewSessions, refetch: refetchSessions } = useQuery({
    queryKey: ['interviewSessions', applicationId],
    queryFn: () => interviewSessionsApi.listByApplication(applicationId!),
    enabled: !!applicationId,
  });

  const latestSession = interviewSessions && interviewSessions.length > 0 ? interviewSessions[interviewSessions.length - 1] : null;

  // Actions
  const handleAnalyzeEvidence = async () => {
    if (!applicationId) return;
    try {
      await applicationsApi.analyzeEvidence(applicationId);
      await refetchEvidence();
    } catch (err: any) {
      alert(err.message || 'Evidence analysis failed');
    }
  };

  const handleUploadResume = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!applicationId || !resumeFile) return;
    setResumeUploading(true);
    try {
      await applicationsApi.uploadResume(applicationId, resumeFile);
      await applicationsApi.processResume(applicationId);
      setResumeFile(null);
      await refetchApp();
      alert('Resume uploaded and processed successfully.');
    } catch (err: any) {
      alert(err.message || 'Failed to upload/process resume');
    } finally {
      setResumeUploading(false);
    }
  };

  const handleSubmitDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!applicationId || !decisionReason.trim()) return;
    setDecisionSubmitting(true);
    try {
      await applicationsApi.recordHiringDecision(applicationId, {
        decision: decisionType,
        decision_reason: decisionReason.trim(),
      });
      setIsDecisionModalOpen(false);
      setDecisionReason('');
      await refetchApp();
      alert('Human hiring decision recorded and persisted.');
    } catch (err: any) {
      alert(err.message || 'Failed to record decision');
    } finally {
      setDecisionSubmitting(false);
    }
  };

  const handleSubmitOutcome = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!applicationId || !outcomeCapName.trim() || !observedDesc.trim()) return;
    setOutcomeSubmitting(true);
    try {
      await applicationsApi.recordPostHireOutcome(applicationId, {
        capability_name: outcomeCapName.trim(),
        outcome_period: outcomePeriod,
        outcome_status: outcomeStatus,
        observed_outcome_description: observedDesc.trim(),
        manager_notes: managerNotes.trim() || undefined,
      });
      setIsOutcomeModalOpen(false);
      setOutcomeCapName('');
      setObservedDesc('');
      setManagerNotes('');
      await refetchOutcomes();
      alert('Post-hire work observation recorded.');
    } catch (err: any) {
      alert(err.message || 'Failed to record post-hire outcome');
    } finally {
      setOutcomeSubmitting(false);
    }
  };

  const openDrawerForSummary = (cap: any) => {
    setDrawerEvidence({
      capability_name: cap.name,
      state: cap.state === 'KNOWN' ? cap.provenance : 'UNKNOWN',
      strength: cap.strength,
      provenance: cap.provenance,
      content: cap.evidence,
      source_type: 'Resume / Candidate Ingestion',
      verification_status: cap.provenance === 'VERIFIED' ? 'Verified' : 'Pending Review',
    });
    setIsDrawerOpen(true);
  };

  const handleStartInterview = async () => {
    if (!applicationId) return;
    setStartingInterview(true);
    try {
      const session = await interviewSessionsApi.create(applicationId);
      navigate(`/interview-room/${session.id}`);
    } catch (err: any) {
      alert(err.message || 'Failed to start interview');
      setStartingInterview(false);
    }
  };

  const handleQuickShortlist = async (decision: 'SHORTLISTED' | 'NOT_SHORTLISTED' | 'HOLD', reason?: string) => {
    if (!applicationId) return;
    setShortlistProcessing(true);
    try {
      await screeningApi.shortlistCandidate(
        applicationId,
        decision,
        reason || (decision === 'SHORTLISTED' ? 'Manually shortlisted by HR' : undefined)
      );
      await Promise.all([refetchApp(), refetchScreening(), refetchSessions()]);
    } catch (err: any) {
      alert(err.message || 'Failed to update candidate shortlist status');
    } finally {
      setShortlistProcessing(false);
    }
  };

  if (appLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <Skeleton height={50} />
        <Skeleton height={140} />
        <Skeleton height={300} />
      </div>
    );
  }

  if (!application) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <h3>Application Not Found</h3>
        <p>This candidate application could not be found.</p>
        <Link to="/screening" className="btn btn-secondary" style={{ marginTop: '1rem' }}>
          Back to Screening
        </Link>
      </div>
    );
  }

  const isShortlisted =
    application.status === 'SHORTLISTED' ||
    application.shortlist_status === 'SHORTLISTED' ||
    application.status === 'INTERVIEW';

  return (
    <div>
      {/* Candidate Header */}
      <PageHeader
        title={`Candidate: ${application.id.slice(0, 8)}...`}
        description={`Application Date: ${new Date(application.applied_at || application.created_at).toLocaleDateString()} • Position ID: ${application.job_id}`}
        badge={<StatusBadge status={application.status} />}
        actions={
          <>
            {isShortlisted && (
              <button
                onClick={handleStartInterview}
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
            )}
            {latestSession && (
              <Link
                to={`/interviews/${latestSession.id}/report`}
                className="btn btn-secondary"
              >
                <ClipboardList size={15} />
                Interview Report
              </Link>
            )}
            <Link
              to={`/candidates/${application.id}/interview-plan`}
              className="btn btn-secondary"
            >
              <Calendar size={15} />
              Interview Plan
            </Link>
            <button
              onClick={() => setIsDecisionModalOpen(true)}
              className="btn btn-primary"
            >
              <Gavel size={15} />
              Make Human Decision
            </button>
          </>
        }
      />

      {/* Navigation Tabs Bar */}
      <div
        style={{
          display: 'flex',
          gap: '0.25rem',
          borderBottom: '1px solid var(--border-base)',
          marginBottom: '1.5rem',
          overflowX: 'auto',
          backgroundColor: '#FFFFFF',
          borderRadius: 'var(--radius-lg) var(--radius-lg) 0 0',
          padding: '0.5rem 0.5rem 0',
        }}
      >
        {[
          { key: 'scorecard', label: 'Pre-Interview Scorecard', icon: ClipboardList },
          { key: 'post_scorecard', label: 'Post-Interview Scorecard', icon: Award },
          { key: 'screening', label: 'Screening Profile', icon: Layers },
          { key: 'evidence', label: 'Capability Evidence', icon: ShieldCheck },
          { key: 'resume', label: 'Extracted Resume', icon: FileText },
          { key: 'replay', label: 'Decision Replay', icon: RotateCcw },
          { key: 'outcomes', label: 'Post-Hire Outcomes', icon: TrendingUp },
          { key: 'autopsy', label: 'Hiring Autopsy', icon: Brain },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.65rem 1rem',
                fontSize: '0.875rem',
                fontWeight: isActive ? 600 : 500,
                color: isActive ? 'var(--primary-700)' : 'var(--text-secondary)',
                borderBottom: isActive ? '2px solid var(--primary-600)' : '2px solid transparent',
                backgroundColor: isActive ? 'var(--primary-50)' : 'transparent',
                borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
                transition: 'all var(--transition-fast)',
                whiteSpace: 'nowrap',
              }}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab 0: Pre-Interview Analytical Scorecard */}
      {activeTab === 'scorecard' && (
        <PreInterviewScorecardTab applicationId={application.id} />
      )}

      {/* Tab: Post-Interview Analytical Scorecard */}
      {activeTab === 'post_scorecard' && (
        <PostInterviewScorecardTab applicationId={application.id} />
      )}

      {/* Tab 1: Screening Profile */}
      {activeTab === 'screening' && (
        <div>
          {screeningLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <Skeleton height={100} />
              <Skeleton height={200} />
            </div>
          ) : !screeningProfile ? (
            <EmptyState
              icon={Layers}
              title="No screening profile generated"
              description="Click 'Run Candidate Screening' to extract requirements against the position blueprint."
              actionText="Run Candidate Screening"
              onAction={async () => {
                await screeningApi.runCandidateScreening(applicationId!);
                await refetchScreening();
              }}
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Summary explanation card */}
              <div className="card" style={{ backgroundColor: '#F8FAFC' }}>
                <h4 style={{ fontSize: '0.95rem', marginBottom: '0.35rem' }}>Screening Analysis Summary</h4>
                <p style={{ fontSize: '0.875rem', lineHeight: 1.6, color: 'var(--text-main)' }}>
                  {screeningProfile.summary_explanation || 'Candidate requirements evaluated against position blueprint.'}
                </p>
                <div style={{ display: 'flex', gap: '1.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Screening Status:</span>{' '}
                    <strong style={{ fontSize: '0.8125rem' }}>{screeningProfile.screening_status}</strong>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Shortlist Status:</span>{' '}
                    <strong style={{ fontSize: '0.8125rem' }}>{screeningProfile.shortlist_status}</strong>
                  </div>
                  {screeningProfile.rank && (
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Dynamic Rank:</span>{' '}
                      <strong style={{ fontSize: '0.8125rem' }}>#{screeningProfile.rank}</strong>
                    </div>
                  )}
                </div>
              </div>

              {/* Human Recruiter Shortlist Gate Card */}
              <div
                className="card"
                style={{
                  border: '1px solid #CBD5E1',
                  backgroundColor: '#FFFFFF',
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Gavel size={18} color="#1D4ED8" />
                    <h4 style={{ fontSize: '1rem', margin: 0, fontWeight: 700 }}>Human Recruiter Shortlist Gate</h4>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Decision:</span>
                    <StatusBadge status={application.shortlist_status || application.status} />
                    {(application.shortlist_reason?.toLowerCase().includes('manually') || application.shortlist_status === 'SHORTLISTED') && (
                      <span
                        style={{
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          padding: '0.15rem 0.5rem',
                          borderRadius: '4px',
                          backgroundColor: '#FEF3C7',
                          color: '#B45309',
                          border: '1px solid #FDE68A',
                        }}
                      >
                        ⭐ Manually Shortlisted
                      </span>
                    )}
                  </div>
                </div>

                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  Shortlisting locks candidate eligibility and makes the candidate immediately interview-ready without requiring AI re-screening.
                </p>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => handleQuickShortlist('SHORTLISTED')}
                    disabled={shortlistProcessing || application.shortlist_status === 'SHORTLISTED'}
                    className="btn btn-sm"
                    style={{
                      backgroundColor: application.shortlist_status === 'SHORTLISTED' ? '#ECFDF5' : '#059669',
                      color: application.shortlist_status === 'SHORTLISTED' ? '#047857' : '#FFFFFF',
                      border: application.shortlist_status === 'SHORTLISTED' ? '1px solid #A7F3D0' : 'none',
                      fontWeight: 600,
                      padding: '0.45rem 0.85rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                    }}
                  >
                    <Star size={13} fill={application.shortlist_status === 'SHORTLISTED' ? '#047857' : '#FFFFFF'} />
                    {application.shortlist_status === 'SHORTLISTED' ? 'Shortlisted' : '⭐ Shortlist Candidate'}
                  </button>

                  <button
                    onClick={() => handleQuickShortlist('NOT_SHORTLISTED')}
                    disabled={shortlistProcessing || application.shortlist_status === 'NOT_SHORTLISTED'}
                    className="btn btn-secondary btn-sm"
                    style={{
                      color: '#DC2626',
                      borderColor: '#FCA5A5',
                      fontWeight: 600,
                      padding: '0.45rem 0.85rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                    }}
                  >
                    <XCircle size={13} />
                    Do Not Shortlist
                  </button>

                  <button
                    onClick={() => handleQuickShortlist('HOLD')}
                    disabled={shortlistProcessing || application.shortlist_status === 'HOLD'}
                    className="btn btn-secondary btn-sm"
                    style={{
                      color: '#D97706',
                      borderColor: '#FDE68A',
                      fontWeight: 600,
                      padding: '0.45rem 0.85rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                    }}
                  >
                    <Clock size={13} />
                    Hold
                  </button>

                  {(application.shortlist_status === 'SHORTLISTED' || application.status === 'SHORTLISTED' || application.status === 'INTERVIEW') && (
                    <button
                      onClick={handleStartInterview}
                      disabled={startingInterview}
                      className="btn btn-sm"
                      style={{
                        backgroundColor: '#1D4ED8',
                        color: '#FFFFFF',
                        border: 'none',
                        fontWeight: 600,
                        padding: '0.45rem 1rem',
                        marginLeft: 'auto',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                      }}
                      title="Directly launch the live AI interview room"
                    >
                      <Play size={13} fill="#FFFFFF" />
                      {startingInterview ? 'Opening Room...' : 'Start Interview Now'}
                    </button>
                  )}
                </div>
              </div>

              {/* Evaluated Requirements Table */}
              <div className="card">
                <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Capability Requirements Evaluation</h3>
                <div className="data-table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Capability</th>
                        <th>Importance</th>
                        <th>Evidence Found</th>
                        <th>Provenance</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {screeningProfile.capability_results.map((res) => (
                        <tr key={res.capability_id}>
                          <td>
                            <strong style={{ fontSize: '0.875rem' }}>{res.capability_name}</strong>
                          </td>
                          <td>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>{res.importance}</span>
                          </td>
                          <td>
                            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                              {res.content || res.unknown_reason || '—'}
                            </span>
                          </td>
                          <td>
                            <EvidenceBadge state={res.provenance || (res.status === 'MET' ? 'DEMONSTRATED' : 'UNKNOWN')} />
                          </td>
                          <td>
                            <StatusBadge status={res.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Capability Evidence */}
      {activeTab === 'evidence' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
            <button onClick={handleAnalyzeEvidence} className="btn btn-secondary btn-sm">
              <Sparkles size={14} />
              Re-Analyze Evidence
            </button>
          </div>

          {evidenceLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <Skeleton height={80} />
              <Skeleton height={80} />
            </div>
          ) : !evidenceSummary || evidenceSummary.capabilities.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="No structured evidence extracted yet"
              description="Click 'Re-Analyze Evidence' to parse uploaded resumes and discovered candidate sources."
              actionText="Analyze Evidence"
              onAction={handleAnalyzeEvidence}
            />
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                gap: '1rem',
              }}
            >
              {evidenceSummary.capabilities.map((cap) => (
                <div
                  key={cap.capability_id}
                  className="card"
                  onClick={() => openDrawerForSummary(cap)}
                  style={{
                    cursor: 'pointer',
                    transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                      <h4 style={{ fontSize: '0.95rem' }}>{cap.name}</h4>
                      <EvidenceBadge state={cap.state === 'KNOWN' ? cap.provenance : 'UNKNOWN'} />
                    </div>
                    <p
                      style={{
                        fontSize: '0.8125rem',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.5,
                        display: '-webkit-box',
                        WebkitLineClamp: 3,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {cap.evidence || 'No specific excerpt recorded.'}
                    </p>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginTop: '1rem',
                      paddingTop: '0.75rem',
                      borderTop: '1px solid var(--border-light)',
                    }}
                  >
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Strength: <strong>{cap.strength}</strong>
                    </span>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        color: 'var(--primary-600)',
                        fontWeight: 600,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.2rem',
                      }}
                    >
                      Inspect Details <ChevronRight size={14} />
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Extracted Resume */}
      {activeTab === 'resume' && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem' }}>Candidate Resume & Submission Document</h3>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                {application.resume_path ? `File: ${application.resume_path}` : 'No resume file attached'}
              </p>
            </div>
            <form onSubmit={handleUploadResume} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                required
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                style={{ fontSize: '0.8125rem' }}
              />
              <button
                type="submit"
                disabled={resumeUploading || !resumeFile}
                className="btn btn-secondary btn-sm"
              >
                {resumeUploading ? 'Uploading...' : 'Upload & Process'}
              </button>
            </form>
          </div>

          <div
            style={{
              backgroundColor: 'var(--bg-app)',
              border: '1px solid var(--border-base)',
              borderRadius: 'var(--radius-md)',
              padding: '1.25rem',
              maxHeight: '500px',
              overflowY: 'auto',
              fontSize: '0.875rem',
              lineHeight: 1.65,
              whiteSpace: 'pre-wrap',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-main)',
            }}
          >
            {application.resume_text || 'No extracted resume text available. Upload a resume file above.'}
          </div>
        </div>
      )}

      {/* Tab 4: Decision Replay */}
      {activeTab === 'replay' && (
        <div>
          {replayLoading ? (
            <Skeleton height={200} />
          ) : !decisionReplay ? (
            <EmptyState
              icon={RotateCcw}
              title="No Decision Replay Available"
              description="Decision replay snapshots are generated when an authorized human decision (SELECTED, REJECTED, ON_HOLD) is recorded."
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Limitation Notice */}
              <div
                style={{
                  padding: '0.875rem 1rem',
                  backgroundColor: '#FFFBEB',
                  border: '1px solid #FDE68A',
                  borderRadius: 'var(--radius-md)',
                  color: '#92400E',
                  fontSize: '0.8125rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <AlertTriangle size={18} />
                <span>
                  <strong>Historical Reconstruction Notice:</strong> This view reconstructs the exact state of candidate evidence, screening outcomes, and interview findings available at decision time.
                </span>
              </div>

              {/* Decision Context Card */}
              <div className="card">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <h3 style={{ fontSize: '1.1rem' }}>Recorded Hiring Decision</h3>
                  <StatusBadge status={decisionReplay.decision_context.decision} />
                </div>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-main)', lineHeight: 1.6, marginBottom: '1rem', backgroundColor: 'var(--bg-subtle)', padding: '0.875rem', borderRadius: 'var(--radius-md)' }}>
                  <strong>Human Rationale:</strong> "{decisionReplay.decision_context.decision_reason}"
                </div>
                <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  <div>
                    Decided by: <strong>{decisionReplay.decision_context.decided_by_name}</strong>
                  </div>
                  <div>
                    Timestamp: <strong>{new Date(decisionReplay.decision_context.decided_at).toLocaleString()}</strong>
                  </div>
                  <div>
                    Reconstructed at: <strong>{new Date(decisionReplay.reconstructed_at).toLocaleTimeString()}</strong>
                  </div>
                </div>
              </div>

              {/* Historical Evidence Snapshot */}
              <div className="card">
                <h4 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>Evidence Snapshot at Decision Time</h4>
                <div className="data-table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Capability</th>
                        <th>Historical State</th>
                        <th>Evidence Excerpt</th>
                        <th>Provenance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {decisionReplay.evidence_context.map((e, idx) => (
                        <tr key={idx}>
                          <td><strong>{e.capability_name}</strong></td>
                          <td><EvidenceBadge state={e.state} /></td>
                          <td><span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{e.evidence_excerpt || '—'}</span></td>
                          <td><span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>{e.provenance_summary || 'CLAIM'}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Post-Hire Outcomes */}
      {activeTab === 'outcomes' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem' }}>Post-Hire Work Execution Tracking</h3>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                Record objective, fact-based performance observations across 30/60/90-day intervals.
              </p>
            </div>
            <button
              onClick={() => setIsOutcomeModalOpen(true)}
              className="btn btn-primary btn-sm"
            >
              <TrendingUp size={14} />
              Record Work Outcome
            </button>
          </div>

          {outcomesLoading ? (
            <Skeleton height={150} />
          ) : !outcomesList || outcomesList.outcomes.length === 0 ? (
            <EmptyState
              icon={TrendingUp}
              title="No post-hire outcomes recorded"
              description="Record objective capability performance observations after onboarding to enable full hiring autopsy loop."
              actionText="Record First Outcome"
              onAction={() => setIsOutcomeModalOpen(true)}
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {outcomesList.outcomes.map((outcome) => (
                <div key={outcome.id} className="card">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <h4 style={{ fontSize: '1rem' }}>{outcome.capability_name}</h4>
                      <span style={{ fontSize: '0.75rem', padding: '0.15rem 0.45rem', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-base)', fontWeight: 600 }}>
                        {outcome.outcome_period}
                      </span>
                    </div>
                    <StatusBadge status={outcome.outcome_status} />
                  </div>
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-main)', lineHeight: 1.6, marginBottom: '0.75rem' }}>
                    {outcome.observed_outcome_description}
                  </p>
                  {outcome.manager_notes && (
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '0.5rem' }}>
                      Manager notes: {outcome.manager_notes}
                    </div>
                  )}
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', gap: '1rem' }}>
                    <span>Recorded by: <strong>{outcome.recorded_by_name}</strong></span>
                    <span>Date: <strong>{new Date(outcome.recorded_at).toLocaleDateString()}</strong></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 6: Hiring Autopsy */}
      {activeTab === 'autopsy' && (
        <div>
          {autopsyLoading ? (
            <Skeleton height={250} />
          ) : !hiringAutopsy ? (
            <EmptyState
              icon={Brain}
              title="Hiring Autopsy Incomplete"
              description="Hiring Autopsy compares pre-hire candidate claims against post-hire execution outcomes. Record at least one post-hire outcome to view."
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Capability Comparison Matrix: Fact-based delta */}
              <div className="card">
                <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>
                  Pre-Hire Expectation vs Post-Hire Work Execution (Fact-Based)
                </h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                  Factual, objective alignment between initial resume claim, interview demonstration, and observed job performance.
                </p>
                <div className="data-table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Capability</th>
                        <th>Pre-Hire Evidence</th>
                        <th>Interview Demonstrated</th>
                        <th>Post-Hire Outcome</th>
                        <th>Observed Delta</th>
                      </tr>
                    </thead>
                    <tbody>
                      {hiringAutopsy.capability_comparison.map((comp, idx) => (
                        <tr key={idx}>
                          <td><strong>{comp.capability_name}</strong></td>
                          <td><EvidenceBadge state={comp.pre_hire_evidence_state} /></td>
                          <td><span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>{comp.interview_demonstration_state}</span></td>
                          <td>{comp.post_hire_outcome_status ? <StatusBadge status={comp.post_hire_outcome_status} /> : <span style={{ color: 'var(--text-muted)' }}>No data</span>}</td>
                          <td><span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{comp.outcome_delta_observation}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* AI Improvement Suggestions: Clearly Marked Advisory */}
              {hiringAutopsy.ai_improvement_suggestions.length > 0 && (
                <div className="card" style={{ borderColor: 'var(--primary-200)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <Brain size={20} color="var(--primary-600)" />
                    <h3 style={{ fontSize: '1.1rem' }}>AI Hiring Process Improvement Suggestions</h3>
                  </div>
                  <div
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: '#B45309',
                      backgroundColor: '#FFFBEB',
                      padding: '0.3rem 0.6rem',
                      borderRadius: 'var(--radius-sm)',
                      display: 'inline-block',
                      marginBottom: '1rem',
                      border: '1px solid #FDE68A',
                    }}
                  >
                    ADVISORY ONLY — Suggestions never modify active criteria or candidate decisions automatically.
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {hiringAutopsy.ai_improvement_suggestions.map((sugg) => (
                      <div
                        key={sugg.suggestion_id}
                        style={{
                          backgroundColor: 'var(--bg-app)',
                          border: '1px solid var(--border-base)',
                          borderRadius: 'var(--radius-md)',
                          padding: '0.875rem 1rem',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                            {sugg.affected_capability}: {sugg.action_type.replace('_', ' ')}
                          </span>
                          <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--primary-700)', backgroundColor: 'var(--primary-100)', padding: '0.15rem 0.45rem', borderRadius: 'var(--radius-full)' }}>
                            {sugg.confidence_strength}
                          </span>
                        </div>
                        <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                          <strong>Observed Pattern:</strong> {sugg.observed_pattern}
                        </p>
                        <p style={{ fontSize: '0.8125rem', color: 'var(--text-main)' }}>
                          <strong>Suggested Improvement:</strong> {sugg.suggested_improvement}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Human Hiring Decision Modal */}
      <Modal
        isOpen={isDecisionModalOpen}
        onClose={() => setIsDecisionModalOpen(false)}
        title="Record Human Hiring Decision"
        subtitle="Mandatory human governance gate. Requires evidence-grounded justification."
      >
        <form onSubmit={handleSubmitDecision} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Final Decision *
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
              {[
                { type: 'SELECTED', label: 'Selected', color: '#059669' },
                { type: 'ON_HOLD', label: 'On Hold', color: '#D97706' },
                { type: 'REJECTED', label: 'Rejected', color: '#DC2626' },
              ].map((d) => (
                <button
                  type="button"
                  key={d.type}
                  onClick={() => setDecisionType(d.type as HiringDecisionType)}
                  style={{
                    padding: '0.65rem',
                    borderRadius: 'var(--radius-md)',
                    border: decisionType === d.type ? `2px solid ${d.color}` : '1px solid var(--border-base)',
                    backgroundColor: decisionType === d.type ? 'var(--bg-subtle)' : '#FFFFFF',
                    fontWeight: 600,
                    fontSize: '0.875rem',
                    color: decisionType === d.type ? d.color : 'var(--text-main)',
                  }}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Human Rationale & Justification (min. 5 characters) *
            </label>
            <textarea
              required
              rows={4}
              minLength={5}
              placeholder="Detail reasons for this decision based on demonstrated evidence, interview performance, or capability gaps..."
              style={{ width: '100%' }}
              value={decisionReason}
              onChange={(e) => setDecisionReason(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsDecisionModalOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={decisionSubmitting || decisionReason.trim().length < 5}
              className="btn btn-primary"
            >
              {decisionSubmitting ? 'Recording Decision...' : 'Commit Decision'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Post-Hire Outcome Modal */}
      <Modal
        isOpen={isOutcomeModalOpen}
        onClose={() => setIsOutcomeModalOpen(false)}
        title="Record Post-Hire Work Execution Observation"
        subtitle="Objective post-onboarding capability observation"
      >
        <form onSubmit={handleSubmitOutcome} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Evaluated Capability *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Distributed Consensus"
              style={{ width: '100%' }}
              value={outcomeCapName}
              onChange={(e) => setOutcomeCapName(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Observation Window
              </label>
              <select
                style={{ width: '100%' }}
                value={outcomePeriod}
                onChange={(e) => setOutcomePeriod(e.target.value)}
              >
                <option value="30_DAYS">30 Days</option>
                <option value="60_DAYS">60 Days</option>
                <option value="90_DAYS">90 Days</option>
                <option value="PROBATION">Probation</option>
                <option value="ANNUAL">Annual</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Performance Rating
              </label>
              <select
                style={{ width: '100%' }}
                value={outcomeStatus}
                onChange={(e) => setOutcomeStatus(e.target.value as OutcomeStatus)}
              >
                <option value="MEETS_EXPECTATION">Meets Expectation</option>
                <option value="PARTIALLY_MEETS_EXPECTATION">Partially Meets Expectation</option>
                <option value="NEEDS_DEVELOPMENT">Needs Development</option>
                <option value="INSUFFICIENT_OBSERVATION">Insufficient Observation</option>
              </select>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Factual Work Observation *
            </label>
            <textarea
              required
              rows={4}
              minLength={5}
              placeholder="Describe actual work deliverable, PR, or architecture contribution observed..."
              style={{ width: '100%' }}
              value={observedDesc}
              onChange={(e) => setObservedDesc(e.target.value)}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Manager Notes (Optional)
            </label>
            <input
              type="text"
              placeholder="Additional internal observations..."
              style={{ width: '100%' }}
              value={managerNotes}
              onChange={(e) => setManagerNotes(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsOutcomeModalOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={outcomeSubmitting || observedDesc.trim().length < 5}
              className="btn btn-primary"
            >
              {outcomeSubmitting ? 'Recording...' : 'Save Observation'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Inspectable Evidence Drawer */}
      <EvidenceDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        evidence={drawerEvidence}
      />
    </div>
  );
};
