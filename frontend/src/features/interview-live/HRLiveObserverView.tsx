import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Eye,
  ShieldCheck,
  Radio,
  Clock,
  ClipboardList,
  AlertCircle,
  Activity,
  Bot,
  User,
} from 'lucide-react';
import { interviewSessionsApi } from '../../core/api/endpoints';
import { AvatarVisualizer } from '../../shared/components/AvatarVisualizer';
import { Skeleton } from '../../shared/components/Skeleton';
import { useInterviewWebSocket } from '../../core/websocket/useInterviewWebSocket';

export const HRLiveObserverView: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [selectedEvidence, setSelectedEvidence] = useState<{
    url: string;
    eventType: string;
    time: string;
    confidence?: number;
  } | null>(null);

  // Fetch initial observer context from backend
  const {
    data: observerContext,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['hrLiveObserver', sessionId],
    queryFn: () => interviewSessionsApi.getHRObserverContext(sessionId!),
    enabled: !!sessionId,
    refetchInterval: 5000, // Poll observer context periodically
  });

  // Fetch real integrity events
  const { data: integrityData, refetch: refetchIntegrity } = useQuery({
    queryKey: ['integrityEvents', sessionId],
    queryFn: () => interviewSessionsApi.getIntegrityEvents(sessionId!),
    enabled: !!sessionId,
    refetchInterval: 5000,
  });

  // Passive WebSocket listener for real-time messages & avatar updates
  const { isConnected, avatarState, messages, currentAIQuestion } = useInterviewWebSocket({
    sessionId: sessionId || '',
    onIntegrityObservation: React.useCallback(() => {
      refetchIntegrity();
    }, [refetchIntegrity]),
  });

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: 'var(--bg-app)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Read-Only Observation Banner */}
      <div
        style={{
          backgroundColor: '#EFF6FF',
          borderBottom: '1px solid #BFDBFE',
          padding: '0.65rem 1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#1D4ED8', fontSize: '0.8125rem', fontWeight: 600 }}>
          <Eye size={16} />
          <span>Live Observation Mode (Read-Only) — Human Observer cannot alter candidate session state.</span>
        </div>
        <Link
          to={`/interviews/${sessionId}/report`}
          className="btn btn-primary btn-sm"
        >
          <ClipboardList size={14} />
          View Evidence Report
        </Link>
      </div>

      {/* Main Container */}
      <div style={{ flex: 1, padding: '1.5rem', display: 'grid', gridTemplateColumns: '1fr 360px', gap: '1.25rem', overflow: 'hidden' }}>
        {/* Left Side: Avatar State & Active Question & Live Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', overflowY: 'auto' }}>
          {/* Header Info Card */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <h2 style={{ fontSize: '1.2rem', marginBottom: '0.2rem' }}>
                  Candidate: {observerContext?.candidate_name || 'Candidate'}
                </h2>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  Position: {observerContext?.job_title || 'Engineering Role'} • Session ID: {sessionId}
                </div>
              </div>

              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', fontWeight: 600, color: isConnected ? '#059669' : '#DC2626' }}>
                <Radio size={14} className={isConnected ? 'animate-pulse' : ''} />
                {isConnected ? 'Live Telemetry Active' : 'Connecting...'}
              </div>
            </div>
          </div>

          {/* AI Avatar State */}
          <div className="card" style={{ display: 'flex', justifyContent: 'center', padding: '1.5rem' }}>
            <AvatarVisualizer state={avatarState} size="md" />
          </div>

          {/* Live Conversation Stream */}
          <div className="card" style={{ flex: 1 }}>
            <h3 style={{ fontSize: '1.05rem', marginBottom: '1rem' }}>Live Conversation Stream</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '420px', overflowY: 'auto' }}>
              {messages.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', textAlign: 'center', padding: '2rem' }}>
                  Awaiting candidate speech or responses...
                </div>
              ) : (
                messages.map((m, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '0.875rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: m.role === 'ai' ? 'var(--primary-50)' : 'var(--bg-subtle)',
                      border: `1px solid ${m.role === 'ai' ? 'var(--primary-200)' : 'var(--border-base)'}`,
                      fontSize: '0.875rem',
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: '0.75rem', color: m.role === 'ai' ? 'var(--primary-700)' : 'var(--text-main)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                      {m.role === 'ai' ? 'AI Interviewer' : 'Candidate'}
                    </div>
                    <div style={{ color: 'var(--text-main)', lineHeight: 1.55 }}>
                      {m.content}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Side: Integrity Signals Telemetry Feed */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Activity size={18} color="var(--primary-600)" />
            <h4 style={{ fontSize: '1rem' }}>Integrity Observations</h4>
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
            Objective observations recorded for human review. Not automatic findings of misconduct.
          </p>

          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {!integrityData || integrityData.events.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8125rem', textAlign: 'center', padding: '2rem' }}>
                No session telemetry signals logged.
              </div>
            ) : (
              integrityData.events.map((evt) => {
                const isVisionAlert = evt.event_type === 'PHONE_DETECTED' || evt.event_type === 'MULTIPLE_PERSONS_DETECTED';
                const meta = evt.metadata_json || {};
                const evidenceUrl = meta.evidence_url || (meta.evidence_reference ? `/api/v1/interviews/${sessionId}/integrity-evidence/${evt.id}` : null);
                const confidence = meta.confidence ? Math.round(Number(meta.confidence) * 100) : null;
                const timeStr = new Date(evt.occurred_at).toLocaleTimeString();

                return (
                  <div
                    key={evt.id}
                    style={{
                      padding: '0.75rem',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: isVisionAlert ? '#FEF2F2' : 'var(--bg-app)',
                      border: `1px solid ${isVisionAlert ? '#FCA5A5' : 'var(--border-base)'}`,
                      fontSize: '0.8125rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                      <span style={{ fontWeight: 700, color: isVisionAlert ? '#B91C1C' : 'var(--text-main)' }}>
                        {isVisionAlert ? (evt.event_type === 'PHONE_DETECTED' ? '🔴 Phone detected' : '🔴 Multiple people detected') : evt.event_type}
                      </span>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                        {timeStr}
                      </span>
                    </div>

                    {isVisionAlert ? (
                      <div style={{ marginTop: '0.35rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#991B1B', fontWeight: 500 }}>
                          Integrity observation • Review required • Evidence captured
                          {confidence ? ` (${confidence}% confidence)` : ''}
                        </div>
                        {evidenceUrl && (
                          <button
                            onClick={() => setSelectedEvidence({
                              url: evidenceUrl,
                              eventType: evt.event_type === 'PHONE_DETECTED' ? 'Mobile Phone Detected' : 'Multiple People Detected',
                              time: timeStr,
                              confidence: confidence ?? undefined,
                            })}
                            style={{
                              marginTop: '0.45rem',
                              padding: '0.3rem 0.65rem',
                              backgroundColor: '#FFFFFF',
                              border: '1px solid #DC2626',
                              borderRadius: '4px',
                              color: '#DC2626',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            🔍 View Evidence Frame
                          </button>
                        )}
                      </div>
                    ) : (
                      evt.metadata_json && Object.keys(evt.metadata_json).length > 0 && (
                        <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>
                          {JSON.stringify(evt.metadata_json)}
                        </div>
                      )
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

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
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Captured at {selectedEvidence.time} {selectedEvidence.confidence ? `• Confidence: ${selectedEvidence.confidence}%` : ''}
                </div>
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
                Single evidence frame captured from candidate's webcam stream. Review required by hiring coordinator.
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
