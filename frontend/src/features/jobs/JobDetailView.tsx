import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Sparkles,
  Plus,
  Trash2,
  CheckCircle2,
  Layers,
  Save,
  AlertCircle,
  Brain,
  ShieldCheck,
} from 'lucide-react';
import { jobsApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { Skeleton } from '../../shared/components/Skeleton';
import { Modal } from '../../shared/components/Modal';
import type { CapabilityImportance } from '../../core/types';

export const JobDetailView: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<Array<{
    name: string;
    description: string;
    importance: CapabilityImportance;
  }> | null>(null);

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newCapName, setNewCapName] = useState('');
  const [newCapDesc, setNewCapDesc] = useState('');
  const [newCapImportance, setNewCapImportance] = useState<CapabilityImportance>('MEDIUM');

  const [targetShortlist, setTargetShortlist] = useState<number | null>(null);
  const [shortlistSaving, setShortlistSaving] = useState(false);

  const {
    data: job,
    isLoading: jobLoading,
    refetch: refetchJob,
  } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.get(jobId!),
    enabled: !!jobId,
  });

  const {
    data: capabilities,
    isLoading: capsLoading,
    refetch: refetchCaps,
  } = useQuery({
    queryKey: ['jobCapabilities', jobId],
    queryFn: () => jobsApi.getCapabilities(jobId!),
    enabled: !!jobId,
  });

  const handleRunJDAnalysis = async () => {
    if (!jobId) return;
    setIsAnalyzing(true);
    try {
      const res = await jobsApi.analyzeJD(jobId);
      setAiSuggestions(res.suggested_capabilities);
    } catch (err: any) {
      alert(err.message || 'Failed to extract capabilities from JD');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleApproveAllSuggestions = async () => {
    if (!jobId || !aiSuggestions || aiSuggestions.length === 0) return;
    try {
      await jobsApi.addCapabilitiesBatch(
        jobId,
        aiSuggestions.map((s) => ({
          name: s.name,
          description: s.description,
          importance: s.importance,
        }))
      );
      setAiSuggestions(null);
      refetchCaps();
    } catch (err: any) {
      alert(err.message || 'Failed to batch approve capabilities');
    }
  };

  const handleApproveSingleSuggestion = async (sugg: {
    name: string;
    description: string;
    importance: CapabilityImportance;
  }) => {
    if (!jobId) return;
    try {
      await jobsApi.addCapability(jobId, sugg);
      setAiSuggestions((prev) => prev ? prev.filter((s) => s.name !== sugg.name) : null);
      refetchCaps();
    } catch (err: any) {
      alert(err.message || 'Failed to approve capability');
    }
  };

  const handleAddManualCapability = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobId || !newCapName.trim()) return;
    try {
      await jobsApi.addCapability(jobId, {
        name: newCapName.trim(),
        description: newCapDesc.trim() || undefined,
        importance: newCapImportance,
      });
      setIsAddModalOpen(false);
      setNewCapName('');
      setNewCapDesc('');
      refetchCaps();
    } catch (err: any) {
      alert(err.message || 'Failed to add capability');
    }
  };

  const handleDeleteCapability = async (capId: string) => {
    if (!confirm('Are you sure you want to delete this capability?')) return;
    try {
      await jobsApi.deleteCapability(capId);
      refetchCaps();
    } catch (err: any) {
      alert(err.message || 'Failed to delete capability');
    }
  };

  const handleSaveShortlistSize = async () => {
    if (!jobId || targetShortlist === null) return;
    setShortlistSaving(true);
    try {
      await jobsApi.updateShortlistSize(jobId, targetShortlist);
      refetchJob();
    } catch (err: any) {
      alert(err.message || 'Failed to update shortlist size');
    } finally {
      setShortlistSaving(false);
    }
  };

  if (jobLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <Skeleton height={40} width={250} />
        <Skeleton height={120} />
        <Skeleton height={200} />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <AlertCircle size={32} color="#EF4444" style={{ margin: '0 auto 1rem' }} />
        <h3>Position Not Found</h3>
        <p>The requested position does not exist or you do not have permission.</p>
        <Link to="/jobs" className="btn btn-secondary" style={{ marginTop: '1rem' }}>
          Back to Jobs
        </Link>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={job.title}
        description={`Position ID: ${job.id} • Created on ${new Date(job.created_at).toLocaleDateString()}`}
        badge={<StatusBadge status={job.status} />}
        actions={
          <>
            <Link
              to={`/screening?job_id=${job.id}`}
              className="btn btn-primary"
            >
              <Layers size={16} />
              Open Screening Queue
            </Link>
          </>
        }
      />

      {/* Top Details & Shortlist Control Card */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Shortlist Configuration */}
        <div className="card">
          <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <ShieldCheck size={18} color="var(--primary-600)" />
            Dynamic Shortlist Capacity (Top-N)
          </h4>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            Controls the number of top-ranked candidates automatically advanced into the interview-ready shortlist.
          </p>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <input
              type="number"
              min={1}
              max={200}
              value={targetShortlist !== null ? targetShortlist : job.shortlist_size}
              onChange={(e) => setTargetShortlist(Number(e.target.value))}
              style={{ width: '100px' }}
            />
            <button
              onClick={handleSaveShortlistSize}
              disabled={shortlistSaving || (targetShortlist !== null && targetShortlist === job.shortlist_size)}
              className="btn btn-secondary btn-sm"
            >
              <Save size={14} />
              {shortlistSaving ? 'Updating...' : 'Update Capacity'}
            </button>
          </div>
        </div>

        {/* JD Summary */}
        <div className="card">
          <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>
            Job Description Preview
          </h4>
          <div
            style={{
              fontSize: '0.8125rem',
              color: 'var(--text-secondary)',
              maxHeight: '100px',
              overflowY: 'auto',
              backgroundColor: 'var(--bg-subtle)',
              padding: '0.75rem',
              borderRadius: 'var(--radius-md)',
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
            }}
          >
            {job.description}
          </div>
        </div>
      </div>

      {/* AI Extraction Banner */}
      <div
        className="card"
        style={{
          borderLeft: '4px solid var(--primary-600)',
          marginBottom: '1.5rem',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Brain size={20} color="var(--primary-600)" />
            <h3 style={{ fontSize: '1.1rem' }}>AI Job Description Capability Extraction</h3>
          </div>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Extract required domain and technical competencies from the job description using LLM parsing. Suggestions require HR review and approval.
          </p>
        </div>

        <button
          onClick={handleRunJDAnalysis}
          disabled={isAnalyzing}
          className="btn btn-primary"
        >
          <Sparkles size={16} />
          {isAnalyzing ? 'Analyzing Requirements...' : 'Run JD Extraction'}
        </button>
      </div>

      {/* AI Suggestions Review Area */}
      {aiSuggestions && aiSuggestions.length > 0 && (
        <div
          className="card"
          style={{
            backgroundColor: 'var(--primary-50)',
            borderColor: 'var(--primary-200)',
            marginBottom: '1.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <div>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', fontWeight: 700, color: 'var(--primary-700)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <Sparkles size={13} />
                AI Suggested Requirements ({aiSuggestions.length})
              </div>
              <h4 style={{ fontSize: '1.1rem', marginTop: '0.15rem' }}>Review Suggested Capabilities</h4>
              <p style={{ fontSize: '0.8125rem', color: 'var(--primary-800)' }}>
                These are AI-generated suggestions. Click "Approve All" or approve individually to commit them into the official HR-approved Blueprint.
              </p>
            </div>
            <button
              onClick={handleApproveAllSuggestions}
              className="btn btn-primary btn-sm"
            >
              <CheckCircle2 size={14} />
              Approve All Suggestions
            </button>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: '0.75rem',
            }}
          >
            {aiSuggestions.map((sugg) => (
              <div
                key={sugg.name}
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid var(--primary-200)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.875rem',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{sugg.name}</span>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        padding: '0.15rem 0.45rem',
                        borderRadius: 'var(--radius-full)',
                        backgroundColor: 'var(--primary-100)',
                        color: 'var(--primary-700)',
                      }}
                    >
                      {sugg.importance}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
                    {sugg.description}
                  </p>
                </div>
                <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    onClick={() => handleApproveSingleSuggestion(sugg)}
                    className="btn btn-secondary btn-sm"
                  >
                    <CheckCircle2 size={13} color="#059669" />
                    Approve Capability
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Official HR-Approved Capability Blueprint */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <h3 style={{ fontSize: '1.125rem' }}>Approved Capability Blueprint</h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Official competencies evaluated against resumes, repositories, and autonomous interview questions.
            </p>
          </div>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="btn btn-secondary btn-sm"
          >
            <Plus size={14} />
            Add Capability
          </button>
        </div>

        {capsLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <Skeleton height={45} />
            <Skeleton height={45} />
          </div>
        ) : !capabilities || capabilities.length === 0 ? (
          <div
            style={{
              padding: '2rem',
              textAlign: 'center',
              backgroundColor: 'var(--bg-subtle)',
              borderRadius: 'var(--radius-md)',
              border: '1px dashed var(--border-base)',
            }}
          >
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              No capabilities added to this blueprint yet. Click "Run JD Extraction" above or manually add requirements.
            </p>
          </div>
        ) : (
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Capability Name</th>
                  <th>Description</th>
                  <th>Importance</th>
                  <th>Governance</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {capabilities.map((cap) => (
                  <tr key={cap.id}>
                    <td>
                      <span style={{ fontWeight: 600 }}>{cap.name}</span>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                        {cap.description || '—'}
                      </span>
                    </td>
                    <td>
                      <span
                        style={{
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          padding: '0.15rem 0.5rem',
                          borderRadius: 'var(--radius-full)',
                          backgroundColor:
                            cap.importance === 'CRITICAL'
                              ? '#FEF2F2'
                              : cap.importance === 'HIGH'
                              ? '#FFFBEB'
                              : '#F1F5F9',
                          color:
                            cap.importance === 'CRITICAL'
                              ? '#B91C1C'
                              : cap.importance === 'HIGH'
                              ? '#B45309'
                              : '#475569',
                          border: `1px solid ${
                            cap.importance === 'CRITICAL'
                              ? '#FECACA'
                              : cap.importance === 'HIGH'
                              ? '#FDE68A'
                              : '#CBD5E1'
                          }`,
                        }}
                      >
                        {cap.importance}
                      </span>
                    </td>
                    <td>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                          fontSize: '0.75rem',
                          color: '#059669',
                          fontWeight: 600,
                        }}
                      >
                        <ShieldCheck size={13} />
                        HR Approved
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => handleDeleteCapability(cap.id)}
                        className="btn btn-ghost btn-sm"
                        style={{ color: '#EF4444' }}
                        title="Delete capability"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Manual Capability Add Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Add Capability Requirement"
        subtitle="Manually define a core skill or architectural domain"
      >
        <form onSubmit={handleAddManualCapability} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Capability Name *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Distributed Consensus (Raft / Paxos)"
              style={{ width: '100%' }}
              value={newCapName}
              onChange={(e) => setNewCapName(e.target.value)}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Description / Evaluation Criteria
            </label>
            <textarea
              rows={3}
              placeholder="What evidence or experience should substantiate this capability?"
              style={{ width: '100%' }}
              value={newCapDesc}
              onChange={(e) => setNewCapDesc(e.target.value)}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Importance Level
            </label>
            <select
              style={{ width: '100%' }}
              value={newCapImportance}
              onChange={(e) => setNewCapImportance(e.target.value as CapabilityImportance)}
            >
              <option value="CRITICAL">CRITICAL (Must have demonstrated evidence)</option>
              <option value="HIGH">HIGH (Strong preference)</option>
              <option value="MEDIUM">MEDIUM (Standard expectation)</option>
              <option value="LOW">LOW (Bonus competency)</option>
            </select>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsAddModalOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Add Capability
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
