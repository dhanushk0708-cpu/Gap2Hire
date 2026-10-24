import React, { useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Play,
  Sparkles,
  Mail,
  Sliders,
  Layers,
  ArrowRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  Target,
  Star,
} from 'lucide-react';
import { jobsApi, screeningApi, demoApi, emailApi, interviewSessionsApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { TopNBanner } from '../../shared/components/TopNBanner';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';
import { Modal } from '../../shared/components/Modal';

export const ScreeningQueueView: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedJobId = searchParams.get('job_id') || '';

  const [isAdjustShortlistOpen, setIsAdjustShortlistOpen] = useState(false);
  const [newShortlistSize, setNewShortlistSize] = useState(5);
  const [isUpdatingShortlistSize, setIsUpdatingShortlistSize] = useState(false);
  const [isDemoModalOpen, setIsDemoModalOpen] = useState(false);
  const [demoFile, setDemoFile] = useState<File | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [isSyncingEmail, setIsSyncingEmail] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [isRunningScreening, setIsRunningScreening] = useState(false);
  const [startingInterviewAppId, setStartingInterviewAppId] = useState<string | null>(null);
  const [shortlistingAppId, setShortlistingAppId] = useState<string | null>(null);

  // Load all jobs
  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: jobsApi.list,
  });

  const activeJobId = selectedJobId || (jobs && jobs.length > 0 ? jobs[0].id : '');

  // Load active job details
  const { data: currentJob, refetch: refetchCurrentJob } = useQuery({
    queryKey: ['job', activeJobId],
    queryFn: () => jobsApi.get(activeJobId),
    enabled: !!activeJobId,
  });

  // Load candidates for this job
  const {
    data: candidates,
    isLoading: candidatesLoading,
    refetch: refetchCandidates,
  } = useQuery({
    queryKey: ['jobCandidates', activeJobId],
    queryFn: () => screeningApi.getJobCandidates(activeJobId),
    enabled: !!activeJobId,
  });

  // Load Top-N summary
  const { data: topNResult, refetch: refetchTopN } = useQuery({
    queryKey: ['jobTopN', activeJobId],
    queryFn: () => screeningApi.getJobTopN(activeJobId),
    enabled: !!activeJobId,
  });

  const handleSelectJob = (id: string) => {
    setSearchParams({ job_id: id });
  };

  const handleRunScreening = async () => {
    if (!activeJobId) return;
    setIsRunningScreening(true);
    try {
      await screeningApi.runJobScreening(activeJobId);
      await Promise.all([refetchCandidates(), refetchTopN()]);
    } catch (err: any) {
      alert(err.message || 'Screening execution failed');
    } finally {
      setIsRunningScreening(false);
    }
  };

  const handleAdjustShortlist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeJobId) return;
    try {
      await jobsApi.updateShortlistSize(activeJobId, newShortlistSize);
      setIsAdjustShortlistOpen(false);
      await Promise.all([refetchCurrentJob(), refetchTopN(), refetchCandidates()]);
    } catch (err: any) {
      alert(err.message || 'Failed to update shortlist capacity');
    }
  };

  const handleQuickChangeShortlistSize = async (newSize: number) => {
    if (!activeJobId || newSize === currentJob?.shortlist_size) return;
    setIsUpdatingShortlistSize(true);
    try {
      await jobsApi.updateShortlistSize(activeJobId, newSize);
      await Promise.all([refetchCurrentJob(), refetchTopN(), refetchCandidates()]);
    } catch (err: any) {
      alert(err.message || 'Failed to update shortlist target');
    } finally {
      setIsUpdatingShortlistSize(false);
    }
  };

  const handleDemoImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!demoFile || !activeJobId) return;
    setDemoLoading(true);
    try {
      const res = await demoApi.importResumes(demoFile, activeJobId);
      alert(`Imported ${res.imported_count} demo resumes!`);
      setIsDemoModalOpen(false);
      setDemoFile(null);
      await Promise.all([refetchCandidates(), refetchTopN()]);
    } catch (err: any) {
      alert(err.message || 'Failed to import demo resumes');
    } finally {
      setDemoLoading(false);
    }
  };

  const handleSyncEmails = async () => {
    if (!activeJobId) return;
    setIsSyncingEmail(true);
    setSyncResult(null);
    try {
      const res = await emailApi.sync(10, activeJobId);
      const skippedCount = res.duplicates_skipped ?? 0;
      const importedCount = res.resumes_processed ?? 0;
      const fetchedCount = res.emails_fetched ?? 0;
      const failedCount = res.failures ?? 0;
      setSyncResult(
        `Gmail Intake Summary — Fetched: ${fetchedCount} | Imported: ${importedCount} | Skipped: ${skippedCount} | Failed: ${failedCount}`
      );
      await Promise.all([refetchCandidates(), refetchTopN()]);
    } catch (err: any) {
      alert(err.message || 'Email sync failed');
    } finally {
      setIsSyncingEmail(false);
    }
  };

  const handleManualShortlist = async (appId: string) => {
    setShortlistingAppId(appId);
    try {
      await screeningApi.shortlistCandidate(appId, 'SHORTLISTED', 'Manually shortlisted by HR');
      await Promise.all([refetchCandidates(), refetchTopN()]);
    } catch (err: any) {
      alert(err.message || 'Failed to shortlist candidate');
    } finally {
      setShortlistingAppId(null);
    }
  };

  const handleDirectStartInterview = async (appId: string) => {
    setStartingInterviewAppId(appId);
    try {
      const session = await interviewSessionsApi.create(appId);
      navigate(`/interview-room/${session.id}`);
    } catch (err: any) {
      alert(err.message || 'Failed to start interview session');
      setStartingInterviewAppId(null);
    }
  };

  const shortlistedCount = candidates?.filter((c) => c.shortlist_status === 'SHORTLISTED').length || 0;
  const totalEvaluated = candidates?.length || 0;

  return (
    <div>
      <PageHeader
        title="Candidate Screening & Dynamic Top-N"
        description="Structured requirement matching, non-presumptive evidence evaluation, and dynamic shortlist movement."
        actions={
          <>
            <button
              onClick={() => setIsDemoModalOpen(true)}
              className="btn btn-secondary"
              title="Import synthetic candidate resumes"
            >
              <Sparkles size={15} color="#9333EA" />
              Demo Resumes
            </button>
            <button
              onClick={handleSyncEmails}
              disabled={isSyncingEmail}
              className="btn btn-secondary"
              title="Fetch new candidate applications via email integration"
            >
              <Mail size={15} />
              {isSyncingEmail ? 'Syncing...' : 'Load New Resumes'}
            </button>
            <button
              onClick={handleRunScreening}
              disabled={isRunningScreening || !activeJobId}
              className="btn btn-primary"
            >
              <Play size={15} />
              {isRunningScreening ? 'Evaluating Evidence...' : 'Run Job Screening'}
            </button>
          </>
        }
      />

      {/* Job Selector Bar */}
      <div
        className="card"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          marginBottom: '1.25rem',
          padding: '0.875rem 1.25rem',
          flexWrap: 'wrap',
        }}
      >
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)', whiteSpace: 'nowrap' }}>
          Select Position:
        </span>
        <select
          value={activeJobId}
          onChange={(e) => handleSelectJob(e.target.value)}
          style={{ maxWidth: '350px', flex: 1 }}
        >
          {jobsLoading ? (
            <option>Loading positions...</option>
          ) : !jobs || jobs.length === 0 ? (
            <option>No positions available</option>
          ) : (
            jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title} ({j.status}) — Top-{j.shortlist_size}
              </option>
            ))
          )}
        </select>
        {activeJobId && (
          <Link
            to={`/jobs/${activeJobId}`}
            className="btn btn-ghost btn-sm"
            style={{ fontSize: '0.8125rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
          >
            Position Blueprint <ExternalLink size={13} />
          </Link>
        )}

        {/* Shortlist Target Quick Selector */}
        {activeJobId && currentJob && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginLeft: 'auto' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-main)', whiteSpace: 'nowrap' }}>
              Shortlist Target:
            </span>
            <select
              id="header-shortlist-target-select"
              value={[3, 5, 10, 15, 20].includes(currentJob.shortlist_size) ? currentJob.shortlist_size : 'custom'}
              onChange={(e) => {
                if (e.target.value === 'custom') {
                  setNewShortlistSize(currentJob.shortlist_size);
                  setIsAdjustShortlistOpen(true);
                } else {
                  handleQuickChangeShortlistSize(Number(e.target.value));
                }
              }}
              disabled={isUpdatingShortlistSize}
              style={{
                fontSize: '0.8125rem',
                fontWeight: 600,
                padding: '0.35rem 0.65rem',
                borderRadius: 'var(--radius-sm)',
                minWidth: '95px',
                cursor: 'pointer',
              }}
            >
              <option value={3}>Top-3</option>
              <option value={5}>Top-5</option>
              <option value={10}>Top-10</option>
              <option value={15}>Top-15</option>
              <option value={20}>Top-20</option>
              <option value="custom">
                {[3, 5, 10, 15, 20].includes(currentJob.shortlist_size) ? 'Custom...' : `Custom (Top-${currentJob.shortlist_size})`}
              </option>
            </select>
          </div>
        )}
      </div>

      {syncResult && (
        <div
          style={{
            padding: '0.75rem 1rem',
            backgroundColor: '#EFF6FF',
            border: '1px solid #BFDBFE',
            borderRadius: 'var(--radius-md)',
            color: '#1D4ED8',
            fontSize: '0.8125rem',
            marginBottom: '1.25rem',
          }}
        >
          {syncResult}
        </div>
      )}

      {/* Top-N Capacity Banner */}
      {currentJob && (
        <TopNBanner
          shortlistSize={currentJob.shortlist_size}
          evaluatedCount={totalEvaluated}
          shortlistedCount={shortlistedCount}
          onSelectSize={handleQuickChangeShortlistSize}
          isUpdatingSize={isUpdatingShortlistSize}
          onAdjustSize={() => {
            setNewShortlistSize(currentJob.shortlist_size);
            setIsAdjustShortlistOpen(true);
          }}
        />
      )}

      {/* Candidate Pipeline Table */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <h3 style={{ fontSize: '1.125rem' }}>Screening Queue & Candidate Roster</h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Deterministic evidence evaluated across resumes, sources, and verified credentials.
            </p>
          </div>
        </div>

        {candidatesLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <Skeleton height={50} />
            <Skeleton height={50} />
            <Skeleton height={50} />
          </div>
        ) : !candidates || candidates.length === 0 ? (
          <EmptyState
            icon={Layers}
            title="No candidates in screening queue"
            description="Use 'Demo Resumes' or 'Load New Resumes' above to ingest applicant profiles for this role."
          />
        ) : (
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Application Status</th>
                  <th>Shortlist Status</th>
                  <th>Applied Date</th>
                  <th>Interview Ready</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((cand) => (
                  <tr key={cand.application_id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Link
                          to={`/candidates/${cand.application_id}`}
                          style={{ fontWeight: 600, color: 'var(--text-main)' }}
                        >
                          {cand.candidate_name}
                        </Link>
                        {cand.is_demo && (
                          <span
                            style={{
                              fontSize: '0.65rem',
                              fontWeight: 700,
                              padding: '0.1rem 0.4rem',
                              borderRadius: '9999px',
                              backgroundColor: 'var(--badge-demo-bg)',
                              color: 'var(--badge-demo-text)',
                              border: '1px solid var(--badge-demo-border)',
                            }}
                          >
                            DEMO
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {cand.candidate_email}
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={cand.status} />
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
                        <StatusBadge status={cand.shortlist_status} />
                        {cand.shortlist_reason?.toLowerCase().includes('manually') && (
                          <span
                            style={{
                              fontSize: '0.65rem',
                              fontWeight: 700,
                              padding: '0.1rem 0.4rem',
                              borderRadius: '4px',
                              backgroundColor: '#FEF3C7',
                              color: '#B45309',
                              border: '1px solid #FDE68A',
                            }}
                          >
                            Manually shortlisted
                          </span>
                        )}
                      </div>
                      {cand.shortlist_reason && !cand.shortlist_reason.toLowerCase().includes('manually') && (
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.2rem', maxWidth: '240px' }}>
                          {cand.shortlist_reason}
                        </div>
                      )}
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                        {new Date(cand.applied_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td>
                      {cand.is_interview_ready ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: '#059669', fontWeight: 600 }}>
                          <CheckCircle2 size={13} />
                          Ready
                        </span>
                      ) : (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          <Clock size={13} />
                          In Review
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', justifyContent: 'flex-end' }}>
                        {cand.shortlist_status === 'SHORTLISTED' || cand.is_interview_ready ? (
                          <button
                            onClick={() => handleDirectStartInterview(cand.application_id)}
                            disabled={startingInterviewAppId === cand.application_id}
                            className="btn btn-sm"
                            style={{
                              backgroundColor: '#059669',
                              color: '#FFFFFF',
                              border: 'none',
                              fontWeight: 600,
                              padding: '0.35rem 0.65rem',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.3rem',
                            }}
                            title="Start live AI interview now (No scheduling required)"
                          >
                            <Play size={12} fill="#FFFFFF" />
                            {startingInterviewAppId === cand.application_id ? 'Starting...' : 'Start Interview'}
                          </button>
                        ) : (
                          <button
                            onClick={() => handleManualShortlist(cand.application_id)}
                            disabled={shortlistingAppId === cand.application_id}
                            className="btn btn-secondary btn-sm"
                            style={{
                              padding: '0.35rem 0.65rem',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.3rem',
                              color: '#B45309',
                            }}
                            title="Manually shortlist candidate for immediate interview"
                          >
                            <Star size={12} color="#D97706" fill="#FDE68A" />
                            {shortlistingAppId === cand.application_id ? 'Shortlisting...' : 'Shortlist'}
                          </button>
                        )}
                        <Link
                          to={`/candidates/${cand.application_id}`}
                          className="btn btn-secondary btn-sm"
                          style={{ padding: '0.35rem 0.65rem' }}
                        >
                          Workspace
                          <ArrowRight size={12} />
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

      {/* Adjust Shortlist Capacity Modal */}
      <Modal
        isOpen={isAdjustShortlistOpen}
        onClose={() => setIsAdjustShortlistOpen(false)}
        title="Configure Top-N Shortlist Capacity"
        subtitle="Set the target shortlist size for dynamic queue evaluation"
      >
        <form onSubmit={handleAdjustShortlist} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Target Shortlist Size (Top-N)
            </label>
            <input
              type="number"
              min={1}
              max={100}
              required
              style={{ width: '100%' }}
              value={newShortlistSize}
              onChange={(e) => setNewShortlistSize(Number(e.target.value))}
            />
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
              When screening runs, the top N candidates meeting critical requirements are placed in the shortlist.
            </p>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsAdjustShortlistOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Save Capacity
            </button>
          </div>
        </form>
      </Modal>

      {/* Demo ZIP Upload Modal */}
      <Modal
        isOpen={isDemoModalOpen}
        onClose={() => setIsDemoModalOpen(false)}
        title="Import Demo Candidate Resumes ZIP"
        subtitle="Ingest synthetic PDF resumes into the screening queue"
      >
        <form onSubmit={handleDemoImport} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
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
              disabled={demoLoading || !demoFile}
              className="btn btn-primary"
            >
              {demoLoading ? 'Ingesting...' : 'Import Resumes'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
