import React from 'react';
import { Bot, Mic, BrainCircuit, Volume2, AlertCircle } from 'lucide-react';
import type { AvatarState } from '../../core/types';

interface AvatarVisualizerProps {
  state: AvatarState;
  interviewerName?: string;
  size?: 'md' | 'lg';
}

export const AvatarVisualizer: React.FC<AvatarVisualizerProps> = ({
  state,
  interviewerName = 'Gap2Hire AI Interviewer',
  size = 'lg',
}) => {
  let stateLabel = 'Ready';
  let StateIcon = Bot;
  let ringColor = 'rgba(37, 99, 235, 0.2)';
  let primaryColor = '#2563EB';
  let animationClass = '';

  switch (state) {
    case 'LISTENING':
      stateLabel = 'Listening to response...';
      StateIcon = Mic;
      ringColor = 'rgba(16, 185, 129, 0.3)';
      primaryColor = '#10B981';
      break;
    case 'THINKING':
      stateLabel = 'Analyzing response & adapting...';
      StateIcon = BrainCircuit;
      ringColor = 'rgba(245, 158, 11, 0.3)';
      primaryColor = '#F59E0B';
      break;
    case 'SPEAKING':
      stateLabel = 'Speaking...';
      StateIcon = Volume2;
      ringColor = 'rgba(37, 99, 235, 0.35)';
      primaryColor = '#2563EB';
      break;
    case 'ERROR':
      stateLabel = 'Connection Interrupted';
      StateIcon = AlertCircle;
      ringColor = 'rgba(239, 68, 68, 0.3)';
      primaryColor = '#EF4444';
      break;
    case 'IDLE':
    default:
      stateLabel = 'Ready';
      StateIcon = Bot;
      ringColor = 'rgba(148, 163, 184, 0.2)';
      primaryColor = '#64748B';
      break;
  }

  const dimension = size === 'lg' ? 120 : 80;
  const iconSize = size === 'lg' ? 48 : 32;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
      }}
    >
      {/* Avatar Circle Container with pulse effect */}
      <div
        style={{
          position: 'relative',
          width: dimension + 30,
          height: dimension + 30,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* Pulsing ring */}
        {(state === 'SPEAKING' || state === 'LISTENING' || state === 'THINKING') && (
          <div
            style={{
              position: 'absolute',
              width: dimension + 24,
              height: dimension + 24,
              borderRadius: '50%',
              border: `2px solid ${primaryColor}`,
              backgroundColor: ringColor,
              animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }}
          />
        )}

        {/* Central Avatar Orb */}
        <div
          style={{
            position: 'relative',
            width: dimension,
            height: dimension,
            borderRadius: '50%',
            backgroundColor: '#FFFFFF',
            border: `3px solid ${primaryColor}`,
            boxShadow: `0 0 20px -2px ${ringColor}, 0 4px 12px rgba(15, 23, 42, 0.08)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: primaryColor,
            transition: 'all 0.3s ease',
          }}
        >
          <StateIcon size={iconSize} />
        </div>
      </div>

      {/* Avatar details & current state */}
      <div style={{ textAlign: 'center', marginTop: '1rem' }}>
        <h4 style={{ fontSize: size === 'lg' ? '1.1rem' : '0.95rem', fontWeight: 600 }}>
          {interviewerName}
        </h4>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            marginTop: '0.35rem',
            padding: '0.2rem 0.65rem',
            borderRadius: '9999px',
            backgroundColor: 'var(--bg-subtle)',
            border: '1px solid var(--border-base)',
            fontSize: '0.75rem',
            fontWeight: 600,
            color: primaryColor,
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: primaryColor,
              display: 'inline-block',
            }}
          />
          {stateLabel}
        </div>
      </div>
    </div>
  );
};
