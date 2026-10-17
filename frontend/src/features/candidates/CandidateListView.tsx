import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Users, ArrowRight, FileText } from 'lucide-react';
import { applicationsApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';

export const CandidateListView: React.FC = () => {
  const { data: applications, isLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: () => applicationsApi.list(),
  });

  return (
    <div>
      <PageHeader
        title="Candidate Talent Pool"
        description="Comprehensive directory of candidate applications across all hiring positions."
      />

      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <Skeleton height={55} />
          <Skeleton height={55} />
          <Skeleton height={55} />
        </div>
      ) : !applications || applications.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No candidates in talent pool"
          description="Candidates will appear here once applications are ingested through email, demo ZIPs, or API uploads."
        />
      ) : (
        <div className="card">
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Application ID</th>
                  <th>Status</th>
                  <th>Resume</th>
                  <th>Applied Date</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr key={app.id}>
                    <td>
                      <Link
                        to={`/candidates/${app.id}`}
                        style={{ fontWeight: 600, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}
                      >
                        {app.id}
                      </Link>
                    </td>
                    <td>
                      <StatusBadge status={app.status} />
                    </td>
                    <td>
                      {app.resume_path ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: '#059669', fontWeight: 600 }}>
                          <FileText size={14} />
                          Uploaded
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          No resume
                        </span>
                      )}
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                        {new Date(app.applied_at || app.created_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <Link
                        to={`/candidates/${app.id}`}
                        className="btn btn-primary btn-sm"
                      >
                        Workspace
                        <ArrowRight size={13} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
