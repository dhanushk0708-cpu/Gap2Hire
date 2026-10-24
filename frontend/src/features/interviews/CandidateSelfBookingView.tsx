import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Calendar,
  Clock,
  Video,
  MapPin,
  CheckCircle2,
  AlertCircle,
  XCircle,
  RefreshCw,
  Sparkles,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  Building,
} from 'lucide-react';
import { candidateBookingApi } from '../../core/api/endpoints';
import { Skeleton } from '../../shared/components/Skeleton';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { Modal } from '../../shared/components/Modal';
import type { BookingSlotItem } from '../../core/types';

export const CandidateSelfBookingView: React.FC = () => {
  const { bookingToken } = useParams<{ bookingToken: string }>();
  const queryClient = useQueryClient();

  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Reschedule & Cancel modals
  const [isRescheduleOpen, setIsRescheduleOpen] = useState(false);
  const [isCancelOpen, setIsCancelOpen] = useState(false);
  const [rescheduleSlotId, setRescheduleSlotId] = useState<string | null>(null);
  const [cancelReason, setCancelReason] = useState('');

  // Load candidate booking view
  const {
    data: bookingView,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['candidateBooking', bookingToken],
    queryFn: () => candidateBookingApi.getView(bookingToken!),
    enabled: !!bookingToken,
    retry: 1,
  });

  // Mutations
  const bookMutation = useMutation({
    mutationFn: (slotId: string) =>
      candidateBookingApi.book(bookingToken!, slotId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['candidateBooking', bookingToken] });
      setSuccessBanner(
        `Your interview is confirmed! Reference: ${data.interview_reference || 'REF'}. A simulated confirmation email has been logged.`
      );
      setSelectedSlotId(null);
    },
    onError: (err: any) => {
      setErrorMessage(
        err.message || 'The selected slot is no longer available. Please choose another time.'
      );
    },
  });

  const rescheduleMutation = useMutation({
    mutationFn: (slotId: string) =>
      candidateBookingApi.reschedule(bookingToken!, slotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidateBooking', bookingToken] });
      setIsRescheduleOpen(false);
      setSuccessBanner('Your interview was rescheduled successfully!');
    },
    onError: (err: any) => {
      setErrorMessage(err.message || 'Failed to reschedule.');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (reason: string) =>
      candidateBookingApi.cancel(bookingToken!, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidateBooking', bookingToken] });
      setIsCancelOpen(false);
      setSuccessBanner('Your interview appointment has been cancelled.');
    },
    onError: (err: any) => {
      setErrorMessage(err.message || 'Failed to cancel appointment.');
    },
  });

  if (isLoading) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#F8FAFC', padding: '3rem 1rem' }}>
        <div style={{ maxWidth: '640px', margin: '0 auto' }}>
          <Skeleton height={60} style={{ marginBottom: '1.5rem' }} />
          <Skeleton height={200} style={{ marginBottom: '1rem' }} />
          <Skeleton height={150} />
        </div>
      </div>
    );
  }

  if (error || !bookingView) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#F8FAFC', padding: '4rem 1rem' }}>
        <div
          style={{
            maxWidth: '520px',
            margin: '0 auto',
            backgroundColor: '#FFFFFF',
            borderRadius: '12px',
            padding: '2.5rem',
            textAlign: 'center',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          }}
        >
          <AlertCircle size={48} color="#EF4444" style={{ margin: '0 auto 1rem' }} />
          <h2 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', color: '#111827' }}>
            Invalid or Expired Booking Link
          </h2>
          <p style={{ color: '#6B7280', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
            This booking link may have already been used, cancelled, or expired. Please contact your hiring coordinator for an updated link.
          </p>
          <Link to="/login" className="btn btn-secondary">
            Return to Gap2Hire
          </Link>
        </div>
      </div>
    );
  }

  const currentBooking = bookingView.current_booking;
  const isConfirmed = currentBooking && (currentBooking.status === 'SCHEDULED' || currentBooking.status === 'CONFIRMED');
  const availableSlots = bookingView.slots.filter((s) => !s.is_booked);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#F8FAFC', padding: '2.5rem 1rem 5rem' }}>
      <div style={{ maxWidth: '680px', margin: '0 auto' }}>
        {/* Top Header Card */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '12px',
            padding: '1.75rem',
            marginBottom: '1.25rem',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.08)',
            border: '1px solid #E2E8F0',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  backgroundColor: '#3B82F6',
                  color: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 800,
                  fontSize: '0.875rem',
                }}
              >
                G2H
              </div>
              <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#1E293B' }}>
                {bookingView.organization_name}
              </span>
            </div>
            <div
              style={{
                backgroundColor: '#EFF6FF',
                color: '#1D4ED8',
                fontSize: '0.6875rem',
                fontWeight: 700,
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                border: '1px solid #BFDBFE',
              }}
            >
              DEMO SELF-BOOKING
            </div>
          </div>

          <h1 style={{ fontSize: '1.45rem', fontWeight: 800, color: '#0F172A', marginBottom: '0.35rem' }}>
            Hi {bookingView.candidate_name}, schedule your interview
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#64748B', margin: 0 }}>
            Position: <strong>{bookingView.job_title}</strong> • Duration: {bookingView.duration_minutes} minutes
          </p>
        </div>

        {/* DEMO NOTICE WATERMARK */}
        <div
          style={{
            backgroundColor: '#EFF6FF',
            border: '1px solid #BFDBFE',
            borderRadius: '8px',
            padding: '0.75rem 1rem',
            marginBottom: '1.25rem',
            fontSize: '0.8125rem',
            color: '#1E40AF',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Sparkles size={16} color="#3B82F6" />
          <span>
            <strong>Demonstration Booking Portal:</strong> Selecting an interview reserves a slot in the demo system without sending external Google Calendar invites.
          </span>
        </div>

        {/* Feedback alerts */}
        {successBanner && (
          <div
            style={{
              backgroundColor: '#ECFDF5',
              border: '1px solid #A7F3D0',
              color: '#065F46',
              padding: '0.875rem 1.25rem',
              borderRadius: '8px',
              marginBottom: '1.25rem',
              fontSize: '0.875rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <CheckCircle2 size={18} color="#059669" />
            <span>{successBanner}</span>
          </div>
        )}

        {errorMessage && (
          <div
            style={{
              backgroundColor: '#FEF2F2',
              border: '1px solid #FECACA',
              color: '#991B1B',
              padding: '0.875rem 1.25rem',
              borderRadius: '8px',
              marginBottom: '1.25rem',
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

        {/* IF ALREADY CONFIRMED: Show Appointment Confirmation Card */}
        {isConfirmed ? (
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              padding: '2rem',
              boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.08)',
              border: '1px solid #E2E8F0',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <CheckCircle2 size={32} color="#059669" />
              <div>
                <h3 style={{ fontSize: '1.15rem', color: '#0F172A', margin: 0 }}>
                  Interview Confirmed
                </h3>
                <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.15rem' }}>
                  Reference: <strong>{currentBooking.interview_reference || 'REF-DEMO'}</strong>
                </div>
              </div>
            </div>

            <div
              style={{
                backgroundColor: '#F8FAFC',
                borderRadius: '8px',
                padding: '1.25rem',
                border: '1px solid #E2E8F0',
                marginBottom: '1.5rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.6rem',
                fontSize: '0.875rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <Calendar size={16} color="#3B82F6" />
                <span style={{ fontWeight: 600 }}>
                  {new Date(currentBooking.scheduled_start).toLocaleDateString(undefined, {
                    weekday: 'long',
                    month: 'long',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <Clock size={16} color="#3B82F6" />
                <span>
                  {new Date(currentBooking.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ({currentBooking.duration_minutes} minutes)
                </span>
              </div>

              {currentBooking.interview_type === 'ONLINE' ? (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', marginTop: '0.25rem' }}>
                  <Video size={16} color="#059669" style={{ marginTop: '0.15rem' }} />
                  <div>
                    <span style={{ fontWeight: 600, color: '#047857' }}>Demo Meeting Room:</span>
                    <div style={{ fontFamily: 'monospace', fontSize: '0.8125rem', color: '#2563EB', marginTop: '0.1rem' }}>
                      {currentBooking.meeting_url || 'https://demo.gap2hire.local/meet/INT-DEMO'}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.15rem' }}>
                      Clearly labelled demonstration video room.
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <MapPin size={16} color="#64748B" />
                  <span>Location: {currentBooking.location || 'Headquarters'}</span>
                </div>
              )}
            </div>

            {/* Candidate Actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button
                  onClick={() => {
                    setErrorMessage(null);
                    setIsRescheduleOpen(true);
                  }}
                  className="btn btn-secondary btn-sm"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
                >
                  <RefreshCw size={13} />
                  Reschedule Time Slot
                </button>
                <button
                  onClick={() => {
                    setErrorMessage(null);
                    setIsCancelOpen(true);
                  }}
                  className="btn btn-ghost btn-sm"
                  style={{ color: '#DC2626', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
                >
                  <XCircle size={14} />
                  Cancel Interview
                </button>
              </div>

              {currentBooking.interview_type === 'ONLINE' && (
                <Link
                  to={`/interview-room/${currentBooking.session_id}`}
                  className="btn btn-primary btn-sm"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
                  target="_blank"
                >
                  <Video size={14} />
                  Enter Live Room
                </Link>
              )}
            </div>
          </div>
        ) : (
          /* IF NOT BOOKED: Show Available Slots to Select */
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              padding: '1.75rem',
              boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.08)',
              border: '1px solid #E2E8F0',
            }}
          >
            <h3 style={{ fontSize: '1.15rem', color: '#0F172A', marginBottom: '0.35rem' }}>
              Choose an available time slot
            </h3>
            <p style={{ fontSize: '0.8125rem', color: '#64748B', marginBottom: '1.25rem' }}>
              Select a slot that fits your schedule. Your choice will instantly be reserved and confirmed.
            </p>

            {availableSlots.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2.5rem 1rem' }}>
                <Clock size={36} color="#94A3B8" style={{ margin: '0 auto 0.75rem' }} />
                <h4 style={{ fontSize: '1rem', color: '#334155', marginBottom: '0.25rem' }}>
                  No Open Slots Currently Available
                </h4>
                <p style={{ fontSize: '0.8125rem', color: '#64748B' }}>
                  All published slots have been reserved. Please contact the recruiting team to publish additional times.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '1.5rem' }}>
                {availableSlots.map((slot) => {
                  const sTime = new Date(slot.start_time);
                  const isSelected = selectedSlotId === slot.id;

                  return (
                    <div
                      key={slot.id}
                      onClick={() => setSelectedSlotId(slot.id)}
                      style={{
                        padding: '1rem 1.25rem',
                        borderRadius: '8px',
                        border: isSelected ? '2px solid #3B82F6' : '1px solid #CBD5E1',
                        backgroundColor: isSelected ? '#EFF6FF' : '#FFFFFF',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div
                          style={{
                            width: '18px',
                            height: '18px',
                            borderRadius: '50%',
                            border: isSelected ? '5px solid #3B82F6' : '2px solid #94A3B8',
                            backgroundColor: '#FFFFFF',
                          }}
                        />
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#0F172A' }}>
                            {sTime.toLocaleDateString(undefined, {
                              weekday: 'short',
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '0.15rem' }}>
                            {sTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • {slot.duration_minutes} min • {slot.interview_type}
                          </div>
                        </div>
                      </div>

                      <span
                        style={{
                          fontSize: '0.75rem',
                          color: isSelected ? '#1D4ED8' : '#64748B',
                          fontWeight: 600,
                        }}
                      >
                        {isSelected ? 'Selected' : 'Available'}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            {availableSlots.length > 0 && (
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  disabled={!selectedSlotId || bookMutation.isPending}
                  onClick={() => selectedSlotId && bookMutation.mutate(selectedSlotId)}
                  className="btn btn-primary"
                  style={{ minWidth: '160px' }}
                >
                  {bookMutation.isPending ? 'Reserving...' : 'Confirm My Appointment'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* RESCHEDULE MODAL FOR CANDIDATE */}
        {isRescheduleOpen && (
          <Modal
            isOpen={isRescheduleOpen}
            title="Reschedule Your Interview"
            onClose={() => setIsRescheduleOpen(false)}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Please select a different available slot for your interview:
              </p>

              {availableSlots.length === 0 ? (
                <p style={{ fontSize: '0.8125rem', color: '#DC2626' }}>
                  No alternate slots are currently open. Please contact HR.
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '250px', overflowY: 'auto' }}>
                  {availableSlots.map((s) => (
                    <div
                      key={s.id}
                      onClick={() => setRescheduleSlotId(s.id)}
                      style={{
                        padding: '0.75rem 1rem',
                        borderRadius: '6px',
                        border: rescheduleSlotId === s.id ? '2px solid #3B82F6' : '1px solid #E2E8F0',
                        backgroundColor: rescheduleSlotId === s.id ? '#EFF6FF' : '#FFFFFF',
                        cursor: 'pointer',
                        fontSize: '0.8125rem',
                      }}
                    >
                      <strong>{new Date(s.start_time).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</strong> at{' '}
                      {new Date(s.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ({s.duration_minutes} min)
                    </div>
                  ))}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsRescheduleOpen(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!rescheduleSlotId || rescheduleMutation.isPending}
                  onClick={() => rescheduleSlotId && rescheduleMutation.mutate(rescheduleSlotId)}
                  className="btn btn-primary"
                >
                  {rescheduleMutation.isPending ? 'Rescheduling...' : 'Confirm New Time'}
                </button>
              </div>
            </div>
          </Modal>
        )}

        {/* CANCEL MODAL FOR CANDIDATE */}
        {isCancelOpen && (
          <Modal
            isOpen={isCancelOpen}
            title="Cancel Interview Appointment"
            onClose={() => setIsCancelOpen(false)}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Are you sure you wish to cancel your scheduled interview? This will free your reserved slot for other candidates.
              </p>

              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  Reason (Optional)
                </label>
                <textarea
                  rows={2}
                  placeholder="Optional note for the hiring team..."
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  style={{ width: '100%', fontSize: '0.875rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsCancelOpen(false)}
                  className="btn btn-secondary"
                >
                  Keep Appointment
                </button>
                <button
                  type="button"
                  disabled={cancelMutation.isPending}
                  onClick={() => cancelMutation.mutate(cancelReason)}
                  className="btn btn-primary"
                  style={{ backgroundColor: '#DC2626', borderColor: '#DC2626' }}
                >
                  {cancelMutation.isPending ? 'Cancelling...' : 'Confirm Cancellation'}
                </button>
              </div>
            </div>
          </Modal>
        )}
      </div>
    </div>
  );
};
