import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Calendar as CalendarIcon,
  Clock,
  Video,
  MapPin,
  User,
  Plus,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Mail,
  Share2,
  ExternalLink,
  ChevronRight,
  Eye,
  RefreshCw,
  Copy,
  Info,
  CalendarDays,
  List,
} from 'lucide-react';
import {
  interviewSchedulerApi,
  applicationsApi,
} from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';
import { Modal } from '../../shared/components/Modal';
import type {
  InterviewScheduleResponse,
  SimulatedNotificationItem,
} from '../../core/types';

export const InterviewSchedulerView: React.FC = () => {
  const queryClient = useQueryClient();

  // Filters state
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [candidateSearch, setCandidateSearch] = useState<string>('');
  const [interviewerFilter, setInterviewerFilter] = useState<string>('');
  const [dateFilter, setDateFilter] = useState<string>('');
  const [viewMode, setViewMode] = useState<'list' | 'agenda'>('list');

  // Modals state
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [isRescheduleModalOpen, setIsRescheduleModalOpen] = useState(false);
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);
  const [isNotificationsModalOpen, setIsNotificationsModalOpen] = useState(false);
  const [isPublishSlotsModalOpen, setIsPublishSlotsModalOpen] = useState(false);

  // Selected schedule state
  const [selectedSchedule, setSelectedSchedule] = useState<InterviewScheduleResponse | null>(null);

  // Form states
  const [formAppId, setFormAppId] = useState('');
  const [formInterviewerId, setFormInterviewerId] = useState('');
  const [formStartTime, setFormStartTime] = useState('');
  const [formDuration, setFormDuration] = useState(45);
  const [formType, setFormType] = useState('ONLINE');
  const [formLocation, setFormLocation] = useState('');
  const [formNotes, setFormNotes] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Reschedule form state
  const [rescheduleStart, setRescheduleStart] = useState('');
  const [rescheduleDuration, setRescheduleDuration] = useState(45);
  const [rescheduleReason, setRescheduleReason] = useState('');

  // Cancel form state
  const [cancelReason, setCancelReason] = useState('');

  // Publish slots form state
  const [publishAppId, setPublishAppId] = useState('');
  const [publishInterviewerId, setPublishInterviewerId] = useState('');
  const [publishSlotsList, setPublishSlotsList] = useState<string[]>([
    '',
    '',
    '',
  ]);
  const [publishedResult, setPublishedResult] = useState<{
    booking_token: string;
    booking_url: string;
    total_slots: number;
  } | null>(null);

  // Copy feedback
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2500);
  };

  // Queries
  const {
    data: interviews,
    isLoading: interviewsLoading,
    refetch: refetchInterviews,
  } = useQuery({
    queryKey: ['interviews', statusFilter, candidateSearch, interviewerFilter, dateFilter],
    queryFn: () =>
      interviewSchedulerApi.list({
        status: statusFilter || undefined,
        candidate: candidateSearch || undefined,
        interviewer_id: interviewerFilter || undefined,
        date: dateFilter || undefined,
      }),
  });

  const { data: interviewers } = useQuery({
    queryKey: ['interviewers'],
    queryFn: () => interviewSchedulerApi.getInterviewers(),
  });

  const { data: applications } = useQuery({
    queryKey: ['applicationsForSchedule'],
    queryFn: () => applicationsApi.list(),
  });

  const {
    data: activeNotifications,
    isLoading: notifsLoading,
  } = useQuery({
    queryKey: ['interviewNotifications', selectedSchedule?.id],
    queryFn: () =>
      selectedSchedule
        ? interviewSchedulerApi.getNotifications({ schedule_id: selectedSchedule.id })
        : Promise.resolve([]),
    enabled: !!selectedSchedule && isNotificationsModalOpen,
  });

  // Mutations
  const scheduleMutation = useMutation({
    mutationFn: (data: any) => interviewSchedulerApi.schedule(data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['interviews'] });
      setIsScheduleModalOpen(false);
      setSuccessMessage(`Interview scheduled successfully! Reference: ${res.interview_reference}`);
      setTimeout(() => setSuccessMessage(null), 5000);
      resetScheduleForm();
    },
    onError: (err: any) => {
      setErrorMessage(err.message || 'Failed to schedule interview.');
    },
  });

  const rescheduleMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      interviewSchedulerApi.reschedule(id, data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['interviews'] });
      setIsRescheduleModalOpen(false);
      setSuccessMessage(`Interview rescheduled! Notification dispatched (DEMO).`);
      setTimeout(() => setSuccessMessage(null), 5000);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || 'Failed to reschedule.');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      interviewSchedulerApi.cancel(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['interviews'] });
      setIsCancelModalOpen(false);
      setSuccessMessage('Interview cancelled and simulated notification sent.');
      setTimeout(() => setSuccessMessage(null), 5000);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || 'Failed to cancel interview.');
    },
  });

  const completeMutation = useMutation({
    mutationFn: (id: string) => interviewSchedulerApi.complete(id),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['interviews'] });
      setSuccessMessage(
        `Interview marked COMPLETED! Ready for post-interview scorecard generation.`
      );
      setTimeout(() => setSuccessMessage(null), 5000);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || 'Failed to mark interview completed.');
    },
  });

  const publishSlotsMutation = useMutation({
    mutationFn: ({ appId, data }: { appId: string; data: any }) =>
      interviewSchedulerApi.publishSlots(appId, data),
    onSuccess: (res) => {
      setPublishedResult(res);
      queryClient.invalidateQueries({ queryKey: ['interviews'] });
    },
    onError: (err: any) => {
      setErrorMessage(err.message || 'Failed to publish self-booking slots.');
    },
  });

  const resetScheduleForm = () => {
    setFormAppId('');
    setFormInterviewerId('');
    setFormStartTime('');
    setFormDuration(45);
    setFormType('ONLINE');
    setFormLocation('');
    setFormNotes('');
    setErrorMessage(null);
  };

  const handleCreateSchedule = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    if (!formAppId) {
      setErrorMessage('Please select a candidate application.');
      return;
    }
    if (!formStartTime) {
      setErrorMessage('Please select a scheduled start date and time.');
      return;
    }
    scheduleMutation.mutate({
      application_id: formAppId,
      interviewer_id: formInterviewerId || undefined,
      scheduled_start: new Date(formStartTime).toISOString(),
      duration_minutes: formDuration,
      interview_type: formType,
      location: formLocation || undefined,
      invitation_notes: formNotes || undefined,
    });
  };

  const handleReschedule = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSchedule || !rescheduleStart) return;
    setErrorMessage(null);
    rescheduleMutation.mutate({
      id: selectedSchedule.id,
      data: {
        scheduled_start: new Date(rescheduleStart).toISOString(),
        duration_minutes: rescheduleDuration,
        reschedule_reason: rescheduleReason || undefined,
      },
    });
  };

  const handleCancel = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSchedule || !cancelReason.trim()) {
      setErrorMessage('Please provide a cancellation reason.');
      return;
    }
    cancelMutation.mutate({
      id: selectedSchedule.id,
      reason: cancelReason,
    });
  };

  const handlePublishSlots = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    if (!publishAppId || !publishInterviewerId) {
      setErrorMessage('Application and interviewer are required.');
      return;
    }
    const validSlotTimes = publishSlotsList.filter((s) => s.trim().length > 0);
    if (validSlotTimes.length === 0) {
      setErrorMessage('Please enter at least one future slot date and time.');
      return;
    }
    publishSlotsMutation.mutate({
      appId: publishAppId,
      data: {
        interviewer_id: publishInterviewerId,
        interview_type: 'ONLINE',
        slots: validSlotTimes.map((t) => ({
          start_time: new Date(t).toISOString(),
          duration_minutes: 45,
        })),
      },
    });
  };

  // Stats calculation
  const totalCount = interviews?.length || 0;
  const scheduledCount = interviews?.filter((i) => i.status === 'SCHEDULED' || i.status === 'CONFIRMED').length || 0;
  const completedCount = interviews?.filter((i) => i.status === 'COMPLETED').length || 0;
  const cancelledCount = interviews?.filter((i) => i.status === 'CANCELLED').length || 0;

  return (
    <div className="interview-scheduler-page" style={{ paddingBottom: '3rem' }}>
      <PageHeader
        title="Interview Scheduler"
        description="Coordinate candidate evaluations, detect scheduling conflicts, and generate labelled demo links."
        actions={
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              onClick={() => {
                setPublishedResult(null);
                setErrorMessage(null);
                setIsPublishSlotsModalOpen(true);
              }}
              className="btn btn-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
            >
              <Share2 size={16} />
              Publish Self-Booking Slots
            </button>
            <button
              onClick={() => {
                resetScheduleForm();
                setIsScheduleModalOpen(true);
              }}
              className="btn btn-primary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
            >
              <Plus size={16} />
              Schedule Interview
            </button>
          </div>
        }
      />

      {/* DEMO MODE WATERMARK BANNER */}
      <div
        className="demo-mode-notice"
        style={{
          backgroundColor: '#EFF6FF',
          border: '1px solid #BFDBFE',
          borderRadius: 'var(--radius-md)',
          padding: '0.75rem 1.25rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              backgroundColor: '#3B82F6',
              color: '#FFFFFF',
              fontSize: '0.6875rem',
              fontWeight: 800,
              padding: '0.2rem 0.5rem',
              borderRadius: '4px',
              letterSpacing: '0.05em',
            }}
          >
            DEMO MODE
          </div>
          <span style={{ fontSize: '0.8125rem', color: '#1E40AF', fontWeight: 500 }}>
            Simulated Environment — Meeting links and candidate emails are generated for demo validation without calling real Google Meet or SMTP APIs.
          </span>
        </div>
        <span style={{ fontSize: '0.75rem', color: '#3B82F6', fontWeight: 600 }}>
          DEMO MODE — EMAILS NOT SENT
        </span>
      </div>

      {/* Feedback Alerts */}
      {successMessage && (
        <div
          style={{
            backgroundColor: '#ECFDF5',
            border: '1px solid #A7F3D0',
            color: '#065F46',
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1rem',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <CheckCircle2 size={18} color="#059669" />
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div
          style={{
            backgroundColor: '#FEF2F2',
            border: '1px solid #FECACA',
            color: '#991B1B',
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1rem',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <AlertCircle size={18} color="#DC2626" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <div className="card" style={{ padding: '1rem 1.25rem' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
            Total Interviews
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.25rem' }}>
            {totalCount}
          </div>
        </div>
        <div className="card" style={{ padding: '1rem 1.25rem', borderLeft: '4px solid #3B82F6' }}>
          <div style={{ fontSize: '0.75rem', color: '#1D4ED8', textTransform: 'uppercase', fontWeight: 700 }}>
            Scheduled / Confirmed
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.25rem', color: '#1E40AF' }}>
            {scheduledCount}
          </div>
        </div>
        <div className="card" style={{ padding: '1rem 1.25rem', borderLeft: '4px solid #10B981' }}>
          <div style={{ fontSize: '0.75rem', color: '#047857', textTransform: 'uppercase', fontWeight: 700 }}>
            Completed
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.25rem', color: '#065F46' }}>
            {completedCount}
          </div>
        </div>
        <div className="card" style={{ padding: '1rem 1.25rem', borderLeft: '4px solid #EF4444' }}>
          <div style={{ fontSize: '0.75rem', color: '#B91C1C', textTransform: 'uppercase', fontWeight: 700 }}>
            Cancelled
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.25rem', color: '#991B1B' }}>
            {cancelledCount}
          </div>
        </div>
      </div>

      {/* Filters & Control Bar */}
      <div
        className="card"
        style={{
          marginBottom: '1.5rem',
          padding: '1rem',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.75rem',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center', flex: 1 }}>
          {/* Search Candidate / Reference */}
          <div style={{ position: 'relative', minWidth: '220px' }}>
            <Search
              size={16}
              style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
            />
            <input
              type="text"
              placeholder="Search candidate or reference..."
              value={candidateSearch}
              onChange={(e) => setCandidateSearch(e.target.value)}
              style={{ paddingLeft: '2.25rem', width: '100%', fontSize: '0.875rem' }}
            />
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ fontSize: '0.875rem', minWidth: '150px' }}
          >
            <option value="">All Statuses</option>
            <option value="SCHEDULED">Scheduled</option>
            <option value="CONFIRMED">Confirmed</option>
            <option value="COMPLETED">Completed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>

          {/* Interviewer Filter */}
          <select
            value={interviewerFilter}
            onChange={(e) => setInterviewerFilter(e.target.value)}
            style={{ fontSize: '0.875rem', minWidth: '170px' }}
          >
            <option value="">All Interviewers</option>
            {interviewers?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.role})
              </option>
            ))}
          </select>

          {/* Date Picker */}
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            style={{ fontSize: '0.875rem' }}
          />

          {(statusFilter || candidateSearch || interviewerFilter || dateFilter) && (
            <button
              onClick={() => {
                setStatusFilter('');
                setCandidateSearch('');
                setInterviewerFilter('');
                setDateFilter('');
              }}
              className="btn btn-secondary btn-sm"
            >
              Clear Filters
            </button>
          )}
        </div>

        {/* View Switcher */}
        <div style={{ display: 'flex', gap: '0.35rem', backgroundColor: 'var(--bg-muted, #F3F4F6)', padding: '0.2rem', borderRadius: 'var(--radius-md)' }}>
          <button
            onClick={() => setViewMode('list')}
            className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ padding: '0.25rem 0.6rem', fontSize: '0.8125rem' }}
          >
            <List size={14} style={{ marginRight: '0.3rem' }} />
            List
          </button>
          <button
            onClick={() => setViewMode('agenda')}
            className={`btn btn-sm ${viewMode === 'agenda' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ padding: '0.25rem 0.6rem', fontSize: '0.8125rem' }}
          >
            <CalendarDays size={14} style={{ marginRight: '0.3rem' }} />
            Agenda
          </button>
        </div>
      </div>

      {/* Main Interview Table / List */}
      {interviewsLoading ? (
        <div className="card" style={{ padding: '2rem' }}>
          <Skeleton height={30} style={{ marginBottom: '1rem' }} />
          <Skeleton height={40} style={{ marginBottom: '0.5rem' }} />
          <Skeleton height={40} style={{ marginBottom: '0.5rem' }} />
          <Skeleton height={40} />
        </div>
      ) : !interviews || interviews.length === 0 ? (
        <EmptyState
          icon={CalendarIcon}
          title="No Interviews Found"
          description="There are no scheduled interviews matching your filter criteria. Create an interview or publish self-booking slots."
          actionText="Schedule Interview"
          onAction={() => {
            resetScheduleForm();
            setIsScheduleModalOpen(true);
          }}
        />
      ) : viewMode === 'list' ? (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', backgroundColor: 'var(--bg-muted, #F9FAFB)', fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.875rem 1rem' }}>Reference & Format</th>
                  <th style={{ padding: '0.875rem 1rem' }}>Candidate & Job</th>
                  <th style={{ padding: '0.875rem 1rem' }}>Interviewer</th>
                  <th style={{ padding: '0.875rem 1rem' }}>Date & Time (UTC)</th>
                  <th style={{ padding: '0.875rem 1rem' }}>Meeting Link / Location</th>
                  <th style={{ padding: '0.875rem 1rem' }}>Status</th>
                  <th style={{ padding: '0.875rem 1rem', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {interviews.map((item) => {
                  const startDate = new Date(item.scheduled_start);
                  const isCompleted = item.status === 'COMPLETED';
                  const isCancelled = item.status === 'CANCELLED';

                  return (
                    <tr
                      key={item.id}
                      style={{
                        borderBottom: '1px solid var(--border-color)',
                        opacity: isCancelled ? 0.65 : 1,
                        transition: 'background-color 0.15s ease',
                      }}
                    >
                      {/* Reference & Format */}
                      <td style={{ padding: '0.875rem 1rem' }}>
                        <div style={{ fontWeight: 700, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                          {item.interview_reference || 'REF-DEMO'}
                        </div>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.2rem' }}>
                          {item.interview_type === 'ONLINE' ? (
                            <span style={{ fontSize: '0.6875rem', backgroundColor: '#EFF6FF', color: '#1D4ED8', padding: '0.1rem 0.4rem', borderRadius: '4px', fontWeight: 600 }}>
                              <Video size={10} style={{ display: 'inline', marginRight: '2px' }} />
                              Online
                            </span>
                          ) : (
                            <span style={{ fontSize: '0.6875rem', backgroundColor: '#F3F4F6', color: '#4B5563', padding: '0.1rem 0.4rem', borderRadius: '4px', fontWeight: 600 }}>
                              <MapPin size={10} style={{ display: 'inline', marginRight: '2px' }} />
                              In-Person
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Candidate & Job */}
                      <td style={{ padding: '0.875rem 1rem' }}>
                        <Link
                          to={`/candidates/${item.application_id}`}
                          style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--primary-600)', textDecoration: 'none' }}
                        >
                          {item.candidate_name || 'Candidate'}
                        </Link>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                          {item.job_title}
                        </div>
                      </td>

                      {/* Interviewer */}
                      <td style={{ padding: '0.875rem 1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <User size={14} color="var(--text-muted)" />
                          <span style={{ fontSize: '0.8125rem', fontWeight: 500 }}>
                            {item.interviewer_name || 'Unassigned'}
                          </span>
                        </div>
                      </td>

                      {/* Date & Time */}
                      <td style={{ padding: '0.875rem 1rem' }}>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>
                          {startDate.toLocaleDateString(undefined, {
                            weekday: 'short',
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          <Clock size={12} />
                          {startDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ({item.duration_minutes} min)
                        </div>
                      </td>

                      {/* Demo Link / Location */}
                      <td style={{ padding: '0.875rem 1rem' }}>
                        {item.interview_type === 'ONLINE' && item.meeting_url ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span
                              style={{
                                fontSize: '0.75rem',
                                color: '#2563EB',
                                fontFamily: 'monospace',
                                backgroundColor: '#EFF6FF',
                                padding: '0.15rem 0.4rem',
                                borderRadius: '4px',
                                maxWidth: '170px',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                              title={item.meeting_url}
                            >
                              {item.meeting_url}
                            </span>
                            <button
                              onClick={() => copyToClipboard(item.meeting_url!, 'Meeting link copied!')}
                              className="btn btn-ghost btn-sm"
                              style={{ padding: '0.2rem', color: 'var(--text-muted)' }}
                              title="Copy Demo Link"
                            >
                              <Copy size={13} />
                            </button>
                          </div>
                        ) : item.location ? (
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                            {item.location}
                          </span>
                        ) : (
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>None</span>
                        )}
                        {item.booking_token && (
                          <div style={{ marginTop: '0.3rem' }}>
                            <Link
                              to={`/book-interview/${item.booking_token}`}
                              target="_blank"
                              style={{ fontSize: '0.6875rem', color: '#059669', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}
                            >
                              <ExternalLink size={10} />
                              Candidate Booking Link
                            </Link>
                          </div>
                        )}
                      </td>

                      {/* Status */}
                      <td style={{ padding: '0.875rem 1rem' }}>
                        <StatusBadge status={item.status} />
                        {item.cancellation_reason && (
                          <div style={{ fontSize: '0.6875rem', color: '#DC2626', marginTop: '0.2rem', maxWidth: '160px' }}>
                            Reason: {item.cancellation_reason}
                          </div>
                        )}
                      </td>

                      {/* Actions */}
                      <td style={{ padding: '0.875rem 1rem', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '0.35rem', alignItems: 'center' }}>
                          {/* Simulated Notification history button */}
                          <button
                            onClick={() => {
                              setSelectedSchedule(item);
                              setIsNotificationsModalOpen(true);
                            }}
                            className="btn btn-secondary btn-sm"
                            title="Inspect Simulated Email Notifications (DEMO)"
                            style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                          >
                            <Mail size={13} />
                            Emails
                          </button>

                          {/* Live room launcher */}
                          {item.interview_type === 'ONLINE' && (
                            <Link
                              to={`/interview-room/${item.session_id}`}
                              className="btn btn-ghost btn-sm"
                              title="Candidate Virtual Interview Room"
                              style={{ padding: '0.25rem 0.4rem', color: '#059669' }}
                              target="_blank"
                            >
                              <Video size={14} />
                            </Link>
                          )}

                          {!isCompleted && !isCancelled && (
                            <>
                              {/* Complete button */}
                              <button
                                onClick={() => completeMutation.mutate(item.id)}
                                className="btn btn-secondary btn-sm"
                                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: '#059669' }}
                                title="Mark Completed (Advances to Scorecard)"
                              >
                                Complete
                              </button>

                              {/* Reschedule button */}
                              <button
                                onClick={() => {
                                  setSelectedSchedule(item);
                                  setRescheduleStart(new Date(item.scheduled_start).toISOString().slice(0, 16));
                                  setRescheduleDuration(item.duration_minutes);
                                  setRescheduleReason('');
                                  setErrorMessage(null);
                                  setIsRescheduleModalOpen(true);
                                }}
                                className="btn btn-ghost btn-sm"
                                style={{ padding: '0.25rem 0.4rem' }}
                                title="Reschedule"
                              >
                                <RefreshCw size={13} />
                              </button>

                              {/* Cancel button */}
                              <button
                                onClick={() => {
                                  setSelectedSchedule(item);
                                  setCancelReason('');
                                  setErrorMessage(null);
                                  setIsCancelModalOpen(true);
                                }}
                                className="btn btn-ghost btn-sm"
                                style={{ padding: '0.25rem 0.4rem', color: '#DC2626' }}
                                title="Cancel Interview"
                              >
                                <XCircle size={14} />
                              </button>
                            </>
                          )}

                          {isCompleted && (
                            <Link
                              to={`/candidates/${item.application_id}`}
                              className="btn btn-ghost btn-sm"
                              style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: '#6366F1' }}
                            >
                              Scorecard <ChevronRight size={12} />
                            </Link>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Agenda View */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
          {interviews.map((item) => {
            const startDate = new Date(item.scheduled_start);
            return (
              <div
                key={item.id}
                className="card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  borderTop: item.status === 'COMPLETED' ? '3px solid #10B981' : item.status === 'CANCELLED' ? '3px solid #EF4444' : '3px solid #3B82F6',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                      {item.interview_reference || 'REF-DEMO'}
                    </span>
                    <StatusBadge status={item.status} />
                  </div>

                  <h4 style={{ fontSize: '1.05rem', marginBottom: '0.25rem' }}>
                    <Link to={`/candidates/${item.application_id}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                      {item.candidate_name || 'Candidate'}
                    </Link>
                  </h4>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                    {item.job_title}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.8125rem', marginBottom: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <CalendarIcon size={14} color="var(--primary-600)" />
                      <span>{startDate.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Clock size={14} color="var(--primary-600)" />
                      <span>{startDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ({item.duration_minutes} min)</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <User size={14} color="var(--text-muted)" />
                      <span>Interviewer: {item.interviewer_name || 'Unassigned'}</span>
                    </div>
                    {item.interview_type === 'ONLINE' ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#2563EB' }}>
                        <Video size={14} />
                        <span style={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>DEMO MEETING ROOM</span>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                        <MapPin size={14} />
                        <span style={{ fontSize: '0.75rem' }}>{item.location || 'In-Person'}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
                  <button
                    onClick={() => {
                      setSelectedSchedule(item);
                      setIsNotificationsModalOpen(true);
                    }}
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem' }}
                  >
                    <Mail size={12} />
                    Emails
                  </button>
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    {item.interview_type === 'ONLINE' && (
                      <Link
                        to={`/interview-room/${item.session_id}`}
                        target="_blank"
                        className="btn btn-primary btn-sm"
                        style={{ fontSize: '0.75rem' }}
                      >
                        Launch Room
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* SCHEDULE INTERVIEW MODAL */}
      {isScheduleModalOpen && (
        <Modal
          isOpen={isScheduleModalOpen}
          title="Schedule New Interview"
          onClose={() => setIsScheduleModalOpen(false)}
        >
          <form onSubmit={handleCreateSchedule} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {errorMessage && (
              <div style={{ padding: '0.6rem 0.8rem', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#991B1B', borderRadius: '4px', fontSize: '0.8125rem' }}>
                {errorMessage}
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Candidate Application *
              </label>
              <select
                required
                value={formAppId}
                onChange={(e) => setFormAppId(e.target.value)}
                style={{ width: '100%', fontSize: '0.875rem' }}
              >
                <option value="">-- Select Candidate Application --</option>
                {applications?.map((app) => (
                  <option key={app.id} value={app.id}>
                    Application {app.id.slice(0, 8)}... ({app.shortlist_status || app.status})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Assigned Interviewer
              </label>
              <select
                value={formInterviewerId}
                onChange={(e) => setFormInterviewerId(e.target.value)}
                style={{ width: '100%', fontSize: '0.875rem' }}
              >
                <option value="">-- Unassigned (Automated System) --</option>
                {interviewers?.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.role})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Start Date & Time (UTC) *
                </label>
                <input
                  type="datetime-local"
                  required
                  value={formStartTime}
                  onChange={(e) => setFormStartTime(e.target.value)}
                  style={{ width: '100%', fontSize: '0.875rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Duration (Minutes)
                </label>
                <select
                  value={formDuration}
                  onChange={(e) => setFormDuration(Number(e.target.value))}
                  style={{ width: '100%', fontSize: '0.875rem' }}
                >
                  <option value={15}>15 Minutes</option>
                  <option value={30}>30 Minutes</option>
                  <option value={45}>45 Minutes (Standard)</option>
                  <option value={60}>60 Minutes</option>
                  <option value={90}>90 Minutes</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Interview Format
                </label>
                <select
                  value={formType}
                  onChange={(e) => setFormType(e.target.value)}
                  style={{ width: '100%', fontSize: '0.875rem' }}
                >
                  <option value="ONLINE">Online Virtual Room (Demo Link)</option>
                  <option value="IN_PERSON">In-Person Office Meeting</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  {formType === 'ONLINE' ? 'Virtual Room Note' : 'Office Location / Room'}
                </label>
                <input
                  type="text"
                  placeholder={formType === 'ONLINE' ? 'e.g. Browser pairing session' : 'e.g. Meeting Room 4B'}
                  value={formLocation}
                  onChange={(e) => setFormLocation(e.target.value)}
                  style={{ width: '100%', fontSize: '0.875rem' }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Instructions for Candidate
              </label>
              <textarea
                rows={3}
                placeholder="Optional notes regarding preparation, camera, microphone, or resume claims..."
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                style={{ width: '100%', fontSize: '0.875rem' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                onClick={() => setIsScheduleModalOpen(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={scheduleMutation.isPending}
                className="btn btn-primary"
              >
                {scheduleMutation.isPending ? 'Scheduling...' : 'Confirm Schedule'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* RESCHEDULE MODAL */}
      {isRescheduleModalOpen && selectedSchedule && (
        <Modal
          isOpen={isRescheduleModalOpen}
          title={`Reschedule Interview (${selectedSchedule.interview_reference})`}
          onClose={() => setIsRescheduleModalOpen(false)}
        >
          <form onSubmit={handleReschedule} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {errorMessage && (
              <div style={{ padding: '0.6rem 0.8rem', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#991B1B', borderRadius: '4px', fontSize: '0.8125rem' }}>
                {errorMessage}
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                New Start Date & Time (UTC) *
              </label>
              <input
                type="datetime-local"
                required
                value={rescheduleStart}
                onChange={(e) => setRescheduleStart(e.target.value)}
                style={{ width: '100%', fontSize: '0.875rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Duration (Minutes)
              </label>
              <select
                value={rescheduleDuration}
                onChange={(e) => setRescheduleDuration(Number(e.target.value))}
                style={{ width: '100%', fontSize: '0.875rem' }}
              >
                <option value={15}>15 Minutes</option>
                <option value={30}>30 Minutes</option>
                <option value={45}>45 Minutes</option>
                <option value={60}>60 Minutes</option>
                <option value={90}>90 Minutes</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Reason for Rescheduling
              </label>
              <input
                type="text"
                placeholder="e.g. Conflict on interviewer calendar, candidate request..."
                value={rescheduleReason}
                onChange={(e) => setRescheduleReason(e.target.value)}
                style={{ width: '100%', fontSize: '0.875rem' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                onClick={() => setIsRescheduleModalOpen(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={rescheduleMutation.isPending}
                className="btn btn-primary"
              >
                {rescheduleMutation.isPending ? 'Updating...' : 'Save & Dispatch Reschedule'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* CANCEL MODAL */}
      {isCancelModalOpen && selectedSchedule && (
        <Modal
          isOpen={isCancelModalOpen}
          title={`Cancel Interview (${selectedSchedule.interview_reference})`}
          onClose={() => setIsCancelModalOpen(false)}
        >
          <form onSubmit={handleCancel} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {errorMessage && (
              <div style={{ padding: '0.6rem 0.8rem', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#991B1B', borderRadius: '4px', fontSize: '0.8125rem' }}>
                {errorMessage}
              </div>
            )}

            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              Are you sure you want to cancel the interview for <strong>{selectedSchedule.candidate_name}</strong>? A simulated cancellation email will be recorded.
            </p>

            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                Cancellation Reason *
              </label>
              <textarea
                required
                rows={3}
                placeholder="Reason for cancellation (e.g., position filled, candidate requested withdrawal)..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                style={{ width: '100%', fontSize: '0.875rem' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                onClick={() => setIsCancelModalOpen(false)}
                className="btn btn-secondary"
              >
                Keep Interview
              </button>
              <button
                type="submit"
                disabled={cancelMutation.isPending}
                className="btn btn-primary"
                style={{ backgroundColor: '#DC2626', borderColor: '#DC2626' }}
              >
                {cancelMutation.isPending ? 'Cancelling...' : 'Confirm Cancellation'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* SIMULATED NOTIFICATION INSPECTION MODAL */}
      {isNotificationsModalOpen && selectedSchedule && (
        <Modal
          isOpen={isNotificationsModalOpen}
          title={`Simulated Email History • ${selectedSchedule.interview_reference}`}
          onClose={() => setIsNotificationsModalOpen(false)}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div
              style={{
                backgroundColor: '#EFF6FF',
                padding: '0.75rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.8125rem',
                color: '#1E40AF',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <Info size={16} />
              <span>
                Demonstration notification log. No external SMTP or Gmail API calls were made.
              </span>
            </div>

            {notifsLoading ? (
              <Skeleton height={100} />
            ) : !activeNotifications || activeNotifications.length === 0 ? (
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', textAlign: 'center', padding: '1.5rem' }}>
                No simulated notifications recorded yet for this interview.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '420px', overflowY: 'auto' }}>
                {activeNotifications.map((n) => (
                  <div
                    key={n.id}
                    style={{
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-md)',
                      padding: '0.875rem',
                      backgroundColor: 'var(--bg-app)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                      <span
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 700,
                          padding: '0.15rem 0.45rem',
                          borderRadius: '4px',
                          backgroundColor:
                            n.notification_type === 'INVITATION'
                              ? '#EFF6FF'
                              : n.notification_type === 'RESCHEDULE'
                              ? '#FFFBEB'
                              : n.notification_type === 'CANCELLATION'
                              ? '#FEF2F2'
                              : '#ECFDF5',
                          color:
                            n.notification_type === 'INVITATION'
                              ? '#1D4ED8'
                              : n.notification_type === 'RESCHEDULE'
                              ? '#B45309'
                              : n.notification_type === 'CANCELLATION'
                              ? '#B91C1C'
                              : '#047857',
                        }}
                      >
                        {n.notification_type}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {new Date(n.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.2rem' }}>
                      {n.subject}
                    </div>

                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                      To: <strong>{n.recipient}</strong> {n.recipient_name && `(${n.recipient_name})`}
                    </div>

                    <pre
                      style={{
                        backgroundColor: '#F9FAFB',
                        padding: '0.6rem',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'monospace',
                        color: 'var(--text-secondary)',
                        maxHeight: '180px',
                        overflowY: 'auto',
                        border: '1px solid #E5E7EB',
                      }}
                    >
                      {n.body}
                    </pre>
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
              <button
                onClick={() => setIsNotificationsModalOpen(false)}
                className="btn btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* PUBLISH SELF-BOOKING SLOTS MODAL */}
      {isPublishSlotsModalOpen && (
        <Modal
          isOpen={isPublishSlotsModalOpen}
          title="Publish Candidate Self-Booking Slots"
          onClose={() => setIsPublishSlotsModalOpen(false)}
        >
          {publishedResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', textAlign: 'center', padding: '1rem 0' }}>
              <CheckCircle2 size={42} color="#059669" style={{ margin: '0 auto' }} />
              <h3 style={{ fontSize: '1.15rem' }}>Self-Booking Link Generated!</h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                {publishedResult.total_slots} slots published for candidate self-selection. Send this link to the candidate or share it directly.
              </p>

              <div
                style={{
                  backgroundColor: '#F3F4F6',
                  padding: '0.75rem',
                  borderRadius: 'var(--radius-md)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '0.5rem',
                  fontFamily: 'monospace',
                  fontSize: '0.8125rem',
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {window.location.origin + publishedResult.booking_url}
                </span>
                <button
                  onClick={() =>
                    copyToClipboard(
                      window.location.origin + publishedResult.booking_url,
                      'Booking URL copied!'
                    )
                  }
                  className="btn btn-primary btn-sm"
                >
                  <Copy size={13} />
                  {copiedText || 'Copy Link'}
                </button>
              </div>

              <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem', marginTop: '0.5rem' }}>
                <Link
                  to={publishedResult.booking_url}
                  target="_blank"
                  className="btn btn-secondary"
                >
                  <ExternalLink size={14} />
                  Open Candidate View
                </Link>
                <button
                  onClick={() => setIsPublishSlotsModalOpen(false)}
                  className="btn btn-primary"
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handlePublishSlots} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {errorMessage && (
                <div style={{ padding: '0.6rem 0.8rem', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#991B1B', borderRadius: '4px', fontSize: '0.8125rem' }}>
                  {errorMessage}
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Candidate Application *
                </label>
                <select
                  required
                  value={publishAppId}
                  onChange={(e) => setPublishAppId(e.target.value)}
                  style={{ width: '100%', fontSize: '0.875rem' }}
                >
                  <option value="">-- Select Candidate Application --</option>
                  {applications?.map((a) => (
                    <option key={a.id} value={a.id}>
                      Application {a.id.slice(0, 8)}... ({a.status})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Hosting Interviewer *
                </label>
                <select
                  required
                  value={publishInterviewerId}
                  onChange={(e) => setPublishInterviewerId(e.target.value)}
                  style={{ width: '100%', fontSize: '0.875rem' }}
                >
                  <option value="">-- Select Interviewer --</option>
                  {interviewers?.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.role})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Available Time Slots (Future UTC dates)
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {publishSlotsList.map((slotVal, idx) => (
                    <input
                      key={idx}
                      type="datetime-local"
                      value={slotVal}
                      onChange={(e) => {
                        const copy = [...publishSlotsList];
                        copy[idx] = e.target.value;
                        setPublishSlotsList(copy);
                      }}
                      style={{ width: '100%', fontSize: '0.875rem' }}
                    />
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setPublishSlotsList([...publishSlotsList, ''])}
                  className="btn btn-ghost btn-sm"
                  style={{ marginTop: '0.4rem', fontSize: '0.75rem' }}
                >
                  + Add another slot
                </button>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsPublishSlotsModalOpen(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={publishSlotsMutation.isPending}
                  className="btn btn-primary"
                >
                  {publishSlotsMutation.isPending ? 'Generating...' : 'Publish Slots'}
                </button>
              </div>
            </form>
          )}
        </Modal>
      )}
    </div>
  );
};
