import React, { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Sparkles,
  Send,
  RefreshCw,
  Shield,
  AlertCircle,
  FileText,
  Briefcase,
  User,
  CheckCircle2,
  Info,
  CornerDownLeft,
  ChevronDown,
  ChevronUp,
  Database,
  Quote,
} from 'lucide-react';
import { hiringChatApi, jobsApi, applicationsApi } from '../../core/api/endpoints';
import { useAuth } from '../../core/auth/AuthContext';
import type {
  ChatMessage,
  HiringChatRequest,
  HiringChatResponse,
  HiringChatCitation,
  IndexSyncResponse,
  Job,
  Application,
} from '../../core/types';

interface UIMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: HiringChatCitation[];
  limitations?: string[];
  contextScope?: string;
  isNoEvidence?: boolean;
  timestamp: Date;
}

const QUICK_PROMPTS = [
  'What are the common unverified capabilities across candidates?',
  'Summarize Python and microservices evidence for our backend openings.',
  'Are there divergence patterns between interview ratings and 90-day outcomes?',
  'List candidates who demonstrated strong system architecture capability.',
];

export const HiringChatView: React.FC = () => {
  const { user } = useAuth();
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [scopeType, setScopeType] = useState<'TENANT' | 'JOB' | 'APPLICATION'>('TENANT');
  const [selectedJobId, setSelectedJobId] = useState<string>('');
  const [selectedApplicationId, setSelectedApplicationId] = useState<string>('');
  const [expandedCitations, setExpandedCitations] = useState<Record<string, boolean>>({});
  const [lastSyncInfo, setLastSyncInfo] = useState<IndexSyncResponse | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load jobs for scope filter
  const { data: jobs = [] } = useQuery<Job[]>({
    queryKey: ['jobsListScope'],
    queryFn: jobsApi.list,
  });

  // Load applications for scope filter
  const { data: applications = [] } = useQuery<Application[]>({
    queryKey: ['applicationsListScope', selectedJobId],
    queryFn: () => applicationsApi.list(selectedJobId || undefined),
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Index synchronization mutation
  const syncMutation = useMutation({
    mutationFn: () =>
      hiringChatApi.syncIndex({
        job_id: scopeType === 'JOB' && selectedJobId ? selectedJobId : undefined,
        application_id: scopeType === 'APPLICATION' && selectedApplicationId ? selectedApplicationId : undefined,
      }),
    onSuccess: (data) => {
      setLastSyncInfo(data);
    },
  });

  // Chat query mutation
  const chatMutation = useMutation({
    mutationFn: (req: HiringChatRequest) => hiringChatApi.chat(req),
    onSuccess: (data: HiringChatResponse) => {
      const isNoEvidence =
        data.citations.length === 0 &&
        data.answer.toLowerCase().includes('no relevant context was found');

      const assistantMsg: UIMessage = {
        id: `asst-${Date.now()}`,
        role: 'assistant',
        content: data.answer,
        citations: data.citations,
        limitations: data.limitations,
        contextScope: data.context_scope,
        isNoEvidence,
        timestamp: new Date(data.generated_at),
      };

      setMessages((prev) => [...prev, assistantMsg]);
      // Expand citations by default if present
      if (data.citations.length > 0) {
        setExpandedCitations((prev) => ({ ...prev, [assistantMsg.id]: true }));
      }
    },
  });

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed || chatMutation.isPending) return;

    const userMsg: UIMessage = {
      id: `usr-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');

    // Prepare history (prior turns, max 20)
    const historyPayload: ChatMessage[] = messages.slice(-20).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const payload: HiringChatRequest = {
      message: trimmed,
      history: historyPayload,
      job_id: scopeType === 'JOB' && selectedJobId ? selectedJobId : null,
      application_id: scopeType === 'APPLICATION' && selectedApplicationId ? selectedApplicationId : null,
    };

    chatMutation.mutate(payload);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const toggleCitations = (msgId: string) => {
    setExpandedCitations((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 180px)', minHeight: '600px' }}>
      {/* 1. Header & Freshness Control */}
      <div
        className="card"
        style={{
          marginBottom: '1rem',
          padding: '0.875rem 1.25rem',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          backgroundColor: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-base)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 'var(--radius-md)',
              backgroundColor: '#EEF2FF',
              color: 'var(--primary-600)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Sparkles size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontWeight: 700, fontSize: '0.9375rem', color: 'var(--text-main)' }}>
                HireIQ Intelligence Chat
              </span>
              <span
                style={{
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                  backgroundColor: '#F0FDF4',
                  color: '#166534',
                  border: '1px solid #BBF7D0',
                  padding: '0.15rem 0.5rem',
                  borderRadius: 'var(--radius-full)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                }}
              >
                <Shield size={10} />
                Tenant Isolated
              </span>
              <span
                style={{
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                  backgroundColor: '#FFFBEB',
                  color: '#92400E',
                  border: '1px solid #FDE68A',
                  padding: '0.15rem 0.5rem',
                  borderRadius: 'var(--radius-full)',
                }}
              >
                Advisory Only
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Evidence-grounded conversational intelligence with verbatim provenance citations.
            </div>
          </div>
        </div>

        {/* Index Freshness & Sync */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', fontSize: '0.75rem' }}>
            <span style={{ color: 'var(--text-secondary)', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
              <Database size={12} style={{ color: '#10B981' }} />
              Hybrid Vector Index: <strong style={{ color: 'var(--text-main)' }}>Active</strong>
            </span>
            {lastSyncInfo && (
              <span style={{ color: '#059669', fontSize: '0.6875rem' }}>
                Synced: {lastSyncInfo.created} new, {lastSyncInfo.updated} updated ({lastSyncInfo.unchanged} unchanged)
              </span>
            )}
          </div>
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="btn btn-secondary btn-sm"
            title="Re-index new candidate resumes, scorecard evidence, and outcome records"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem' }}
          >
            <RefreshCw size={13} className={syncMutation.isPending ? 'spin' : ''} />
            <span>{syncMutation.isPending ? 'Syncing...' : 'Refresh Index'}</span>
          </button>
        </div>
      </div>

      {/* 2. Retrieval Scope Filter Bar */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '0.5rem 0.75rem',
          marginBottom: '0.75rem',
          backgroundColor: '#F8FAFC',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-base)',
          fontSize: '0.8125rem',
        }}
      >
        <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Retrieval Scope:</span>
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          <button
            type="button"
            onClick={() => {
              setScopeType('TENANT');
              setSelectedJobId('');
              setSelectedApplicationId('');
            }}
            className={`btn btn-sm ${scopeType === 'TENANT' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
          >
            Entire Tenant
          </button>
          <button
            type="button"
            onClick={() => setScopeType('JOB')}
            className={`btn btn-sm ${scopeType === 'JOB' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
          >
            Specific Job
          </button>
          <button
            type="button"
            onClick={() => setScopeType('APPLICATION')}
            className={`btn btn-sm ${scopeType === 'APPLICATION' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
          >
            Specific Candidate
          </button>
        </div>

        {scopeType === 'JOB' && (
          <select
            value={selectedJobId}
            onChange={(e) => setSelectedJobId(e.target.value)}
            style={{
              padding: '0.25rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-base)',
              fontSize: '0.75rem',
              maxWidth: '240px',
            }}
          >
            <option value="">-- Select Job --</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title}
              </option>
            ))}
          </select>
        )}

        {scopeType === 'APPLICATION' && (
          <select
            value={selectedApplicationId}
            onChange={(e) => setSelectedApplicationId(e.target.value)}
            style={{
              padding: '0.25rem 0.5rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-base)',
              fontSize: '0.75rem',
              maxWidth: '260px',
            }}
          >
            <option value="">-- Select Application --</option>
            {applications.map((app) => (
              <option key={app.id} value={app.id}>
                Application #{app.id.slice(0, 8)} ({app.status})
              </option>
            ))}
          </select>
        )}

        <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          {scopeType === 'TENANT' && 'Spans all pipeline candidates, JD capabilities & outcome records'}
          {scopeType === 'JOB' && (selectedJobId ? 'Constrained strictly to selected job scope' : 'Select a job to restrict scope')}
          {scopeType === 'APPLICATION' && (selectedApplicationId ? 'Constrained strictly to candidate application' : 'Select a candidate to restrict scope')}
        </span>
      </div>

      {/* 3. Messages Container */}
      <div
        className="card"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
          backgroundColor: '#FAFAFA',
        }}
      >
        {messages.length === 0 ? (
          /* Empty State */
          <div
            style={{
              margin: 'auto',
              maxWidth: '560px',
              textAlign: 'center',
              padding: '2rem 1rem',
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: '50%',
                backgroundColor: '#EEF2FF',
                color: 'var(--primary-600)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '1rem',
              }}
            >
              <Sparkles size={24} />
            </div>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
              Ask HireIQ About Your Hiring Data
            </h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '1.5rem' }}>
              HireIQ performs hybrid semantic and keyword retrieval over your organization's persisted candidate evidence, interview evaluations, and post-hire outcomes. Every response requires verified citations.
            </p>

            <div style={{ textAlign: 'left' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Suggested Questions:
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {QUICK_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setInputValue(prompt);
                    }}
                    style={{
                      textAlign: 'left',
                      padding: '0.5rem 0.75rem',
                      fontSize: '0.8125rem',
                      color: 'var(--primary-700)',
                      backgroundColor: '#FFFFFF',
                      border: '1px solid var(--border-base)',
                      borderRadius: 'var(--radius-md)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--primary-400)')}
                    onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-base)')}
                  >
                    "{prompt}"
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                width: '100%',
              }}
            >
              {/* Message Bubble */}
              <div
                style={{
                  maxWidth: '82%',
                  padding: '0.875rem 1.125rem',
                  borderRadius: 'var(--radius-lg)',
                  backgroundColor: msg.role === 'user' ? 'var(--primary-600)' : '#FFFFFF',
                  color: msg.role === 'user' ? '#FFFFFF' : 'var(--text-main)',
                  border: msg.role === 'user' ? 'none' : '1px solid var(--border-base)',
                  boxShadow: 'var(--shadow-sm)',
                  fontSize: '0.875rem',
                  lineHeight: 1.55,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {/* No-Evidence Alert if applicable */}
                {msg.isNoEvidence && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '0.5rem',
                      padding: '0.5rem 0.75rem',
                      marginBottom: '0.75rem',
                      backgroundColor: '#F8FAFC',
                      border: '1px solid #CBD5E1',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '0.75rem',
                      color: '#475569',
                    }}
                  >
                    <Info size={15} style={{ color: '#0284C7', flexShrink: 0, marginTop: '0.1rem' }} />
                    <div>
                      <strong>No Grounded Evidence Found:</strong> The database currently contains no relevant indexed chunks matching this question within the specified scope. This does not indicate a candidate deficiency.
                    </div>
                  </div>
                )}

                {/* Safe plain text render (avoids raw HTML execution) */}
                <div>{msg.content}</div>

                {/* Scope Badge & Citations Footer for Assistant */}
                {msg.role === 'assistant' && (
                  <div style={{ marginTop: '0.75rem', borderTop: '1px solid #F1F5F9', paddingTop: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                        Scope: <strong>{msg.contextScope || 'TENANT'}</strong> • {msg.timestamp.toLocaleTimeString()}
                      </span>

                      {msg.citations && msg.citations.length > 0 && (
                        <button
                          type="button"
                          onClick={() => toggleCitations(msg.id)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            color: 'var(--primary-600)',
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '0.2rem 0.4rem',
                          }}
                        >
                          <FileText size={12} />
                          <span>{msg.citations.length} Verified Citation{msg.citations.length > 1 ? 's' : ''}</span>
                          {expandedCitations[msg.id] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                      )}
                    </div>

                    {/* Citations List */}
                    {msg.citations && msg.citations.length > 0 && expandedCitations[msg.id] && (
                      <div
                        style={{
                          marginTop: '0.5rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.5rem',
                        }}
                      >
                        {msg.citations.map((cite, cIdx) => (
                          <div
                            key={cIdx}
                            style={{
                              padding: '0.625rem 0.75rem',
                              borderRadius: 'var(--radius-md)',
                              backgroundColor: '#F8FAFC',
                              border: '1px solid #E2E8F0',
                              fontSize: '0.75rem',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <span
                                  style={{
                                    fontWeight: 700,
                                    backgroundColor: '#EEF2FF',
                                    color: 'var(--primary-700)',
                                    borderRadius: '3px',
                                    padding: '0.1rem 0.35rem',
                                  }}
                                >
                                  [{cIdx + 1}]
                                </span>
                                <span
                                  style={{
                                    fontWeight: 600,
                                    color: '#0F172A',
                                  }}
                                >
                                  {cite.source_type.replace(/_/g, ' ')}
                                </span>
                              </div>
                              <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                                ID: {cite.chunk_id.slice(0, 16)}
                              </span>
                            </div>

                            {/* Metadata */}
                            {(cite.candidate_name || cite.job_title || cite.capability_name) && (
                              <div style={{ display: 'flex', gap: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.35rem', fontSize: '0.6875rem' }}>
                                {cite.candidate_name && <span>Candidate: <strong>{cite.candidate_name}</strong></span>}
                                {cite.job_title && <span>Job: <strong>{cite.job_title}</strong></span>}
                                {cite.capability_name && <span>Capability: <strong>{cite.capability_name}</strong></span>}
                              </div>
                            )}

                            {/* Verified Source Excerpt Highlight */}
                            <div
                              style={{
                                padding: '0.4rem 0.6rem',
                                backgroundColor: '#F0FDF4',
                                borderLeft: '3px solid #10B981',
                                borderRadius: '0 4px 4px 0',
                                color: '#14532D',
                                fontSize: '0.75rem',
                                fontStyle: 'italic',
                                display: 'flex',
                                alignItems: 'flex-start',
                                gap: '0.35rem',
                              }}
                            >
                              <Quote size={12} style={{ flexShrink: 0, marginTop: '0.15rem', color: '#059669' }} />
                              <span>"{cite.excerpt}"</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {/* Loading Spinner / Typing state */}
        {chatMutation.isPending && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                backgroundColor: '#EEF2FF',
                color: 'var(--primary-600)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Sparkles size={16} className="spin" />
            </div>
            <span>HireIQ is querying hybrid vector index and verifying citations...</span>
          </div>
        )}

        {/* Error Alert */}
        {chatMutation.isError && (
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: '#FEF2F2',
              border: '1px solid #FECACA',
              color: '#991B1B',
              fontSize: '0.8125rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <AlertCircle size={16} style={{ color: '#DC2626' }} />
              <span>
                {(chatMutation.error as any)?.message ||
                  'Failed to complete hiring intelligence chat. Ensure the embedding service and database are operational.'}
              </span>
            </div>
            <button
              type="button"
              onClick={() => handleSubmit()}
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
            >
              Retry
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 4. Input Form */}
      <form
        onSubmit={handleSubmit}
        style={{
          marginTop: '0.75rem',
          display: 'flex',
          gap: '0.5rem',
          alignItems: 'flex-end',
        }}
      >
        <div style={{ flex: 1, position: 'relative' }}>
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={chatMutation.isPending}
            placeholder={
              chatMutation.isPending
                ? 'Processing question...'
                : 'Ask HireIQ a question about candidate evidence, interview evaluations, or job criteria...'
            }
            rows={2}
            style={{
              width: '100%',
              padding: '0.625rem 0.875rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-base)',
              fontSize: '0.875rem',
              resize: 'none',
              fontFamily: 'inherit',
              boxSizing: 'border-box',
              outline: 'none',
              backgroundColor: chatMutation.isPending ? '#F1F5F9' : '#FFFFFF',
            }}
          />
        </div>
        <button
          type="submit"
          disabled={!inputValue.trim() || chatMutation.isPending}
          className="btn btn-primary"
          style={{
            height: '52px',
            padding: '0 1.25rem',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            fontWeight: 600,
          }}
        >
          <Send size={16} />
          <span>Send</span>
        </button>
      </form>

      {/* 5. Advisory Ownership Notice */}
      <div
        style={{
          marginTop: '0.4rem',
          textAlign: 'center',
          fontSize: '0.6875rem',
          color: 'var(--text-muted)',
        }}
      >
        HireIQ provides evidence-grounded advisory insights. Human HR professionals retain sole authority over hiring decisions.
      </div>
    </div>
  );
};
