import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Briefcase,
  Users,
  Award,
  Clock,
  Plus,
  ArrowRight,
  ShieldCheck,
  Layers,
  Sparkles,
  Upload,
} from 'lucide-react';
import { jobsApi, applicationsApi, demoApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';
import { Modal } from '../../shared/components/Modal';

export const DashboardScreen: React.FC = () => {
  const [isCreateJobOpen, setIsCreateJobOpen] = useState(false);
  const [isDemoModalOpen, setIsDemoModalOpen] = useState(false);
  const [newJobTitle, setNewJobTitle] = useState('');
  const [newJobDesc, setNewJobDesc] = useState('');
  const [newJobShortlist, setNewJobShortlist] = useState(5);
  const [selectedDemoJobId, setSelectedDemoJobId] = useState('');
  const [demoFile, setDemoFile] = useState<File | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoMessage, setDemoMessage] = useState<string | null>(null);

  const {
    data: jobs,
    isLoading: jobsLoading,
    refetch: refetchJobs,
  } = useQuery({
    queryKey: ['jobs'],
    queryFn: jobsApi.list,
  });

  const {
    data: applications,
    isLoading: appsLoading,
  } = useQuery({
    queryKey: ['applications'],
    queryFn: () => applicationsApi.list(),
  });

  const handleCreateJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newJobTitle.trim()) return;
    try {
      await jobsApi.create({
        title: newJobTitle.trim(),
        description: newJobDesc.trim() || 'Role requirements pending extraction.',
        shortlist_size: newJobShortlist,
      });
      setIsCreateJobOpen(false);
      setNewJobTitle('');
      setNewJobDesc('');
      refetchJobs();
    } catch (err: any) {
      alert(err.message || 'Error creating job');
    }
  };

  const handleDemoImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!demoFile || !selectedDemoJobId) return;
    setDemoLoading(true);
    setDemoMessage(null);
    try {
      const res = await demoApi.importResumes(demoFile, selectedDemoJobId);
      setDemoMessage(`Successfully ingested ${res.imported_count} candidate resumes!`);
      setTimeout(() => {
        setIsDemoModalOpen(false);
        setDemoMessage(null);
        setDemoFile(null);
      }, 1500);
    } catch (err: any) {
      alert(err.message || 'Error importing demo resumes');
    } finally {
      setDemoLoading(false);
    }
  };

  const activeJobs = jobs?.filter((j) => j.status === 'ACTIVE') || [];
  const totalCandidates = applications?.length || 0;
  const hiredCandidates = applications?.filter((a) => a.status === 'HIRED').length || 0;
  const inReviewCandidates = applications?.filter((a) => a.status === 'IN_REVIEW' || a.status === 'APPLIED').length || 0;

  return (
    <div>
      <PageHeader
        title="Evidence-Based Talent Intelligence"
        description="Monitor candidate capabilities, autonomous multi-round interviews, and human decision governance across active roles."
        actions={
          <>
            <button
              onClick={() => setIsDemoModalOpen(true)}
              className="btn btn-secondary"
            >
              <Sparkles size={16} color="#9333EA" />
              Demo Resume ZIP
            </button>
            <button
              onClick={() => setIsCreateJobOpen(true)}
              className="btn btn-primary"
            >
              <Plus size={16} />
              Create Job
            </button>
          </>
        }
      />

      {/* Top Metric Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.75rem',
        }}
      >
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Active Jobs</span>
            <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-md)', backgroundColor: 'var(--primary-50)', color: 'var(--primary-600)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Briefcase size={18} />
            </div>
          </div>
          {jobsLoading ? (
            <Skeleton height={32} width={60} />
          ) : (
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-main)' }}>
              {activeJobs.length}
            </div>
          )}
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {jobs?.length || 0} total roles configured
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Total Candidates</span>
            <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-md)', backgroundColor: '#F0FDF4', color: '#16A34A', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Users size={18} />
            </div>
          </div>
          {appsLoading ? (
            <Skeleton height={32} width={60} />
          ) : (
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-main)' }}>
              {totalCandidates}
            </div>
          )}
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Across all pipeline stages
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Screening Queue</span>
            <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-md)', backgroundColor: '#FFFBEB', color: '#D97706', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Clock size={18} />
            </div>
          </div>
          {appsLoading ? (
            <Skeleton height={32} width={60} />
          ) : (
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-main)' }}>
              {inReviewCandidates}
            </div>
          )}
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Pending evidence evaluation
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Hired / Selected</span>
            <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-md)', backgroundColor: '#ECFDF5', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Award size={18} />
            </div>
          </div>
          {appsLoading ? (
            <Skeleton height={32} width={60} />
          ) : (
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#059669' }}>
              {hiredCandidates}
            </div>
          )}
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Human-approved selections
          </div>
        </div>
      </div>

      {/* Main Section: Active Jobs Pipeline */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <h3 style={{ fontSize: '1.125rem' }}>Active Positions & Capability Blueprints</h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Manage requirements, run AI screening, and observe live interviews.
            </p>
          </div>
          <Link to="/jobs" className="btn btn-secondary btn-sm">
            View All Jobs
            <ArrowRight size={14} />
          </Link>
        </div>

        {jobsLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <Skeleton height={50} />
            <Skeleton height={50} />
            <Skeleton height={50} />
          </div>
        ) : !jobs || jobs.length === 0 ? (
          <EmptyState
            icon={Briefcase}
            title="No jobs created yet"
            description="Create your first job description to extract required capabilities and start evaluating candidate evidence."
            actionText="Create Job"
            onAction={() => setIsCreateJobOpen(true)}
          />
        ) : (
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job Title</th>
                  <th>Status</th>
                  <th>Target Shortlist</th>
                  <th>Created</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.slice(0, 5).map((job) => (
                  <tr key={job.id}>
                    <td>
                      <Link to={`/jobs/${job.id}`} style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                        {job.title}
                      </Link>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        ID: {job.id.slice(0, 8)}...
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
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Job Modal */}
      <Modal
        isOpen={isCreateJobOpen}
        onClose={() => setIsCreateJobOpen(false)}
        title="Create Job Position"
        subtitle="Define a new role and configure its initial shortlist size"
      >
        <form onSubmit={handleCreateJob} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Role Title *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Senior Backend Engineer"
              style={{ width: '100%' }}
              value={newJobTitle}
              onChange={(e) => setNewJobTitle(e.target.value)}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Job Description (JD) *
            </label>
            <textarea
              required
              rows={5}
              placeholder="Paste job description text here for automated capability extraction..."
              style={{ width: '100%' }}
              value={newJobDesc}
              onChange={(e) => setNewJobDesc(e.target.value)}
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
              value={newJobShortlist}
              onChange={(e) => setNewJobShortlist(Number(e.target.value))}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsCreateJobOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Create Job
            </button>
          </div>
        </form>
      </Modal>

      {/* Demo Resume Import Modal */}
      <Modal
        isOpen={isDemoModalOpen}
        onClose={() => setIsDemoModalOpen(false)}
        title="Import Demo Resumes ZIP"
        subtitle="Ingest synthetic demonstration resumes without touching live Gmail pipelines"
      >
        <form onSubmit={handleDemoImport} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {demoMessage && (
            <div style={{ padding: '0.75rem', backgroundColor: '#ECFDF5', color: '#047857', borderRadius: 'var(--radius-md)', fontSize: '0.8125rem', border: '1px solid #A7F3D0' }}>
              {demoMessage}
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Target Job *
            </label>
            <select
              required
              style={{ width: '100%' }}
              value={selectedDemoJobId}
              onChange={(e) => setSelectedDemoJobId(e.target.value)}
            >
              <option value="">-- Select Target Job --</option>
              {jobs?.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} ({j.status})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Select ZIP Archive (.zip) *
            </label>
            <input
              type="file"
              accept=".zip"
              required
              style={{ width: '100%' }}
              onChange={(e) => setDemoFile(e.target.files?.[0] || null)}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsDemoModalOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={demoLoading || !demoFile || !selectedDemoJobId}
              className="btn btn-primary"
            >
              <Upload size={16} />
              {demoLoading ? 'Ingesting ZIP...' : 'Import Resumes'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
