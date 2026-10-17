import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Award,
  ShieldCheck,
  HelpCircle,
  AlertTriangle,
  CheckCircle2,
  FileText,
  RotateCw,
  TrendingUp,
  ArrowRight,
  Info,
  Clock,
  Search,
  MessageSquare,
  Sparkles,
} from 'lucide-react';
import { applicationsApi } from '../../core/api/endpoints';
import type {
  PostInterviewScorecard,
  PostInterviewCapabilityScorecardItem,
  PostInterviewChangeType,
  PreInterviewCapabilityStatus,
} from '../../core/types';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';

interface PostInterviewScorecardTabProps {
  applicationId: string;
}

export const PostInterviewScorecardTab: React.FC<PostInterviewScorecardTabProps> = ({
  applicationId,
}) => {
  const queryClient = useQueryClient();
  const [filterType, setFilterType] = useState<'ALL' | PostInterviewChangeType>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch Post-Interview Scorecard
  const {
    data: scorecard,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['postInterviewScorecard', applicationId],
    queryFn: () => applicationsApi.getPostInterviewScorecard(applicationId),
    enabled: !!applicationId,
  });

  // Refresh Mutation
  const refreshMutation = useMutation({
    mutationFn: () => applicationsApi.refreshPostInterviewScorecard(applicationId),
    onSuccess: (updated) => {
      queryClient.setQueryData(['postInterviewScorecard', applicationId], updated);
    },
  });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <Skeleton height={90} />
        <Skeleton height={140} />
        <Skeleton height={280} />
      </div>
    );
  }

  if (isError || !scorecard) {
    const errorMsg = (error as any)?.message || '';
    const isIncomplete = errorMsg.toLowerCase().includes('completed') || errorMsg.toLowerCase().includes('status');

    return (
      <EmptyState
        icon={Award}
        title={isIncomplete ? 'Interview Session Not Completed' : 'Scorecard Unavailable'}
        description={
          isIncomplete
            ? 'The post-interview analytical scorecard is generated once the candidate completes their live interview session.'
            : errorMsg || 'Could not load post-interview analytical scorecard.'
        }
        actionText={isIncomplete ? undefined : 'Generate Post-Interview Scorecard'}
        onAction={isIncomplete ? undefined : () => refreshMutation.mutate()}
      />
    );
  }

  // Filter capabilities
  const filteredCapabilities = scorecard.capabilities.filter((cap) => {
    const matchesFilter = filterType === 'ALL' || cap.change_type === filterType;
    const matchesSearch =
      !searchQuery.trim() ||
      cap.capability_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (cap.requirement_description || '').toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const getChangeBadge = (changeType: PostInterviewChangeType) => {
    switch (changeType) {
      case 'STRENGTHENED':
        return {
          bg: '#ECFDF5',
          text: '#065F46',
          border: '#A7F3D0',
          label: 'Strengthened in Interview',
          icon: TrendingUp,
        };
      case 'CONFIRMED':
        return {
          bg: '#EFF6FF',
          text: '#1E40AF',
          border: '#BFDBFE',
          label: 'Baseline Confirmed',
          icon: CheckCircle2,
        };
      case 'UNVERIFIED_CLAIM':
        return {
          bg: '#FFFBEB',
          text: '#92400E',
          border: '#FDE68A',
          label: 'Unverified Claim (Superficial)',
          icon: Clock,
        };
      case 'REMAINED_UNKNOWN':
        return {
          bg: '#F8FAFC',
          text: '#475569',
          border: '#E2E8F0',
          label: 'Untested (Remained Unknown)',
          icon: HelpCircle,
        };
      case 'CONTRADICTORY':
        return {
          bg: '#FEF2F2',
          text: '#991B1B',
          border: '#FECACA',
          label: 'Contradiction Detected',
          icon: AlertTriangle,
        };
      default:
        return {
          bg: '#F1F5F9',
          text: '#475569',
          border: '#E2E8F0',
          label: changeType,
          icon: Info,
        };
    }
  };

  const getStatusBadgeStyle = (status: PreInterviewCapabilityStatus) => {
    switch (status) {
      case 'SUPPORTED':
        return {
          bg: 'var(--evidence-demonstrated-bg)',
          text: 'var(--evidence-demonstrated-text)',
          border: 'var(--evidence-demonstrated-border)',
          label: 'Supported',
        };
      case 'PARTIAL':
        return {
          bg: 'var(--evidence-claim-bg)',
          text: 'var(--evidence-claim-text)',
          border: 'var(--evidence-claim-border)',
          label: 'Partial',
        };
      case 'UNKNOWN':
        return {
          bg: 'var(--evidence-unknown-bg)',
          text: 'var(--evidence-unknown-text)',
          border: 'var(--evidence-unknown-border)',
          label: 'Unknown',
        };
      case 'CONTRADICTORY':
        return {
          bg: '#FEF3C7',
          text: '#92400E',
          border: '#FCD34D',
          label: 'Contradictory',
        };
      default:
        return {
          bg: '#F1F5F9',
          text: '#475569',
          border: '#E2E8F0',
          label: status,
        };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* 1. Core Principle Banner */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.75rem',
          padding: '0.875rem 1.15rem',
          backgroundColor: '#F0FDF4',
          border: '1px solid #BBF7D0',
          borderRadius: 'var(--radius-md)',
          color: '#166534',
        }}
      >
        <Info size={20} style={{ flexShrink: 0, marginTop: '2px', color: '#15803D' }} />
        <div style={{ fontSize: '0.8125rem', lineHeight: 1.55 }}>
          <strong>Core Assessment Principle:</strong> The pre-interview scorecard serves as the immutable
          baseline. Untested capabilities remain <strong style={{ color: '#0F172A' }}>UNKNOWN</strong> without
          penalty (absence of questioning is not candidate failure). AI assists HR; all hiring decisions
          require human review.
        </div>
      </div>

      {/* 2. Executive Context Card with Progression Delta */}
      <div
        className="card"
        style={{
          backgroundColor: '#FFFFFF',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.25rem 1.5rem',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: '1rem',
            borderBottom: '1px solid var(--border-light)',
            paddingBottom: '1rem',
            marginBottom: '1rem',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 600, color: 'var(--text-main)', margin: 0 }}>
                Post-Interview Analytical Scorecard
              </h3>
              <span
                style={{
                  fontSize: '0.75rem',
                  padding: '0.15rem 0.5rem',
                  backgroundColor: '#ECFDF5',
                  color: '#065F46',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 600,
                  border: '1px solid #A7F3D0',
                }}
              >
                v{scorecard.scorecard_version}
              </span>
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              Position: <strong>{scorecard.job_title}</strong> • Candidate: <strong>{scorecard.candidate_name}</strong>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Baseline: {new Date(scorecard.baseline_assessment_timestamp).toLocaleDateString()} • Post-Interview:{' '}
              {new Date(scorecard.assessment_timestamp).toLocaleDateString()}
            </div>
          </div>

          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
            className="btn btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8125rem' }}
          >
            <RotateCw
              size={14}
              style={{
                animation: refreshMutation.isPending ? 'spin 1s linear infinite' : 'none',
              }}
            />
            {refreshMutation.isPending ? 'Re-evaluating...' : 'Refresh Scorecard'}
          </button>
        </div>

        {/* Readiness Progression Row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem',
            alignItems: 'center',
          }}
        >
          {/* Readiness Progression Comparison Card */}
          <div
            style={{
              padding: '0.875rem 1rem',
              backgroundColor: 'var(--bg-app)',
              border: '1px solid var(--border-base)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                EVIDENCE READINESS
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontSize: '1.1rem', color: 'var(--text-muted)', fontWeight: 500 }}>
                  {scorecard.baseline_readiness_score}%
                </span>
                <ArrowRight size={14} style={{ color: 'var(--text-muted)' }} />
                <strong
                  style={{
                    fontSize: '1.4rem',
                    fontWeight: 700,
                    color: scorecard.post_interview_readiness_score >= 70 ? '#065F46' : '#1E40AF',
                  }}
                >
                  {scorecard.post_interview_readiness_score}%
                </strong>
                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.1rem 0.4rem',
                    borderRadius: 'var(--radius-xs)',
                    backgroundColor: scorecard.readiness_change_delta >= 0 ? '#ECFDF5' : '#FEF2F2',
                    color: scorecard.readiness_change_delta >= 0 ? '#065F46' : '#991B1B',
                  }}
                >
                  {scorecard.readiness_change_delta >= 0 ? `+${scorecard.readiness_change_delta}%` : `${scorecard.readiness_change_delta}%`}
                </span>
              </div>
            </div>

            <div
              style={{
                width: '100%',
                height: '6px',
                backgroundColor: 'var(--border-base)',
                borderRadius: 'var(--radius-full)',
                marginTop: '0.5rem',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, scorecard.post_interview_readiness_score))}%`,
                  height: '100%',
                  backgroundColor: scorecard.post_interview_readiness_score >= 70 ? '#10B981' : '#3B82F6',
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
            <p style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
              {scorecard.score_explanation}
            </p>
          </div>

          {/* Metric 1: Strengthened */}
          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: '#ECFDF5',
              border: '1px solid #A7F3D0',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: '#065F46', fontWeight: 600 }}>
              STRENGTHENED IN INTERVIEW
            </div>
            <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#065F46' }}>
              +{scorecard.capabilities_strengthened_count}
            </div>
            <div style={{ fontSize: '0.6875rem', color: '#065F46', marginTop: '0.15rem' }}>
              Demonstrated live competence
            </div>
          </div>

          {/* Metric 2: Supported Total */}
          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--evidence-demonstrated-bg)',
              border: '1px solid var(--evidence-demonstrated-border)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--evidence-demonstrated-text)', fontWeight: 600 }}>
              SUPPORTED TOTAL
            </div>
            <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--evidence-demonstrated-text)' }}>
              {scorecard.supported_count}{' '}
              <span style={{ fontSize: '0.8125rem', fontWeight: 500 }}>/ {scorecard.total_capabilities}</span>
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--evidence-demonstrated-text)', marginTop: '0.15rem' }}>
              Verified or demonstrated
            </div>
          </div>

          {/* Metric 3: Remaining Unknowns */}
          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--evidence-unknown-bg)',
              border: '1px solid var(--evidence-unknown-border)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--evidence-unknown-text)', fontWeight: 600 }}>
              REMAINING UNKNOWNS
            </div>
            <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--evidence-unknown-text)' }}>
              {scorecard.unknown_count}{' '}
              <span style={{ fontSize: '0.8125rem', fontWeight: 500 }}>/ {scorecard.total_capabilities}</span>
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--evidence-unknown-text)', marginTop: '0.15rem' }}>
              Untested during interview
            </div>
          </div>

          {/* Metric 4: Contradictory */}
          {scorecard.contradictory_count > 0 && (
            <div
              style={{
                padding: '0.75rem 1rem',
                backgroundColor: '#FEF2F2',
                border: '1px solid #FECACA',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div style={{ fontSize: '0.75rem', color: '#991B1B', fontWeight: 600 }}>
                CONTRADICTIONS
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#991B1B' }}>
                {scorecard.contradictory_count}
              </div>
              <div style={{ fontSize: '0.6875rem', color: '#991B1B', marginTop: '0.15rem' }}>
                Requires human review
              </div>
            </div>
          )}
        </div>

        {/* Executive Summary */}
        <div style={{ marginTop: '1rem', fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.55 }}>
          <strong>Executive Assessment Summary: </strong>
          {scorecard.executive_summary}
        </div>
      </div>

      {/* 3. Filter Chips & Search Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {[
            { id: 'ALL', label: `All Capabilities (${scorecard.total_capabilities})` },
            { id: 'STRENGTHENED', label: `Strengthened (+${scorecard.capabilities_strengthened_count})` },
            { id: 'CONFIRMED', label: 'Confirmed Baseline' },
            { id: 'UNVERIFIED_CLAIM', label: `Unverified Claims (${scorecard.partial_count})` },
            { id: 'REMAINED_UNKNOWN', label: `Untested (${scorecard.unknown_count})` },
            ...(scorecard.contradictory_count > 0
              ? [{ id: 'CONTRADICTORY', label: `Contradictions (${scorecard.contradictory_count})` }]
              : []),
          ].map((tab) => {
            const isSelected = filterType === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setFilterType(tab.id as any)}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.75rem',
                  fontWeight: isSelected ? 600 : 500,
                  borderRadius: 'var(--radius-full)',
                  border: isSelected ? '1px solid var(--primary-600)' : '1px solid var(--border-base)',
                  backgroundColor: isSelected ? 'var(--primary-50)' : '#FFFFFF',
                  color: isSelected ? 'var(--primary-700)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div style={{ position: 'relative', minWidth: '220px' }}>
          <Search
            size={14}
            style={{
              position: 'absolute',
              left: '0.75rem',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-muted)',
            }}
          />
          <input
            type="text"
            placeholder="Search capabilities..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '0.4rem 0.75rem 0.4rem 2rem',
              fontSize: '0.8125rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-base)',
              backgroundColor: '#FFFFFF',
              color: 'var(--text-main)',
            }}
          />
        </div>
      </div>

      {/* 4. Capability-by-Capability Comparison Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {filteredCapabilities.length === 0 ? (
          <div
            className="card"
            style={{
              textAlign: 'center',
              padding: '2.5rem',
              color: 'var(--text-muted)',
              backgroundColor: '#FFFFFF',
            }}
          >
            <p style={{ fontSize: '0.875rem' }}>No capabilities match the current filter selection.</p>
          </div>
        ) : (
          filteredCapabilities.map((cap) => {
            const changeBadge = getChangeBadge(cap.change_type);
            const ChangeIcon = changeBadge.icon;
            const origStyle = getStatusBadgeStyle(cap.original_status);
            const updatedStyle = getStatusBadgeStyle(cap.updated_status);

            return (
              <div
                key={cap.capability_id}
                className="card"
                style={{
                  backgroundColor: '#FFFFFF',
                  border: `1px solid ${changeBadge.border}`,
                  borderRadius: 'var(--radius-lg)',
                  padding: '1.25rem 1.5rem',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                {/* Header: Name + Change Badge */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    gap: '1rem',
                    flexWrap: 'wrap',
                    marginBottom: '0.75rem',
                  }}
                >
                  <div style={{ flex: 1, minWidth: '260px' }}>
                    <h4 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-main)', margin: 0 }}>
                      {cap.capability_name}
                    </h4>
                    {cap.requirement_description && (
                      <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                        {cap.requirement_description}
                      </p>
                    )}
                  </div>

                  {/* Change Analysis Badge */}
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      padding: '0.25rem 0.65rem',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      borderRadius: 'var(--radius-full)',
                      backgroundColor: changeBadge.bg,
                      color: changeBadge.text,
                      border: `1px solid ${changeBadge.border}`,
                    }}
                  >
                    <ChangeIcon size={14} />
                    {changeBadge.label}
                  </span>
                </div>

                {/* Change Summary Callout */}
                <div
                  style={{
                    padding: '0.65rem 0.85rem',
                    backgroundColor: changeBadge.bg,
                    borderRadius: 'var(--radius-md)',
                    border: `1px solid ${changeBadge.border}`,
                    fontSize: '0.8125rem',
                    color: changeBadge.text,
                    lineHeight: 1.5,
                    marginBottom: '1rem',
                  }}
                >
                  <strong>Assessment Evolution: </strong>
                  {cap.change_summary}
                </div>

                {/* Dual Comparison Columns: Baseline vs Post-Interview */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                    gap: '1rem',
                    marginBottom: '1rem',
                  }}
                >
                  {/* Left Column: Pre-Interview Baseline */}
                  <div
                    style={{
                      padding: '0.85rem 1rem',
                      backgroundColor: 'var(--bg-app)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-base)',
                    }}
                  >
                    <div
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        color: 'var(--text-muted)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                        marginBottom: '0.5rem',
                        display: 'flex',
                        justifyContent: 'space-between',
                      }}
                    >
                      <span>PRE-INTERVIEW BASELINE</span>
                      <span
                        style={{
                          padding: '0.1rem 0.4rem',
                          backgroundColor: origStyle.bg,
                          color: origStyle.text,
                          borderRadius: 'var(--radius-xs)',
                          border: `1px solid ${origStyle.border}`,
                        }}
                      >
                        {origStyle.label} ({cap.original_confidence})
                      </span>
                    </div>

                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                      {cap.original_rationale}
                    </div>

                    {cap.original_evidence.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                        {cap.original_evidence.map((ev, evIdx) => (
                          <div
                            key={evIdx}
                            style={{
                              padding: '0.4rem 0.6rem',
                              backgroundColor: '#FFFFFF',
                              borderRadius: 'var(--radius-xs)',
                              border: '1px solid var(--border-base)',
                              fontSize: '0.75rem',
                            }}
                          >
                            <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                              [{ev.source_type}] {ev.source_reference}:
                            </span>{' '}
                            <span style={{ fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                              "{ev.excerpt}"
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        No pre-interview evidence documented.
                      </div>
                    )}
                  </div>

                  {/* Right Column: Live Interview Evidence */}
                  <div
                    style={{
                      padding: '0.85rem 1rem',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid #BAE6FD',
                      backgroundColor: '#F0F9FF',
                    }}
                  >
                    <div
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        color: '#0369A1',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                        marginBottom: '0.5rem',
                        display: 'flex',
                        justifyContent: 'space-between',
                      }}
                    >
                      <span>POST-INTERVIEW ASSESSMENT</span>
                      <span
                        style={{
                          padding: '0.1rem 0.4rem',
                          backgroundColor: updatedStyle.bg,
                          color: updatedStyle.text,
                          borderRadius: 'var(--radius-xs)',
                          border: `1px solid ${updatedStyle.border}`,
                        }}
                      >
                        {updatedStyle.label} ({cap.updated_confidence})
                      </span>
                    </div>

                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                      {cap.updated_rationale}
                    </div>

                    {cap.interview_evidence.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                        {cap.interview_evidence.map((ie, ieIdx) => (
                          <div
                            key={ieIdx}
                            style={{
                              padding: '0.5rem 0.65rem',
                              backgroundColor: '#FFFFFF',
                              borderRadius: 'var(--radius-xs)',
                              border: '1px solid #BAE6FD',
                              fontSize: '0.75rem',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                              <span style={{ fontWeight: 600, color: '#0369A1' }}>Q: {ie.question_text}</span>
                              <span
                                style={{
                                  fontSize: '0.6875rem',
                                  fontWeight: 700,
                                  padding: '0.05rem 0.35rem',
                                  backgroundColor: ie.evaluation_quality === 'SUFFICIENT' ? '#ECFDF5' : '#FFFBEB',
                                  color: ie.evaluation_quality === 'SUFFICIENT' ? '#065F46' : '#92400E',
                                  borderRadius: 'var(--radius-xs)',
                                }}
                              >
                                {ie.evaluation_quality}
                              </span>
                            </div>
                            {ie.candidate_answer_excerpt && (
                              <blockquote
                                style={{
                                  margin: '0.25rem 0',
                                  padding: '0.25rem 0.5rem',
                                  backgroundColor: '#F8FAFC',
                                  borderLeft: '2px solid #3B82F6',
                                  color: 'var(--text-main)',
                                }}
                              >
                                "{ie.candidate_answer_excerpt}"
                              </blockquote>
                            )}
                            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                              <strong>Finding:</strong> {ie.evaluation_summary}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.75rem', color: '#64748B', fontStyle: 'italic' }}>
                        No questions asked for this capability during this interview session.
                      </div>
                    )}
                  </div>
                </div>

                {/* Remaining Uncertainties & Recommended Follow-Up */}
                {cap.remaining_uncertainties && (
                  <div
                    style={{
                      padding: '0.45rem 0.75rem',
                      backgroundColor: '#FFFBEB',
                      border: '1px solid #FDE68A',
                      borderRadius: 'var(--radius-xs)',
                      fontSize: '0.75rem',
                      color: '#92400E',
                      marginBottom: '0.5rem',
                    }}
                  >
                    <strong>Remaining Uncertainty:</strong> {cap.remaining_uncertainties}
                  </div>
                )}

                {cap.recommended_follow_up && (
                  <div
                    style={{
                      padding: '0.45rem 0.75rem',
                      backgroundColor: '#F8FAFC',
                      border: '1px solid var(--border-base)',
                      borderRadius: 'var(--radius-xs)',
                      fontSize: '0.75rem',
                      color: 'var(--text-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        padding: '0.1rem 0.35rem',
                        backgroundColor: '#E0E7FF',
                        color: '#4338CA',
                        borderRadius: 'var(--radius-xs)',
                      }}
                    >
                      {cap.recommended_follow_up.action_type}
                    </span>
                    <span>{cap.recommended_follow_up.guidance}</span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* 5. Evaluator Notice Footer */}
      <div
        style={{
          padding: '0.85rem 1.15rem',
          backgroundColor: '#F8FAFC',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-md)',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
          lineHeight: 1.5,
          textAlign: 'center',
        }}
      >
        {scorecard.human_review_notice}
      </div>
    </div>
  );
};
