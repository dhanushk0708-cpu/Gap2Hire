import React from 'react';
import { Target, Users, ShieldAlert, Award } from 'lucide-react';

interface TopNBannerProps {
  shortlistSize: number;
  evaluatedCount: number;
  shortlistedCount: number;
  onAdjustSize?: () => void;
  onSelectSize?: (newSize: number) => void;
  isUpdatingSize?: boolean;
}

export const TopNBanner: React.FC<TopNBannerProps> = ({
  shortlistSize,
  evaluatedCount,
  shortlistedCount,
  onAdjustSize,
  onSelectSize,
  isUpdatingSize,
}) => {
  return (
    <div
      style={{
        backgroundColor: '#FFFFFF',
        border: '1px solid var(--border-base)',
        borderRadius: 'var(--radius-lg)',
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--primary-50)',
              color: 'var(--primary-600)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Target size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              Target Shortlist
            </div>
            {onSelectSize ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.15rem' }}>
                <select
                  value={[3, 5, 10, 15, 20].includes(shortlistSize) ? shortlistSize : 'custom'}
                  onChange={(e) => {
                    if (e.target.value === 'custom') {
                      onAdjustSize?.();
                    } else {
                      onSelectSize(Number(e.target.value));
                    }
                  }}
                  disabled={isUpdatingSize}
                  style={{
                    fontWeight: 700,
                    fontSize: '1rem',
                    padding: '0.15rem 0.5rem',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-base)',
                    backgroundColor: '#F8FAFC',
                    color: 'var(--text-main)',
                    cursor: 'pointer',
                  }}
                >
                  <option value={3}>Top-3</option>
                  <option value={5}>Top-5</option>
                  <option value={10}>Top-10</option>
                  <option value={15}>Top-15</option>
                  <option value={20}>Top-20</option>
                  <option value="custom">{[3, 5, 10, 15, 20].includes(shortlistSize) ? 'Custom...' : `Custom (Top-${shortlistSize})`}</option>
                </select>
              </div>
            ) : (
              <div style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Top-{shortlistSize}
              </div>
            )}
          </div>
        </div>

        <div style={{ height: 28, width: 1, backgroundColor: 'var(--border-base)' }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 'var(--radius-md)',
              backgroundColor: '#ECFDF5',
              color: '#059669',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Award size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              Currently Shortlisted
            </div>
            <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#059669' }}>
              {shortlistedCount} Candidates
            </div>
          </div>
        </div>

        <div style={{ height: 28, width: 1, backgroundColor: 'var(--border-base)' }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-subtle)',
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Users size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              Total Evaluated
            </div>
            <div style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-main)' }}>
              {evaluatedCount} Pool
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            fontSize: '0.75rem',
            color: 'var(--text-secondary)',
            backgroundColor: 'var(--bg-subtle)',
            padding: '0.4rem 0.75rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-base)',
          }}
        >
          <ShieldAlert size={14} color="#64748B" />
          <span>Top-N maintains candidate ranks. Final decisions remain strictly human-controlled.</span>
        </div>

        {onAdjustSize && (
          <button
            onClick={onAdjustSize}
            className="btn btn-secondary btn-sm"
          >
            Adjust Shortlist Size
          </button>
        )}
      </div>
    </div>
  );
};
