import React from 'react';
import { Sparkles, CheckCircle2, Clock, XCircle, PauseCircle } from 'lucide-react';

interface StatusBadgeProps {
  status: string;
  isDemo?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, isDemo }) => {
  const norm = (status || '').toUpperCase();

  let label = norm.replace('_', ' ');
  let Icon = Clock;
  let bg = '#F1F5F9';
  let text = '#475569';
  let border = '#CBD5E1';

  switch (norm) {
    case 'ACTIVE':
    case 'HIRED':
    case 'SHORTLISTED':
    case 'SELECTED':
      label = norm === 'ACTIVE' ? 'Active' : norm === 'HIRED' ? 'Hired' : norm === 'SHORTLISTED' ? 'Shortlisted' : 'Selected';
      Icon = CheckCircle2;
      bg = '#ECFDF5';
      text = '#047857';
      border = '#A7F3D0';
      break;
    case 'DRAFT':
    case 'PENDING':
    case 'IN_REVIEW':
    case 'APPLIED':
    case 'HOLD':
    case 'ON_HOLD':
      label = norm === 'ON_HOLD' ? 'On Hold' : norm.replace('_', ' ');
      Icon = Clock;
      bg = '#FFFBEB';
      text = '#B45309';
      border = '#FDE68A';
      break;
    case 'PAUSED':
      label = 'Paused';
      Icon = PauseCircle;
      bg = '#F8FAFC';
      text = '#64748B';
      border = '#CBD5E1';
      break;
    case 'CLOSED':
    case 'REJECTED':
    case 'WITHDRAWN':
      label = norm === 'REJECTED' ? 'Rejected' : norm === 'CLOSED' ? 'Closed' : 'Withdrawn';
      Icon = XCircle;
      bg = '#FEF2F2';
      text = '#B91C1C';
      border = '#FECACA';
      break;
    case 'INTERVIEW':
    case 'VERIFICATION':
      label = norm === 'INTERVIEW' ? 'Interview Stage' : 'Verification Stage';
      Icon = Clock;
      bg = '#EFF6FF';
      text = '#1D4ED8';
      border = '#BFDBFE';
      break;
  }

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.3rem',
          fontSize: '0.75rem',
          fontWeight: 600,
          padding: '0.2rem 0.55rem',
          borderRadius: '9999px',
          backgroundColor: bg,
          color: text,
          border: `1px solid ${border}`,
          textTransform: 'capitalize',
        }}
      >
        <Icon size={12} />
        {label}
      </span>
      {isDemo && (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.25rem',
            fontSize: '0.7rem',
            fontWeight: 700,
            padding: '0.15rem 0.45rem',
            borderRadius: '9999px',
            backgroundColor: 'var(--badge-demo-bg)',
            color: 'var(--badge-demo-text)',
            border: '1px solid var(--badge-demo-border)',
            letterSpacing: '0.04em',
          }}
          title="Synthetic demo candidate from demo ingestion ZIP"
        >
          <Sparkles size={11} />
          DEMO
        </span>
      )}
    </div>
  );
};
