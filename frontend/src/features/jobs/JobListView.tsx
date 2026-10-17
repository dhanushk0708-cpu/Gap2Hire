import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Briefcase, Plus, Layers, ArrowRight } from 'lucide-react';
import { jobsApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';
import { Modal } from '../../shared/components/Modal';

export const JobListView: React.FC = () => {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [shortlistSize, setShortlistSize] = useState(5);

  const { data: jobs, isLoading, refetch } = useQuery({
    queryKey: ['jobs'],
    queryFn: jobsApi.list,
  });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      await jobsApi.create({
        title: title.trim(),
        description: description.trim() || 'Role requirements pending.',
        shortlist_size: shortlistSize,
      });
      setIsCreateOpen(false);
      setTitle('');
      setDescription('');
      refetch();
    } catch (err: any) {
      alert(err.message || 'Failed to create job');
    }
  };

  return (
    <div>
      <PageHeader
        title="Jobs & Capability Blueprints"
        description="Configure hiring criteria, AI-extracted capability blueprints, and dynamic shortlist capacities."
        actions={
          <button
            onClick={() => setIsCreateOpen(true)}
            className="btn btn-primary"
          >
            <Plus size={16} />
            Create Position
          </button>
        }
      />

      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <Skeleton height={60} />
          <Skeleton height={60} />
          <Skeleton height={60} />
        </div>
      ) : !jobs || jobs.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No open positions found"
          description="Create your first position to begin extracting capability requirements and evaluating candidate evidence."
          actionText="Create Position"
          onAction={() => setIsCreateOpen(true)}
        />
      ) : (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Position Title</th>
                <th>Status</th>
                <th>Target Shortlist</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>
                    <Link
                      to={`/jobs/${job.id}`}
                      style={{ fontWeight: 600, color: 'var(--text-main)' }}
                    >
                      {job.title}
                    </Link>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      ID: {job.id}
                    </div>
                  </td>
                  <td>
                    <StatusBadge status={job.status} />
                  </td>
                  <td>
                    <span style={{ fontWeight: 600 }}>Top-{job.shortlist_size}</span>
                  </td>
                  <td>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                      {new Date(job.created_at).toLocaleDateString()}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '0.5rem' }}>
                      <Link
                        to={`/screening?job_id=${job.id}`}
                        className="btn btn-secondary btn-sm"
                      >
                        <Layers size={13} />
                        Screening
                      </Link>
                      <Link
                        to={`/jobs/${job.id}`}
                        className="btn btn-primary btn-sm"
                      >
                        Blueprint
                        <ArrowRight size={13} />
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create Hiring Position"
        subtitle="Specify position title, description text, and dynamic Top-N capacity"
      >
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Position Title *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Lead Distributed Systems Engineer"
              style={{ width: '100%' }}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Job Description *
            </label>
            <textarea
              required
              rows={6}
              placeholder="Paste complete job description or responsibilities..."
              style={{ width: '100%' }}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Target Dynamic Shortlist Size (Top-N)
            </label>
            <input
              type="number"
              min={1}
              max={100}
              style={{ width: '100%' }}
              value={shortlistSize}
              onChange={(e) => setShortlistSize(Number(e.target.value))}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsCreateOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Create Position
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
