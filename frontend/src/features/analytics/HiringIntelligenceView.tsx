import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Sparkles,
  Users,
  ShieldCheck,
  Clock,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Info,
  RefreshCw,
  Search,
  Filter,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Shield,
  BarChart3,
  MessageSquare,
} from 'lucide-react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { hiringIntelligenceApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';
import type { HiringIntelligenceResponse } from '../../core/types';
import { HiringChatView } from './HiringChatView';

export const HiringIntelligenceView: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') === 'chat' ? 'CHAT' : 'CALIBRATION';
  const [activeTab, setActiveTab] = useState<'CALIBRATION' | 'CHAT'>(initialTab);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedFindingKey, setExpandedFindingKey] = useState<string | null>(null);

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery<HiringIntelligenceResponse>({
    queryKey: ['hiringIntelligence'],
    queryFn: hiringIntelligenceApi.get,
  });

  // Unique categories for filtering
  const categories = useMemo(() => {
    if (!data?.findings) return ['ALL'];
    const cats = new Set<string>();
    data.findings.forEach((f) => {
      if (f.category) cats.add(f.category);
    });
    return ['ALL', ...Array.from(cats)];
  }, [data]);

  // Filtered findings based on category and search text
  const filteredFindings = useMemo(() => {
    if (!data?.findings) return [];
    return data.findings.filter((f) => {
      const matchesCat = selectedCategory === 'ALL' || f.category === selectedCategory;
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        (f.capability_name && f.capability_name.toLowerCase().includes(q)) ||
        f.summary.toLowerCase().includes(q) ||
        f.category.toLowerCase().includes(q);
      return matchesCat && matchesSearch;
    });
  }, [data, selectedCategory, searchQuery]);

  const coverageRatio = useMemo(() => {
    if (!data || data.total_applications === 0) return 0;
    return Math.round((data.applications_with_outcomes / data.total_applications) * 100);
  }, [data]);

  const getCategoryBadgeStyle = (category: string) => {
    switch (category) {
      case 'UNVERIFIED_CAPABILITY':
        return {
          bg: '#FFFBEB',
          text: '#92400E',
          border: '#FDE68A',
          label: 'Unverified Capability',
        };
      case 'OUTCOME_DIVERGENCE':
        return {
          bg: '#FEF2F2',
          text: '#991B1B',
          border: '#FECACA',
          label: 'Outcome Divergence',
        };
      case 'INTERVIEW_COVERAGE_GAP':
        return {
          bg: '#EFF6FF',
          text: '#1E40AF',
          border: '#BFDBFE',
          label: 'Coverage Gap',
        };
      case 'PROCESS_OPPORTUNITY':
        return {
          bg: '#F0FDF4',
          text: '#166534',
          border: '#BBF7D0',
          label: 'Process Opportunity',
        };
      default:
        return {
          bg: '#F8FAFC',
          text: '#475569',
          border: '#E2E8F0',
          label: category.replace(/_/g, ' '),
        };
    }
  };

  const getActionTypeBadgeStyle = (actionType?: string | null) => {
    switch (actionType) {
      case 'ADD_VERIFICATION_STEP':
        return { bg: '#EFF6FF', text: '#1D4ED8', border: '#BFDBFE', label: 'Add Verification Step' };
      case 'EXPAND_INTERVIEW_QUESTIONS':
        return { bg: '#FAF5FF', text: '#7E22CE', border: '#E9D5FF', label: 'Expand Interview Questions' };
      case 'UPDATE_CAPABILITY_BLUEPRINT':
        return { bg: '#F0FDF4', text: '#15803D', border: '#BBF7D0', label: 'Update Blueprint' };
      case 'REFINE_SCREENING_CRITERIA':
        return { bg: '#FFFBEB', text: '#B45309', border: '#FDE68A', label: 'Refine Screening' };
      default:
        return { bg: '#F8FAFC', text: '#475569', border: '#E2E8F0', label: actionType || 'Recommendation' };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Page Header */}
      <PageHeader
        title="Hiring Quality Intelligence"
        description="Evidence-grounded organizational calibration: comparing post-hire work performance with candidate scorecards to systematically improve interview rubrics."
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-base)',
                padding: '0.4rem 0.75rem',
                borderRadius: 'var(--radius-full)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <Shield size={12} style={{ color: 'var(--primary-600)' }} />
              Tenant Isolated
            </span>
            <button
              onClick={() => refetch()}
              disabled={isLoading || isFetching}
              className="btn btn-secondary btn-sm"
              title="Refresh hiring intelligence data"
            >
              <RefreshCw size={14} className={isFetching ? 'spin' : ''} />
              <span>{isFetching ? 'Refreshing...' : 'Refresh'}</span>
            </button>
          </div>
        }
      />

      {/* Navigation Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          borderBottom: '1px solid var(--border-base)',
          paddingBottom: '0.625rem',
        }}
      >
        <button
          type="button"
          onClick={() => {
            setActiveTab('CALIBRATION');
            setSearchParams({});
          }}
          className={`btn btn-sm ${activeTab === 'CALIBRATION' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600 }}
        >
          <BarChart3 size={15} />
          <span>Pipeline Calibration & Rubrics</span>
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab('CHAT');
            setSearchParams({ tab: 'chat' });
          }}
          className={`btn btn-sm ${activeTab === 'CHAT' ? 'btn-primary' : 'btn-secondary'}`}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600 }}
        >
          <Sparkles size={15} />
          <span>HireIQ Intelligence Chat (RAG)</span>
        </button>
      </div>

      {activeTab === 'CHAT' ? (
        <HiringChatView />
      ) : isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem' }}>
            <Skeleton height={110} />
            <Skeleton height={110} />
            <Skeleton height={110} />
            <Skeleton height={110} />
          </div>
          <Skeleton height={320} />
          <Skeleton height={280} />
        </div>
      ) : isError ? (
        /* Error State */
        <div
          className="card"
          style={{
            borderColor: '#FCA5A5',
            backgroundColor: '#FEF2F2',
            padding: '2rem',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              backgroundColor: '#FEE2E2',
              color: '#DC2626',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '1rem',
            }}
          >
            <AlertTriangle size={24} />
          </div>
          <h3 style={{ color: '#991B1B', marginBottom: '0.5rem' }}>Failed to Load Hiring Intelligence</h3>
          <p style={{ color: '#7F1D1D', maxWidth: '520px', margin: '0 auto 1.25rem', fontSize: '0.875rem' }}>
            {(error as any)?.message ||
              'Unable to retrieve aggregated hiring intelligence. Ensure you possess Recruiter or Admin privileges for this organization.'}
          </p>
          <button onClick={() => refetch()} className="btn btn-primary btn-sm">
            Retry Request
          </button>
        </div>
      ) : !data || data.total_applications === 0 ? (
        /* Empty State: 0 Applications */
        <EmptyState
          icon={Users}
          title="No Application Data Available"
          description={
            data?.message ||
            'There are currently no candidate applications registered under this organization tenant. Candidate applications and post-hire observation logs are required to generate hiring quality intelligence.'
          }
          actionText="View Job Pipelines"
          onAction={() => navigate('/jobs')}
        />
      ) : (
        /* Main Dashboard Content */
        <>
          {/* SECTION A: HIRING OVERVIEW (METRIC CARDS) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
                gap: '1.25rem',
              }}
            >
              {/* Card 1: Total Applications */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                      Total Applications
                    </span>
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: 'var(--primary-50)',
                        color: 'var(--primary-600)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Users size={16} />
                    </div>
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                    {data.total_applications}
                  </div>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
                  Candidate applications across tenant jobs
                </div>
              </div>

              {/* Card 2: Applications with Outcomes */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                      With Post-Hire Outcomes
                    </span>
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: '#ECFDF5',
                        color: '#059669',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <ShieldCheck size={16} />
                    </div>
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 700, color: '#059669', letterSpacing: '-0.02em' }}>
                    {data.applications_with_outcomes}
                  </div>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
                  {coverageRatio}% observation coverage rate
                </div>
              </div>

              {/* Card 3: Applications without Outcomes */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                      Without Outcomes
                    </span>
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: '#FFFBEB',
                        color: '#D97706',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Clock size={16} />
                    </div>
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 700, color: '#D97706', letterSpacing: '-0.02em' }}>
                    {data.applications_without_outcomes}
                  </div>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
                  In pipeline or awaiting observation period
                </div>
              </div>

              {/* Card 4: Total Outcome Records */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                      Total Outcome Records
                    </span>
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: '#EFF6FF',
                        color: 'var(--primary-700)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <FileText size={16} />
                    </div>
                  </div>
                  <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                    {data.total_outcome_records}
                  </div>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
                  Observed 30/60/90-day competency records
                </div>
              </div>
            </div>

            {/* Coverage Calibration Notice */}
            <div
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-base)',
                borderRadius: 'var(--radius-md)',
                padding: '0.875rem 1.25rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '1rem',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Info size={18} style={{ color: 'var(--primary-600)', flexShrink: 0 }} />
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  <strong style={{ color: 'var(--text-main)' }}>Calibration Notice:</strong> Unrecorded post-hire
                  outcomes represent active observation windows or pipeline candidates. Missing outcome logs are never
                  treated as negative performance evidence.
                </div>
              </div>

              {data.applications_with_outcomes === 0 && (
                <Link to="/candidates" className="btn btn-secondary btn-sm" style={{ flexShrink: 0 }}>
                  <span>Record Post-Hire Outcomes</span>
                  <ArrowRight size={14} />
                </Link>
              )}
            </div>
          </div>

          {/* Missing Outcomes Banner if 0 outcomes recorded */}
          {data.applications_with_outcomes === 0 ? (
            <div
              className="card"
              style={{
                backgroundColor: '#F8FAFC',
                border: '1px dashed var(--border-strong)',
                textAlign: 'center',
                padding: '3rem 1.5rem',
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  backgroundColor: 'var(--primary-50)',
                  color: 'var(--primary-600)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '1rem',
                }}
              >
                <Sparkles size={24} />
              </div>
              <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', color: 'var(--text-main)' }}>
                Awaiting Post-Hire Work Observations
              </h3>
              <p
                style={{
                  maxWidth: '620px',
                  margin: '0 auto 1.5rem',
                  fontSize: '0.875rem',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.6,
                }}
              >
                {data.message ||
                  'No post-hire outcomes have been recorded for this organization yet. To populate recurring hiring findings and AI rubric recommendations, record 30-day, 60-day, or 90-day performance observations for hired candidates.'}
              </p>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem' }}>
                <Link to="/candidates" className="btn btn-primary btn-sm">
                  Go to Candidate Workspace
                </Link>
                <Link to="/jobs" className="btn btn-secondary btn-sm">
                  View Job Blueprints
                </Link>
              </div>
            </div>
          ) : (
            <>
              {/* SECTION B: RECURRING HIRING FINDINGS */}
              <div className="card" style={{ padding: '1.5rem' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1rem',
                    marginBottom: '1.25rem',
                  }}
                >
                  <div>
                    <h3 style={{ fontSize: '1.15rem', color: 'var(--text-main)' }}>Recurring Process Findings</h3>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                      Patterns where interview evaluations and on-the-job execution observations exhibited divergence.
                    </p>
                  </div>

                  {/* Search and Category Filter */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <div style={{ position: 'relative', width: '220px' }}>
                      <Search
                        size={14}
                        style={{
                          position: 'absolute',
                          left: '0.65rem',
                          top: '50%',
                          transform: 'translateY(-50%)',
                          color: 'var(--text-tertiary)',
                        }}
                      />
                      <input
                        type="text"
                        placeholder="Filter capability or text..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{
                          paddingLeft: '2rem',
                          fontSize: '0.8125rem',
                          width: '100%',
                          height: '34px',
                        }}
                      />
                    </div>

                    {categories.length > 2 && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <Filter size={14} style={{ color: 'var(--text-muted)' }} />
                        <select
                          value={selectedCategory}
                          onChange={(e) => setSelectedCategory(e.target.value)}
                          style={{ height: '34px', fontSize: '0.8125rem' }}
                        >
                          {categories.map((c) => (
                            <option key={c} value={c}>
                              {c === 'ALL' ? 'All Categories' : c.replace(/_/g, ' ')}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                </div>

                {filteredFindings.length === 0 ? (
                  <div
                    style={{
                      padding: '2.5rem',
                      textAlign: 'center',
                      backgroundColor: 'var(--bg-subtle)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px dashed var(--border-base)',
                    }}
                  >
                    <CheckCircle2 size={32} style={{ color: '#059669', margin: '0 auto 0.75rem' }} />
                    <div style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.9375rem' }}>
                      {searchQuery
                        ? 'No findings match your search query.'
                        : 'No recurring capability gaps detected.'}
                    </div>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                      Post-hire observations confirm expected execution across evaluated candidates.
                    </div>
                  </div>
                ) : (
                  <div className="data-table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th style={{ width: '22%' }}>Capability</th>
                          <th style={{ width: '18%' }}>Category</th>
                          <th style={{ width: '42%' }}>Observation & Explanation</th>
                          <th style={{ width: '10%', textAlign: 'center' }}>Applications</th>
                          <th style={{ width: '8%', textAlign: 'right' }}>Provenance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredFindings.map((finding, idx) => {
                          const catBadge = getCategoryBadgeStyle(finding.category);
                          const rowKey = `${finding.category}-${finding.capability_name || 'general'}-${idx}`;
                          const isExpanded = expandedFindingKey === rowKey;

                          return (
                            <React.Fragment key={rowKey}>
                              <tr>
                                <td>
                                  <div style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.875rem' }}>
                                    {finding.capability_name || 'General Pipeline'}
                                  </div>
                                </td>
                                <td>
                                  <span
                                    style={{
                                      fontSize: '0.72rem',
                                      fontWeight: 600,
                                      backgroundColor: catBadge.bg,
                                      color: catBadge.text,
                                      border: `1px solid ${catBadge.border}`,
                                      padding: '0.2rem 0.55rem',
                                      borderRadius: 'var(--radius-full)',
                                      whiteSpace: 'nowrap',
                                    }}
                                  >
                                    {catBadge.label}
                                  </span>
                                </td>
                                <td>
                                  <div
                                    style={{
                                      fontSize: '0.84rem',
                                      color: 'var(--text-secondary)',
                                      lineHeight: 1.45,
                                    }}
                                  >
                                    {finding.summary}
                                  </div>
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                  <span
                                    style={{
                                      fontWeight: 700,
                                      fontSize: '0.875rem',
                                      color: 'var(--text-main)',
                                      backgroundColor: 'var(--bg-subtle)',
                                      padding: '0.2rem 0.6rem',
                                      borderRadius: 'var(--radius-sm)',
                                      border: '1px solid var(--border-base)',
                                    }}
                                  >
                                    {finding.count}
                                  </span>
                                </td>
                                <td style={{ textAlign: 'right' }}>
                                  <button
                                    onClick={() => setExpandedFindingKey(isExpanded ? null : rowKey)}
                                    className="btn btn-ghost btn-sm"
                                    style={{ padding: '0.25rem 0.4rem', fontSize: '0.75rem' }}
                                    title="View underlying reference IDs"
                                  >
                                    <span>{isExpanded ? 'Hide' : 'Refs'}</span>
                                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                  </button>
                                </td>
                              </tr>

                              {/* Expanded Provenance References Panel */}
                              {isExpanded && (
                                <tr>
                                  <td
                                    colSpan={5}
                                    style={{
                                      backgroundColor: 'var(--bg-subtle)',
                                      padding: '1rem 1.25rem',
                                      borderBottom: '1px solid var(--border-base)',
                                    }}
                                  >
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                                      <div
                                        style={{
                                          fontSize: '0.75rem',
                                          fontWeight: 700,
                                          textTransform: 'uppercase',
                                          color: 'var(--text-secondary)',
                                          letterSpacing: '0.04em',
                                        }}
                                      >
                                        Provenance & Audit Trace
                                      </div>

                                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem', fontSize: '0.8125rem' }}>
                                        {/* Application IDs */}
                                        <div>
                                          <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem', fontSize: '0.75rem' }}>
                                            Contributing Applications ({finding.application_ids.length}):
                                          </div>
                                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                                            {finding.application_ids.map((id) => (
                                              <Link
                                                key={id}
                                                to={`/candidates/${id}`}
                                                className="font-mono"
                                                style={{
                                                  backgroundColor: '#FFFFFF',
                                                  border: '1px solid var(--border-base)',
                                                  padding: '0.15rem 0.45rem',
                                                  borderRadius: 'var(--radius-xs)',
                                                  fontSize: '0.75rem',
                                                  color: 'var(--primary-700)',
                                                }}
                                              >
                                                {id.substring(0, 8)}...
                                              </Link>
                                            ))}
                                          </div>
                                        </div>

                                        {/* Job IDs */}
                                        {finding.job_ids.length > 0 && (
                                          <div>
                                            <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem', fontSize: '0.75rem' }}>
                                              Associated Jobs ({finding.job_ids.length}):
                                            </div>
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                                              {finding.job_ids.map((id) => (
                                                <Link
                                                  key={id}
                                                  to={`/jobs/${id}`}
                                                  className="font-mono"
                                                  style={{
                                                    backgroundColor: '#FFFFFF',
                                                    border: '1px solid var(--border-base)',
                                                    padding: '0.15rem 0.45rem',
                                                    borderRadius: 'var(--radius-xs)',
                                                    fontSize: '0.75rem',
                                                    color: 'var(--primary-700)',
                                                  }}
                                                >
                                                  {id.substring(0, 8)}...
                                                </Link>
                                              ))}
                                            </div>
                                          </div>
                                        )}

                                        {/* Outcome IDs */}
                                        {finding.outcome_ids.length > 0 && (
                                          <div>
                                            <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem', fontSize: '0.75rem' }}>
                                              Post-Hire Outcome Logs ({finding.outcome_ids.length}):
                                            </div>
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                                              {finding.outcome_ids.map((id) => (
                                                <span
                                                  key={id}
                                                  className="font-mono"
                                                  style={{
                                                    backgroundColor: '#FFFFFF',
                                                    border: '1px solid var(--border-base)',
                                                    padding: '0.15rem 0.45rem',
                                                    borderRadius: 'var(--radius-xs)',
                                                    fontSize: '0.75rem',
                                                    color: 'var(--text-secondary)',
                                                  }}
                                                >
                                                  {id.substring(0, 8)}...
                                                </span>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* SECTION C: AI IMPROVEMENT RECOMMENDATIONS */}
              <div className="card" style={{ padding: '1.5rem' }}>
                <div style={{ marginBottom: '1.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <div
                      style={{
                        width: 24,
                        height: 24,
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--primary-50)',
                        color: 'var(--primary-600)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Sparkles size={14} />
                    </div>
                    <h3 style={{ fontSize: '1.15rem', color: 'var(--text-main)' }}>
                      AI-Assisted Improvement Recommendations
                    </h3>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    Targeted process calibrations derived from verified recurring gaps. Suggestions are purely advisory
                    and guide rubric expansion without overriding human authority.
                  </p>
                </div>

                {data.recommendations.length === 0 ? (
                  <div
                    style={{
                      padding: '2.5rem',
                      textAlign: 'center',
                      backgroundColor: 'var(--bg-subtle)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px dashed var(--border-base)',
                    }}
                  >
                    <CheckCircle2 size={32} style={{ color: '#059669', margin: '0 auto 0.75rem' }} />
                    <div style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.9375rem' }}>
                      Current Rubric Demonstrates Strong Calibration
                    </div>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                      Interview evaluations and work performance remain aligned. Continue monitoring 90-day outcomes.
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                      gap: '1.25rem',
                    }}
                  >
                    {data.recommendations.map((rec, idx) => {
                      const actionBadge = getActionTypeBadgeStyle(rec.action_type);

                      return (
                        <div
                          key={idx}
                          style={{
                            backgroundColor: 'var(--bg-surface)',
                            border: '1px solid var(--border-base)',
                            borderRadius: 'var(--radius-md)',
                            padding: '1.25rem',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                            gap: '1rem',
                            boxShadow: 'var(--shadow-sm)',
                            transition: 'border-color var(--transition-fast)',
                          }}
                        >
                          <div>
                            {/* Badges Row */}
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                flexWrap: 'wrap',
                                gap: '0.5rem',
                                marginBottom: '0.75rem',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                <span
                                  style={{
                                    fontSize: '0.72rem',
                                    fontWeight: 700,
                                    backgroundColor: 'var(--primary-50)',
                                    color: 'var(--primary-700)',
                                    border: '1px solid var(--primary-100)',
                                    padding: '0.2rem 0.55rem',
                                    borderRadius: 'var(--radius-full)',
                                  }}
                                >
                                  {rec.capability_name || 'General Process'}
                                </span>
                                <span
                                  style={{
                                    fontSize: '0.72rem',
                                    fontWeight: 600,
                                    backgroundColor: actionBadge.bg,
                                    color: actionBadge.text,
                                    border: `1px solid ${actionBadge.border}`,
                                    padding: '0.2rem 0.55rem',
                                    borderRadius: 'var(--radius-full)',
                                  }}
                                >
                                  {actionBadge.label}
                                </span>
                              </div>

                              {rec.confidence_strength && (
                                <span
                                  style={{
                                    fontSize: '0.68rem',
                                    fontWeight: 600,
                                    color: 'var(--text-muted)',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.3rem',
                                  }}
                                >
                                  <span
                                    style={{
                                      width: 6,
                                      height: 6,
                                      borderRadius: '50%',
                                      backgroundColor:
                                        rec.confidence_strength === 'HIGH_CONFIDENCE'
                                          ? '#10B981'
                                          : rec.confidence_strength === 'MODERATE_CONFIDENCE'
                                          ? '#F59E0B'
                                          : '#94A3B8',
                                    }}
                                  />
                                  {rec.confidence_strength.replace(/_/g, ' ')}
                                </span>
                              )}
                            </div>

                            {/* Recommendation Text */}
                            <p
                              style={{
                                fontSize: '0.875rem',
                                fontWeight: 500,
                                color: 'var(--text-main)',
                                lineHeight: 1.5,
                                marginBottom: '0.75rem',
                              }}
                            >
                              {rec.suggestion_text}
                            </p>

                            {/* Supporting Records & Context */}
                            {rec.supporting_records && rec.supporting_records.length > 0 && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.5rem' }}>
                                {rec.supporting_records.map((sr, sIdx) => (
                                  <span
                                    key={sIdx}
                                    style={{
                                      fontSize: '0.7rem',
                                      backgroundColor: 'var(--bg-subtle)',
                                      color: 'var(--text-secondary)',
                                      border: '1px solid var(--border-base)',
                                      padding: '0.15rem 0.45rem',
                                      borderRadius: 'var(--radius-xs)',
                                    }}
                                  >
                                    {sr}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* Footer Info */}
                          <div
                            style={{
                              borderTop: '1px solid var(--border-light)',
                              paddingTop: '0.75rem',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              fontSize: '0.75rem',
                              color: 'var(--text-muted)',
                            }}
                          >
                            <span>
                              Supported by <strong style={{ color: 'var(--text-main)' }}>{rec.count}</strong> candidate
                              application{rec.count > 1 ? 's' : ''}
                            </span>
                            <span style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>
                              Advisory Only • Non-binding
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}

          {/* SECTION D: DATA QUALITY, INTEGRITY & LIMITATIONS */}
          <div
            className="card"
            style={{
              backgroundColor: 'var(--bg-subtle)',
              border: '1px solid var(--border-base)',
              padding: '1.5rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              <ShieldCheck size={20} style={{ color: 'var(--primary-600)' }} />
              <h4 style={{ fontSize: '1rem', color: 'var(--text-main)', margin: 0 }}>
                Data Integrity, Evidence Ethics & Governance Principles
              </h4>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: '1rem',
                marginBottom: '1.25rem',
              }}
            >
              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-base)',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.8125rem', color: 'var(--text-main)', marginBottom: '0.25rem' }}>
                  Missing Outcomes Policy
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                  Unrecorded outcomes represent ongoing 30/60/90-day observation windows or in-pipeline candidates.
                  Missing logs are strictly neutral and never treated as failure signals.
                </div>
              </div>

              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-base)',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.8125rem', color: 'var(--text-main)', marginBottom: '0.25rem' }}>
                  Observational Correlation
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                  Aggregated findings reveal pipeline calibration opportunities between rubrics and workplace observations.
                  They do not imply causation or individual interviewer error.
                </div>
              </div>

              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-base)',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.8125rem', color: 'var(--text-main)', marginBottom: '0.25rem' }}>
                  Sample Calibration
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                  High-confidence suggestions require repeated demonstrations across multiple cohorts before recommending
                  structural rubric or blueprint updates.
                </div>
              </div>

              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-base)',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.8125rem', color: 'var(--text-main)', marginBottom: '0.25rem' }}>
                  Human Authority
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                  AI recommendations are advisory aids. Human HR managers and recruiters retain full ownership over
                  job blueprint edits, interview questions, and candidate hiring outcomes.
                </div>
              </div>
            </div>

            {/* Backend-provided limitations */}
            {data.limitations && data.limitations.length > 0 && (
              <div
                style={{
                  borderTop: '1px solid var(--border-base)',
                  paddingTop: '0.875rem',
                }}
              >
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                  Platform Scope & Analytical Boundaries:
                </div>
                <ul style={{ paddingLeft: '1.25rem', margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {data.limitations.map((lim, lIdx) => (
                    <li key={lIdx} style={{ marginBottom: '0.25rem' }}>
                      {lim}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
