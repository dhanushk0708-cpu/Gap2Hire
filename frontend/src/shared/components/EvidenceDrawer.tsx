import React from 'react';
import { X, ExternalLink, Calendar, Shield, BookmarkCheck, FileText } from 'lucide-react';
import { EvidenceBadge } from './EvidenceBadge';

export interface EvidenceDrawerItem {
  capability_name: string;
  state: string;
  strength?: string | null;
  provenance?: string | null;
  content?: string | null;
  source_type?: string | null;
  source_url?: string | null;
  confidence?: string | null;
  verification_status?: string | null;
  unknown_reason?: string | null;
  created_at?: string;
}

interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  evidence: EvidenceDrawerItem | null;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  isOpen,
  onClose,
  evidence,
}) => {
  if (!isOpen || !evidence) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.4)',
          backdropFilter: 'blur(2px)',
          transition: 'opacity var(--transition-fast)',
        }}
      />

      {/* Slide-out drawer panel */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '520px',
          height: '100%',
          backgroundColor: '#FFFFFF',
          boxShadow: 'var(--shadow-modal)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 101,
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-base)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Evidence Provenance & Verification
            </div>
            <h3 style={{ fontSize: '1.2rem', marginTop: '0.2rem' }}>
              {evidence.capability_name}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="btn btn-ghost"
            style={{ padding: '0.4rem', borderRadius: 'var(--radius-full)' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Content body */}
        <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Status & Provenance Header Card */}
          <div
            style={{
              padding: '1rem',
              backgroundColor: 'var(--bg-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-base)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Evidence State</span>
              <EvidenceBadge state={evidence.state} />
            </div>

            {evidence.provenance && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Provenance Method</span>
                <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
                  {evidence.provenance}
                </span>
              </div>
            )}

            {evidence.strength && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Observed Strength</span>
                <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)' }}>
                  {evidence.strength}
                </span>
              </div>
            )}
          </div>

          {/* Excerpt / Observation */}
          <div>
            <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <FileText size={16} color="var(--primary-600)" />
              Extracted Evidence Content
            </div>
            <div
              style={{
                backgroundColor: 'var(--bg-app)',
                border: '1px solid var(--border-base)',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                fontSize: '0.875rem',
                lineHeight: 1.6,
                color: 'var(--text-main)',
                fontStyle: evidence.content ? 'normal' : 'italic',
              }}
            >
              {evidence.content || evidence.unknown_reason || 'No specific textual excerpt attached for this capability.'}
            </div>
          </div>

          {/* Source Provenance Link */}
          {(evidence.source_type || evidence.source_url) && (
            <div>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <BookmarkCheck size={16} color="var(--primary-600)" />
                Source Origin
              </div>
              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid var(--border-base)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.875rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-main)' }}>
                    {evidence.source_type || 'Resume / Submission'}
                  </div>
                  {evidence.source_url && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', wordBreak: 'break-all', marginTop: '0.2rem' }}>
                      {evidence.source_url}
                    </div>
                  )}
                </div>
                {evidence.source_url && (
                  <a
                    href={evidence.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-secondary btn-sm"
                  >
                    <ExternalLink size={14} />
                    View
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Verification Status */}
          {evidence.verification_status && (
            <div>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Shield size={16} color="#059669" />
                Verification Status
              </div>
              <div
                style={{
                  backgroundColor: '#F0FDF4',
                  border: '1px solid #BBF7D0',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.875rem',
                  fontSize: '0.875rem',
                  color: '#166534',
                }}
              >
                Status: <strong>{evidence.verification_status}</strong>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '1rem 1.5rem',
            borderTop: '1px solid var(--border-base)',
            display: 'flex',
            justifyContent: 'flex-end',
            backgroundColor: 'var(--bg-subtle)',
          }}
        >
          <button onClick={onClose} className="btn btn-secondary">
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
