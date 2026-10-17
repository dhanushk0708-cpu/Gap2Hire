import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { BarChart3, Users, Briefcase, Award, ShieldCheck, CheckCircle2, Sparkles, ArrowRight } from 'lucide-react';
import { jobsApi, applicationsApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';
import type { Application } from '../../core/types';

export const AnalyticsView: React.FC = () => {
  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: jobsApi.list,
  });

  const { data: applications, isLoading: appsLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: () => applicationsApi.list(),
  });

  const isLoading = jobsLoading || appsLoading;

  const totalApps = applications?.length || 0;
  const hiredCount = applications?.filter((a: Application) => a.status === 'HIRED').length || 0;
  const inReviewCount = applications?.filter((a: Application) => a.status === 'IN_REVIEW' || a.status === 'APPLIED').length || 0;
  const rejectedCount = applications?.filter((a: Application) => a.status === 'REJECTED').length || 0;
  const interviewCount = applications?.filter((a: Application) => a.status === 'INTERVIEW').length || 0;

  return (
    <div>
      <PageHeader
        title="Evidence & Hiring Pipeline Analytics"
        description="Real-time pipeline metrics and competency verification statistics across all active positions."
        actions={
          <Link to="/hiring-intelligence" className="btn btn-primary btn-sm">
            <Sparkles size={14} />
            <span>Hiring Quality Intelligence</span>
            <ArrowRight size={14} />
          </Link>
        }
      />

      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Skeleton height={100} />
          <Skeleton height={200} />
        </div>
      ) : totalApps === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="No Pipeline Data Available"
          description="Analytics will populate once candidates are evaluated through screening and interviews."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Funnel Metrics Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem' }}>
            <div className="card">
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Total Applicants</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-main)', marginTop: '0.25rem' }}>
                {totalApps}
              </div>
            </div>

            <div className="card">
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Screening Queue</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#D97706', marginTop: '0.25rem' }}>
                {inReviewCount}
              </div>
            </div>

            <div className="card">
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Interview Stage</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--primary-600)', marginTop: '0.25rem' }}>
                {interviewCount}
              </div>
            </div>

            <div className="card">
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Hired / Selected</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#059669', marginTop: '0.25rem' }}>
                {hiredCount}
              </div>
            </div>
          </div>

          {/* Pipeline Distribution Visualizer */}
          <div className="card">
            <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Candidate Progression Funnel</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {[
                { label: 'Applied / In Review', count: inReviewCount, color: '#D97706' },
                { label: 'Interview Stage', count: interviewCount, color: 'var(--primary-600)' },
                { label: 'Selected / Hired', count: hiredCount, color: '#059669' },
                { label: 'Rejected', count: rejectedCount, color: '#DC2626' },
              ].map((stage) => {
                const pct = totalApps > 0 ? Math.round((stage.count / totalApps) * 100) : 0;
                return (
                  <div key={stage.label}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
                      <span style={{ fontWeight: 600 }}>{stage.label}</span>
                      <span style={{ color: 'var(--text-secondary)' }}>
                        {stage.count} candidates ({pct}%)
                      </span>
                    </div>
                    <div style={{ height: '8px', backgroundColor: 'var(--bg-muted)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${pct}%`,
                          backgroundColor: stage.color,
                          borderRadius: 'var(--radius-full)',
                          transition: 'width 0.5s ease',
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
