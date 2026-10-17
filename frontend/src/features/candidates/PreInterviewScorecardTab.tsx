import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ShieldCheck,
  HelpCircle,
  AlertTriangle,
  CheckCircle2,
  FileText,
  RotateCw,
  Sparkles,
  ExternalLink,
  MessageSquare,
  Compass,
  Info,
  Clock,
  Layers,
  Search,
} from 'lucide-react';
import { applicationsApi } from '../../core/api/endpoints';
import type {
  PreInterviewScorecard,
  CapabilityScorecardItem,
  PreInterviewCapabilityStatus,
} from '../../core/types';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';

interface PreInterviewScorecardTabProps {
  applicationId: string;
}

export const PreInterviewScorecardTab: React.FC<PreInterviewScorecardTabProps> = ({
  applicationId,
}) => {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<'ALL' | PreInterviewCapabilityStatus>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch Scorecard
  const {
    data: scorecard,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['preInterviewScorecard', applicationId],
    queryFn: () => applicationsApi.getPreInterviewScorecard(applicationId),
    enabled: !!applicationId,
  });

  // Refresh Mutation
  const refreshMutation = useMutation({
    mutationFn: () => applicationsApi.refreshPreInterviewScorecard(applicationId),
    onSuccess: (updated) => {
      queryClient.setQueryData(['preInterviewScorecard', applicationId], updated);
    },
  });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <Skeleton height={90} />
        <Skeleton height={140} />
        <Skeleton height={260} />
      </div>
    );
  }

  if (isError || !scorecard) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Scorecard Unavailable"
        description={
          (error as any)?.message ||
          'Could not load pre-interview analytical scorecard for this candidate application.'
        }
        actionText="Generate Pre-Interview Scorecard"
        onAction={() => refreshMutation.mutate()}
      />
    );
  }

  // Filter capabilities
  const filteredCapabilities = scorecard.capabilities.filter((cap) => {
    const matchesFilter = statusFilter === 'ALL' || cap.status === statusFilter;
    const matchesSearch =
      !searchQuery.trim() ||
      cap.capability_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (cap.requirement_description || '').toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const getStatusBadgeStyle = (status: PreInterviewCapabilityStatus) => {
    switch (status) {
      case 'SUPPORTED':
        return {
          bg: 'var(--evidence-demonstrated-bg)',
          text: 'var(--evidence-demonstrated-text)',
          border: 'var(--evidence-demonstrated-border)',
          label: 'Supported',
          icon: CheckCircle2,
        };
      case 'PARTIAL':
        return {
          bg: 'var(--evidence-claim-bg)',
          text: 'var(--evidence-claim-text)',
          border: 'var(--evidence-claim-border)',
          label: 'Partial Evidence',
          icon: FileText,
        };
      case 'UNKNOWN':
        return {
          bg: 'var(--evidence-unknown-bg)',
          text: 'var(--evidence-unknown-text)',
          border: 'var(--evidence-unknown-border)',
          label: 'Unknown (Missing)',
          icon: HelpCircle,
        };
      case 'CONTRADICTORY':
        return {
          bg: '#FEF3C7',
          text: '#92400E',
          border: '#FCD34D',
          label: 'Contradictory',
          icon: AlertTriangle,
        };
      default:
        return {
          bg: '#F1F5F9',
          text: '#475569',
          border: '#E2E8F0',
          label: status,
          icon: HelpCircle,
        };
    }
  };

  const getImportanceBadge = (importance?: string | null) => {
    const imp = (importance || 'MEDIUM').toUpperCase();
    let bg = '#F1F5F9';
    let text = '#475569';
    let border = '#E2E8F0';

    if (imp === 'CRITICAL') {
      bg = '#FEE2E2';
      text = '#991B1B';
      border = '#FCA5A5';
    } else if (imp === 'HIGH') {
      bg = '#FEF3C7';
      text = '#92400E';
      border = '#FCD34D';
    } else if (imp === 'MEDIUM') {
      bg = '#E0F2FE';
      text = '#075985';
      border = '#BAE6FD';
    }

    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          padding: '0.15rem 0.5rem',
          fontSize: '0.6875rem',
          fontWeight: 700,
          borderRadius: 'var(--radius-xs)',
          backgroundColor: bg,
          color: text,
          border: `1px solid ${border}`,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        {imp}
      </span>
    );
  };

  const getConfidencePill = (conf: string) => {
    let color = '#64748B';
    let bg = '#F8FAFC';
    if (conf === 'HIGH') {
      color = '#065F46';
      bg = '#ECFDF5';
    } else if (conf === 'MEDIUM') {
      color = '#0284C7';
      bg = '#F0F9FF';
    } else if (conf === 'LOW') {
      color = '#B45309';
      bg = '#FFFBEB';
    } else if (conf === 'NONE') {
      color = '#64748B';
      bg = '#F1F5F9';
    }

    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.3rem',
          fontSize: '0.75rem',
          fontWeight: 600,
          padding: '0.2rem 0.55rem',
          borderRadius: 'var(--radius-full)',
          backgroundColor: bg,
          color: color,
        }}
        title="Transparent evidence-derived confidence rating"
      >
        <span>Confidence:</span>
        <strong style={{ textTransform: 'uppercase' }}>{conf}</strong>
      </span>
    );
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
          <strong>Core Assessment Principle:</strong> Absence of evidence is not evidence of absence.
          Capabilities not explicitly documented in candidate materials are classified as{' '}
          <strong style={{ color: '#0F172A' }}>UNKNOWN</strong>, not failures. This scorecard assists
          HR in targeted interview preparation; AI does not autonomously shortlist or reject
          candidates.
        </div>
      </div>

      {/* 2. Executive Context Card & Score Bar */}
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
                Pre-Interview Analytical Scorecard
              </h3>
              <span
                style={{
                  fontSize: '0.75rem',
                  padding: '0.15rem 0.5rem',
                  backgroundColor: 'var(--primary-50)',
                  color: 'var(--primary-700)',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 600,
                }}
              >
                v{scorecard.scorecard_version}
              </span>
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              Position: <strong>{scorecard.job_title}</strong> • Candidate: <strong>{scorecard.candidate_name}</strong>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Evaluated on {new Date(scorecard.assessment_timestamp).toLocaleString()}
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
            {refreshMutation.isPending ? 'Recalculating...' : 'Refresh Scorecard'}
          </button>
        </div>

        {/* Readiness Score & Metrics Row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '1rem',
            alignItems: 'center',
          }}
        >
          {/* Readiness Score */}
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
              <strong
                style={{
                  fontSize: '1.45rem',
                  fontWeight: 700,
                  color:
                    scorecard.evidence_readiness_score >= 70
                      ? '#065F46'
                      : scorecard.evidence_readiness_score >= 40
                      ? '#1E40AF'
                      : '#92400E',
                }}
              >
                {scorecard.evidence_readiness_score}%
              </strong>
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
                  width: `${Math.min(100, Math.max(0, scorecard.evidence_readiness_score))}%`,
                  height: '100%',
                  backgroundColor:
                    scorecard.evidence_readiness_score >= 70
                      ? '#10B981'
                      : scorecard.evidence_readiness_score >= 40
                      ? '#3B82F6'
                      : '#F59E0B',
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
            <p style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
              {scorecard.score_explanation}
            </p>
          </div>

          {/* Metric 1: Supported */}
          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--evidence-demonstrated-bg)',
              border: '1px solid var(--evidence-demonstrated-border)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--evidence-demonstrated-text)', fontWeight: 600 }}>
              SUPPORTED EVIDENCE
            </div>
            <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--evidence-demonstrated-text)' }}>
              {scorecard.supported_count}{' '}
              <span style={{ fontSize: '0.8125rem', fontWeight: 500 }}>/ {scorecard.total_capabilities}</span>
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--evidence-demonstrated-text)', marginTop: '0.15rem' }}>
              Verified or demonstrated
            </div>
          </div>

          {/* Metric 2: Partial */}
          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--evidence-claim-bg)',
              border: '1px solid var(--evidence-claim-border)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--evidence-claim-text)', fontWeight: 600 }}>
              PARTIAL (RESUME CLAIM)
            </div>
            <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--evidence-claim-text)' }}>
              {scorecard.partial_count}{' '}
              <span style={{ fontSize: '0.8125rem', fontWeight: 500 }}>/ {scorecard.total_capabilities}</span>
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--evidence-claim-text)', marginTop: '0.15rem' }}>
              Self-reported claims
            </div>
          </div>

          {/* Metric 3: Unknown */}
          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--evidence-unknown-bg)',
              border: '1px solid var(--evidence-unknown-border)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--evidence-unknown-text)', fontWeight: 600 }}>
              UNKNOWN (MISSING)
            </div>
            <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--evidence-unknown-text)' }}>
              {scorecard.unknown_count}{' '}
              <span style={{ fontSize: '0.8125rem', fontWeight: 500 }}>/ {scorecard.total_capabilities}</span>
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--evidence-unknown-text)', marginTop: '0.15rem' }}>
              Requires interview inquiry
            </div>
          </div>

          {/* Metric 4: Contradictory */}
          {scorecard.contradictory_count > 0 && (
            <div
              style={{
                padding: '0.75rem 1rem',
                backgroundColor: '#FEF3C7',
                border: '1px solid #FCD34D',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div style={{ fontSize: '0.75rem', color: '#92400E', fontWeight: 600 }}>
                CONTRADICTORY
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#92400E' }}>
                {scorecard.contradictory_count}
              </div>
              <div style={{ fontSize: '0.6875rem', color: '#92400E', marginTop: '0.15rem' }}>
                Conflicting evidence items
              </div>
            </div>
          )}
        </div>

        {/* Critical Verification Needs Bar */}
        {scorecard.critical_verification_needs.length > 0 && (
          <div
            style={{
              marginTop: '1rem',
              padding: '0.65rem 0.85rem',
              backgroundColor: '#FFFBEB',
              border: '1px solid #FDE68A',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              flexWrap: 'wrap',
            }}
          >
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#92400E' }}>
              CRITICAL VERIFICATION NEEDS:
            </span>
            <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
              {scorecard.critical_verification_needs.map((need, idx) => (
                <span
                  key={idx}
                  style={{
                    fontSize: '0.6875rem',
                    fontWeight: 600,
                    padding: '0.15rem 0.45rem',
                    backgroundColor: '#FEF3C7',
                    color: '#B45309',
                    borderRadius: 'var(--radius-xs)',
                    border: '1px solid #FCD34D',
                  }}
                >
                  {need}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 3. Filter Bar & Search */}
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
            { id: 'ALL', label: `All Requirements (${scorecard.total_capabilities})` },
            { id: 'SUPPORTED', label: `Supported (${scorecard.supported_count})` },
            { id: 'PARTIAL', label: `Partial Claims (${scorecard.partial_count})` },
            { id: 'UNKNOWN', label: `Unknowns (${scorecard.unknown_count})` },
            ...(scorecard.contradictory_count > 0
              ? [{ id: 'CONTRADICTORY', label: `Contradictory (${scorecard.contradictory_count})` }]
              : []),
          ].map((tab) => {
            const isSelected = statusFilter === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id as any)}
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

      {/* 4. Capability-by-Capability Scorecard List */}
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
            const badge = getStatusBadgeStyle(cap.status);
            const StatusIcon = badge.icon;

            return (
              <div
                key={cap.capability_id}
                className="card"
                style={{
                  backgroundColor: '#FFFFFF',
                  border: `1px solid ${badge.border}`,
                  borderRadius: 'var(--radius-lg)',
                  padding: '1.25rem 1.5rem',
                  boxShadow: 'var(--shadow-sm)',
                  transition: 'border-color var(--transition-fast)',
                }}
              >
                {/* Capability Header */}
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <h4 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-main)', margin: 0 }}>
                        {cap.capability_name}
                      </h4>
                      {getImportanceBadge(cap.importance)}
                    </div>
                    {cap.requirement_description && (
                      <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                        {cap.requirement_description}
                      </p>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                    {/* Status Badge */}
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        padding: '0.25rem 0.65rem',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        borderRadius: 'var(--radius-full)',
                        backgroundColor: badge.bg,
                        color: badge.text,
                        border: `1px solid ${badge.border}`,
                      }}
                    >
                      <StatusIcon size={14} />
                      {badge.label}
                    </span>

                    {/* Confidence Pill */}
                    {getConfidencePill(cap.confidence)}
                  </div>
                </div>

                {/* Status Rationale & Confidence Justification */}
                <div
                  style={{
                    padding: '0.65rem 0.85rem',
                    backgroundColor: 'var(--bg-app)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-base)',
                    marginBottom: '0.85rem',
                    fontSize: '0.8125rem',
                    lineHeight: 1.5,
                  }}
                >
                  <div>
                    <strong style={{ color: 'var(--text-main)' }}>Assessment Rationale: </strong>
                    <span style={{ color: 'var(--text-secondary)' }}>{cap.status_rationale}</span>
                  </div>
                  <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    <em>Confidence Rationale: {cap.confidence_justification}</em>
                  </div>
                </div>

                {/* Supporting Evidence Items */}
                <div style={{ marginBottom: '1rem' }}>
                  <div
                    style={{
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      color: 'var(--text-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                      marginBottom: '0.4rem',
                    }}
                  >
                    Supporting Persisted Evidence ({cap.supporting_evidence.length})
                  </div>

                  {cap.supporting_evidence.length === 0 ? (
                    <div
                      style={{
                        padding: '0.65rem 0.85rem',
                        backgroundColor: '#F8FAFC',
                        border: '1px dashed var(--border-base)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.75rem',
                        color: 'var(--text-muted)',
                        fontStyle: 'italic',
                      }}
                    >
                      No explicit supporting evidence found in submitted artifacts. Lack of mention does
                      not indicate lack of competence; verification during live interview is recommended.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {cap.supporting_evidence.map((ev) => (
                        <div
                          key={ev.id}
                          style={{
                            padding: '0.65rem 0.85rem',
                            backgroundColor: '#FFFFFF',
                            border: '1px solid var(--border-base)',
                            borderRadius: 'var(--radius-sm)',
                            borderLeft:
                              ev.provenance === 'VERIFIED'
                                ? '3px solid #10B981'
                                : ev.provenance === 'DEMONSTRATED'
                                ? '3px solid #059669'
                                : '3px solid #3B82F6',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              marginBottom: '0.3rem',
                              flexWrap: 'wrap',
                              gap: '0.5rem',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <span
                                style={{
                                  fontSize: '0.6875rem',
                                  fontWeight: 700,
                                  padding: '0.1rem 0.4rem',
                                  backgroundColor: 'var(--primary-50)',
                                  color: 'var(--primary-700)',
                                  borderRadius: 'var(--radius-xs)',
                                }}
                              >
                                {ev.source_type}
                              </span>
                              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-main)' }}>
                                {ev.source_reference || 'Resume Submission'}
                              </span>
                              {ev.source_location && (
                                <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                                  ({ev.source_location})
                                </span>
                              )}
                            </div>
                            <span
                              style={{
                                fontSize: '0.6875rem',
                                color: 'var(--text-muted)',
                                textTransform: 'uppercase',
                                fontWeight: 600,
                              }}
                            >
                              Provenance: {ev.provenance}
                            </span>
                          </div>

                          {ev.excerpt && (
                            <blockquote
                              style={{
                                margin: '0.3rem 0',
                                padding: '0.4rem 0.65rem',
                                backgroundColor: '#F8FAFC',
                                borderLeft: '2px solid var(--border-strong)',
                                fontSize: '0.8125rem',
                                color: 'var(--text-main)',
                                fontStyle: 'normal',
                                lineHeight: 1.45,
                              }}
                            >
                              "{ev.excerpt}"
                            </blockquote>
                          )}

                          {ev.limitations && (
                            <div style={{ fontSize: '0.6875rem', color: '#B45309', marginTop: '0.25rem' }}>
                              <strong>Limitation:</strong> {ev.limitations}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Recommended Verification Action */}
                <div
                  style={{
                    padding: '0.5rem 0.75rem',
                    backgroundColor: '#F8FAFC',
                    border: '1px solid var(--border-base)',
                    borderRadius: 'var(--radius-sm)',
                    marginBottom: '0.85rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.6rem',
                    flexWrap: 'wrap',
                  }}
                >
                  <span
                    style={{
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      padding: '0.15rem 0.45rem',
                      backgroundColor: '#E0E7FF',
                      color: '#4338CA',
                      borderRadius: 'var(--radius-xs)',
                      textTransform: 'uppercase',
                    }}
                  >
                    Action: {cap.recommended_verification.action_type}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {cap.recommended_verification.guidance}
                  </span>
                </div>

                {/* Targeted Interview Questions for this Gap */}
                {cap.targeted_questions.length > 0 && (
                  <div
                    style={{
                      backgroundColor: '#F0F9FF',
                      border: '1px solid #BAE6FD',
                      borderRadius: 'var(--radius-md)',
                      padding: '0.85rem 1rem',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        color: '#0369A1',
                        marginBottom: '0.5rem',
                      }}
                    >
                      <MessageSquare size={14} />
                      TARGETED INTERVIEW VERIFICATION QUESTIONS ({cap.targeted_questions.length})
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                      {cap.targeted_questions.map((q, qIdx) => (
                        <div
                          key={qIdx}
                          style={{
                            backgroundColor: '#FFFFFF',
                            border: '1px solid #E0F2FE',
                            borderRadius: 'var(--radius-sm)',
                            padding: '0.65rem 0.85rem',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                              marginBottom: '0.3rem',
                              flexWrap: 'wrap',
                            }}
                          >
                            <span
                              style={{
                                fontSize: '0.6875rem',
                                fontWeight: 700,
                                padding: '0.1rem 0.4rem',
                                backgroundColor: '#E0F2FE',
                                color: '#0369A1',
                                borderRadius: 'var(--radius-xs)',
                              }}
                            >
                              Intent: {q.intent}
                            </span>
                            <span
                              style={{
                                fontSize: '0.6875rem',
                                fontWeight: 600,
                                padding: '0.1rem 0.4rem',
                                backgroundColor: '#F1F5F9',
                                color: '#475569',
                                borderRadius: 'var(--radius-xs)',
                              }}
                            >
                              Difficulty: {q.difficulty}
                            </span>
                          </div>

                          <div
                            style={{
                              fontSize: '0.8125rem',
                              fontWeight: 500,
                              color: 'var(--text-main)',
                              lineHeight: 1.5,
                              marginBottom: '0.4rem',
                            }}
                          >
                            "{q.question_text}"
                          </div>

                          <div style={{ fontSize: '0.6875rem', color: '#0284C7', lineHeight: 1.4 }}>
                            <strong>Expected Signals: </strong>
                            {q.expected_signals}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* 5. Evaluator Human Notice Footer */}
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
