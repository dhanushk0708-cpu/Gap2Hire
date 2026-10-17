import React from 'react';
import {
  CheckCircle2,
  HelpCircle,
  AlertTriangle,
  FileText,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import type { EvidenceState } from '../../core/types';

interface EvidenceBadgeProps {
  state: EvidenceState | string;
  size?: 'sm' | 'md';
  showLabel?: boolean;
}

export const EvidenceBadge: React.FC<EvidenceBadgeProps> = ({
  state,
  size = 'md',
  showLabel = true,
}) => {
  const normalized = (state || 'UNKNOWN').toUpperCase();

  let label = 'Unknown';
  let Icon = HelpCircle;
  let bgClass = 'bg-slate-50';
  let textClass = 'text-slate-600';
  let borderClass = 'border-slate-200';
  let dotColor = '#94A3B8';

  switch (normalized) {
    case 'DEMONSTRATED':
      label = 'Demonstrated';
      Icon = CheckCircle2;
      bgClass = 'bg-emerald-50';
      textClass = 'text-emerald-700';
      borderClass = 'border-emerald-200';
      dotColor = '#10B981';
      break;
    case 'CLAIM':
      label = 'Claim';
      Icon = FileText;
      bgClass = 'bg-blue-50';
      textClass = 'text-blue-700';
      borderClass = 'border-blue-200';
      dotColor = '#3B82F6';
      break;
    case 'VERIFIED':
      label = 'Verified';
      Icon = ShieldCheck;
      bgClass = 'bg-green-50';
      textClass = 'text-green-700';
      borderClass = 'border-green-200';
      dotColor = '#22C55E';
      break;
    case 'VERIFICATION_NEEDED':
      label = 'Verification Needed';
      Icon = AlertTriangle;
      bgClass = 'bg-amber-50';
      textClass = 'text-amber-800';
      borderClass = 'border-amber-200';
      dotColor = '#F59E0B';
      break;
    case 'INSUFFICIENT':
      label = 'Insufficient';
      Icon = XCircle;
      bgClass = 'bg-rose-50';
      textClass = 'text-rose-700';
      borderClass = 'border-rose-200';
      dotColor = '#EF4444';
      break;
    case 'UNKNOWN':
    default:
      label = 'Unknown';
      Icon = HelpCircle;
      bgClass = 'bg-slate-50';
      textClass = 'text-slate-600';
      borderClass = 'border-slate-200';
      dotColor = '#94A3B8';
      break;
  }

  const padding = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';
  const iconSize = size === 'sm' ? 12 : 14;

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${padding} ${bgClass} ${textClass} ${borderClass}`}
      style={{
        backgroundColor:
          normalized === 'DEMONSTRATED'
            ? 'var(--evidence-demonstrated-bg)'
            : normalized === 'CLAIM'
            ? 'var(--evidence-claim-bg)'
            : normalized === 'VERIFIED'
            ? 'var(--evidence-verified-bg)'
            : normalized === 'VERIFICATION_NEEDED'
            ? 'var(--evidence-vneed-bg)'
            : normalized === 'INSUFFICIENT'
            ? 'var(--evidence-insufficient-bg)'
            : 'var(--evidence-unknown-bg)',
        color:
          normalized === 'DEMONSTRATED'
            ? 'var(--evidence-demonstrated-text)'
            : normalized === 'CLAIM'
            ? 'var(--evidence-claim-text)'
            : normalized === 'VERIFIED'
            ? 'var(--evidence-verified-text)'
            : normalized === 'VERIFICATION_NEEDED'
            ? 'var(--evidence-vneed-text)'
            : normalized === 'INSUFFICIENT'
            ? 'var(--evidence-insufficient-text)'
            : 'var(--evidence-unknown-text)',
        borderColor:
          normalized === 'DEMONSTRATED'
            ? 'var(--evidence-demonstrated-border)'
            : normalized === 'CLAIM'
            ? 'var(--evidence-claim-border)'
            : normalized === 'VERIFIED'
            ? 'var(--evidence-verified-border)'
            : normalized === 'VERIFICATION_NEEDED'
            ? 'var(--evidence-vneed-border)'
            : normalized === 'INSUFFICIENT'
            ? 'var(--evidence-insufficient-border)'
            : 'var(--evidence-unknown-border)',
      }}
    >
      <Icon size={iconSize} />
      {showLabel && <span>{label}</span>}
    </span>
  );
};
