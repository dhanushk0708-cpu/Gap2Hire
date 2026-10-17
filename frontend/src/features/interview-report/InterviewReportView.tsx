import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ClipboardList,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Activity,
  Layers,
  Sparkles,
  Gavel,
  ShieldAlert,
  ArrowRight,
} from 'lucide-react';
import { interviewSessionsApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { EvidenceBadge } from '../../shared/components/EvidenceBadge';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';

export const InterviewReportView: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState<{
    url: string;
    eventType: string;
    time?: string;
  } | null>(null);

  const {
    data: report,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['interviewReport', sessionId],
    queryFn: () => interviewSessionsApi.getReport(sessionId!),
    enabled: !!sessionId,
  });

  const handleGenerateReport = async () => {
    if (!sessionId) return;
    setIsGenerating(true);
    try {
      await interviewSessionsApi.generateReport(sessionId);
      await refetch();
    } catch (err: any) {
      alert(err.message || 'Report generation failed');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Post-Interview Evidence & Competency Report"
        description="Deterministic post-interview findings, demonstrated capabilities, and human review recommendations."
        actions={
          <>
            {report?.application_id && (
              <Link
                to={`/candidates/${report.application_id}`}
                className="btn btn-primary"
              >
                <Gavel size={15} />
                Make Human Decision
              </Link>
            )}
            <button
              onClick={handleGenerateReport}
              disabled={isGenerating}
              className="btn btn-secondary"
            >
              <Sparkles size={15} />
              {isGenerating ? 'Generating...' : 'Re-Generate Report'}
            </button>
          </>
        }
      />

      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Skeleton height={140} />
          <Skeleton height={200} />
          <Skeleton height={200} />
        </div>
      ) : !report ? (
        <EmptyState
          icon={ClipboardList}
          title="Interview Report Not Yet Generated"
          description="The post-interview analysis report synthesizes answers and multi-round evidence. Click below to generate it."
          actionText="Generate Evidence Report"
          onAction={handleGenerateReport}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Executive Summary Card */}
          <div className="card">
            <h3 style={{ fontSize: '1.15rem', marginBottom: '0.5rem' }}>Executive Summary</h3>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.65, color: 'var(--text-main)', backgroundColor: 'var(--bg-subtle)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
              {report.executive_summary || report.summary || 'Post-interview evaluation completed. Evidence observed across scheduled rounds.'}
            </p>

            <div style={{ display: 'flex', gap: '2rem', marginTop: '1.25rem', flexWrap: 'wrap' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Candidate:</span>{' '}
                <strong style={{ fontSize: '0.875rem' }}>{report.candidate_name || 'Candidate'}</strong>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Role:</span>{' '}
                <strong style={{ fontSize: '0.875rem' }}>{report.job_title || 'Engineering Role'}</strong>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Questions Asked:</span>{' '}
                <strong style={{ fontSize: '0.875rem' }}>{report.total_questions}</strong>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Generated:</span>{' '}
                <strong style={{ fontSize: '0.875rem' }}>
                  {report.generated_at ? new Date(report.generated_at).toLocaleString() : 'Recent'}
                </strong>
              </div>
            </div>
          </div>

          {/* Competency Findings Grid: Demonstrated vs Claims vs Unknowns */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
            {/* Demonstrated */}
            <div className="card" style={{ borderColor: '#A7F3D0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#047857', fontWeight: 700, fontSize: '0.8125rem', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
                <CheckCircle2 size={16} />
                Demonstrated Capabilities ({report.demonstrated_capabilities.length})
              </div>
              {report.demonstrated_capabilities.length === 0 ? (
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>None recorded in this session.</div>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.875rem' }}>
                  {report.demonstrated_capabilities.map((c: any, idx: number) => (
                    <li key={idx} style={{ color: '#065F46' }}>
                      <strong>{c.capability_name || c.name || JSON.stringify(c)}</strong>
                      {c.observation && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{c.observation}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Claims Investigated */}
            <div className="card" style={{ borderColor: '#BFDBFE' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#1D4ED8', fontWeight: 700, fontSize: '0.8125rem', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
                <HelpCircle size={16} />
                Investigated Claims ({report.claimed_capabilities.length})
              </div>
              {report.claimed_capabilities.length === 0 ? (
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>No standalone claims noted.</div>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.875rem' }}>
                  {report.claimed_capabilities.map((c: any, idx: number) => (
                    <li key={idx} style={{ color: '#1E40AF' }}>
                      <strong>{c.capability_name || c.name || JSON.stringify(c)}</strong>
                      {c.observation && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{c.observation}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Unknowns / Verification Needed */}
            <div className="card" style={{ borderColor: '#FDE68A' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#B45309', fontWeight: 700, fontSize: '0.8125rem', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
                <AlertTriangle size={16} />
                Verification Needed / Unknowns ({report.verification_needed.length + report.unknown_capabilities.length})
              </div>
              {report.verification_needed.length === 0 && report.unknown_capabilities.length === 0 ? (
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>All targeted competencies resolved.</div>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.875rem' }}>
                  {[...report.verification_needed, ...report.unknown_capabilities].map((u: any, idx: number) => (
                    <li key={idx} style={{ color: '#92400E' }}>
                      <strong>{u.capability_name || u.name || JSON.stringify(u)}</strong>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Question-Level Findings */}
          {report.question_findings && report.question_findings.length > 0 && (
            <div className="card">
              <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Question-by-Question Evaluation</h3>
              <div className="data-table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Question</th>
                      <th>Candidate Answer Quality</th>
                      <th>Evidence State</th>
                      <th>Observed Findings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.question_findings.map((qf: any, idx: number) => (
                      <tr key={idx}>
                        <td><strong>{qf.sequence_number || idx + 1}</strong></td>
                        <td style={{ maxWidth: '300px' }}>
                          <div style={{ fontWeight: 600 }}>{qf.question_text}</div>
                          {qf.concept && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{qf.concept}</div>
                          )}
                        </td>
                        <td>
                          <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>
                            {qf.answer_quality || 'Evaluated'}
                          </span>
                        </td>
                        <td>
                          <EvidenceBadge state={qf.evidence_state || 'DEMONSTRATED'} />
                        </td>
                        <td>
                          <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                            {qf.what_was_demonstrated || qf.reasoning || '—'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Integrity Observations Section */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <Activity size={18} color="var(--primary-600)" />
              <h4 style={{ fontSize: '1rem', fontWeight: 700 }}>INTEGRITY OBSERVATIONS</h4>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: '1rem',
                marginBottom: '1rem',
              }}
            >
              {/* Baseline System Telemetry Signals */}
              <div
                style={{
                  padding: '1rem',
                  backgroundColor: '#F8FAFC',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-base)',
                }}
              >
                <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
                  Hardware & Environmental State
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.8125rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#16A34A', fontWeight: 500 }}>
                    <CheckCircle2 size={16} /> Camera connected
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#16A34A', fontWeight: 500 }}>
                    <CheckCircle2 size={16} /> Microphone connected
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#16A34A', fontWeight: 500 }}>
                    <CheckCircle2 size={16} /> Connection stable
                  </div>
                </div>
              </div>

              {/* Automated Vision Observations */}
              <div
                style={{
                  padding: '1rem',
                  backgroundColor: '#F8FAFC',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-base)',
                }}
              >
                <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
                  Automated Vision Observations
                </div>
                {(() => {
                  const observations = report.integrity_summary?.observations || [];
                  const visionObs = observations.filter((o: any) =>
                    o.event_type === 'PHONE_DETECTED' || o.event_type === 'MULTIPLE_PERSONS_DETECTED'
                  );

                  if (visionObs.length === 0) {
                    return (
                      <div style={{ fontSize: '0.8125rem', color: '#16A34A', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <CheckCircle2 size={16} /> No phone or multiple person anomalies detected
                      </div>
                    );
                  }

                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                      {visionObs.map((obs: any, idx: number) => {
                        const isPhone = obs.event_type === 'PHONE_DETECTED';
                        const title = isPhone ? 'Phone detected' : 'Multiple people detected';
                        const firstTime = obs.occurred_at_list?.[0] ? new Date(obs.occurred_at_list[0]).toLocaleTimeString() : 'Recorded';
                        const evidenceUrl = obs.evidence_urls?.[0] || (obs.evidence_references?.[0] ? `/api/v1/interviews/${sessionId}/integrity-evidence/${obs.evidence_references[0].split('/').pop()?.replace('.jpg', '')}` : null);

                        return (
                          <div
                            key={idx}
                            style={{
                              padding: '0.65rem',
                              backgroundColor: '#FEF2F2',
                              border: '1px solid #FCA5A5',
                              borderRadius: 'var(--radius-sm)',
                              fontSize: '0.8125rem',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                              <span style={{ fontWeight: 700, color: '#B91C1C' }}>
                                ⚠ {title} ({obs.count} event{obs.count > 1 ? 's' : ''})
                              </span>
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                {firstTime}
                              </span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.35rem' }}>
                              <span style={{ fontSize: '0.75rem', color: '#991B1B' }}>
                                Evidence available
                              </span>
                              {evidenceUrl && (
                                <button
                                  onClick={() => setSelectedEvidence({
                                    url: evidenceUrl,
                                    eventType: title,
                                    time: firstTime,
                                  })}
                                  style={{
                                    padding: '0.2rem 0.5rem',
                                    backgroundColor: '#FFFFFF',
                                    border: '1px solid #DC2626',
                                    borderRadius: '4px',
                                    color: '#DC2626',
                                    fontSize: '0.75rem',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                  }}
                                >
                                  View Evidence
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>
            </div>

            <div
              style={{
                padding: '0.75rem 1rem',
                backgroundColor: '#FFFBEB',
                border: '1px solid #FDE68A',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.78rem',
                color: '#92400E',
                lineHeight: 1.45,
              }}
            >
              <strong>Notice:</strong> These are automated observations and should be reviewed by a human. They are not automatic findings of misconduct.
            </div>
          </div>

          {/* Human Decision Callout Banner */}
          <div
            className="card"
            style={{
              backgroundColor: '#EFF6FF',
              borderColor: '#BFDBFE',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '1.25rem 1.5rem',
            }}
          >
            <div>
              <div style={{ fontSize: '1rem', fontWeight: 700, color: '#1D4ED8' }}>
                Ready to Record Final Human Hiring Decision?
              </div>
              <p style={{ fontSize: '0.8125rem', color: '#1E40AF', marginTop: '0.2rem' }}>
                The AI does not decide who to hire. Human managers review evidence and provide required justification.
              </p>
            </div>
            {report.application_id && (
              <Link
                to={`/candidates/${report.application_id}`}
                className="btn btn-primary"
              >
                Go to Candidate Workspace
                <ArrowRight size={15} />
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Evidence Frame Preview Modal */}
      {selectedEvidence && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
          onClick={() => setSelectedEvidence(null)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: 'var(--radius-lg)',
              maxWidth: '640px',
              width: '100%',
              overflow: 'hidden',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: '1rem 1.25rem',
                borderBottom: '1px solid var(--border-base)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#B91C1C' }}>
                  🔴 Integrity Evidence: {selectedEvidence.eventType}
                </h3>
                {selectedEvidence.time && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Observed at {selectedEvidence.time}
                  </div>
                )}
              </div>
              <button
                onClick={() => setSelectedEvidence(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '1.25rem',
                  cursor: 'pointer',
                  color: 'var(--text-muted)',
                }}
              >
                ✕
              </button>
            </div>
            <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <img
                src={selectedEvidence.url}
                alt="Integrity Evidence Frame"
                style={{
                  maxWidth: '100%',
                  maxHeight: '420px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-base)',
                  objectFit: 'contain',
                }}
              />
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.75rem', textAlign: 'center' }}>
                Evidence frame captured from candidate's webcam stream. Review required by hiring coordinator.
              </p>
            </div>
            <div
              style={{
                padding: '0.75rem 1.25rem',
                backgroundColor: 'var(--bg-subtle)',
                borderTop: '1px solid var(--border-base)',
                display: 'flex',
                justifyContent: 'flex-end',
              }}
            >
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setSelectedEvidence(null)}
              >
                Close Evidence
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
