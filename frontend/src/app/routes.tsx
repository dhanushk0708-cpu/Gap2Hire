import React from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../core/auth/AuthContext';
import { AppShell } from '../shared/components/AppShell';

import { LoginScreen } from '../features/auth/LoginScreen';
import { RegisterScreen } from '../features/auth/RegisterScreen';
import { DashboardScreen } from '../features/dashboard/DashboardScreen';
import { JobListView } from '../features/jobs/JobListView';
import { JobDetailView } from '../features/jobs/JobDetailView';
import { ScreeningQueueView } from '../features/screening/ScreeningQueueView';
import { CandidateListView } from '../features/candidates/CandidateListView';
import { CandidateWorkspaceView } from '../features/candidates/CandidateWorkspaceView';
import { DatasetLibraryView } from '../features/interview-planning/DatasetLibraryView';
import { InterviewPlanView } from '../features/interview-planning/InterviewPlanView';
import { CandidateLiveRoomView } from '../features/interview-live/CandidateLiveRoomView';
import { HRLiveObserverView } from '../features/interview-live/HRLiveObserverView';
import { InterviewReportView } from '../features/interview-report/InterviewReportView';
import { AnalyticsView } from '../features/analytics/AnalyticsView';
import { HiringIntelligenceView } from '../features/analytics/HiringIntelligenceView';
import { EmailSettingsView } from '../features/settings/EmailSettingsView';
import { InterviewSchedulerView } from '../features/interviews/InterviewSchedulerView';
import { CandidateSelfBookingView } from '../features/interviews/CandidateSelfBookingView';
import { Skeleton } from '../shared/components/Skeleton';

// Protected Route wrapper checking authentication
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--bg-app)',
        }}
      >
        <div style={{ width: '200px', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <Skeleton height={20} />
          <Skeleton height={20} />
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public Authentication routes */}
      <Route path="/login" element={<LoginScreen />} />
      <Route path="/register" element={<RegisterScreen />} />

      {/* Candidate Live Interview Room (standalone focused experience) */}
      <Route path="/interview-room/:sessionId" element={<CandidateLiveRoomView />} />

      {/* Candidate Public Self-Booking Portal */}
      <Route path="/book-interview/:bookingToken" element={<CandidateSelfBookingView />} />

      {/* Protected Enterprise SaaS App Layout */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardScreen />} />
        <Route path="jobs" element={<JobListView />} />
        <Route path="jobs/:jobId" element={<JobDetailView />} />
        <Route path="candidates" element={<CandidateListView />} />
        <Route path="candidates/:applicationId" element={<CandidateWorkspaceView />} />
        <Route path="screening" element={<ScreeningQueueView />} />
        <Route path="interview-datasets" element={<DatasetLibraryView />} />
        <Route path="candidates/:applicationId/interview-plan" element={<InterviewPlanView />} />
        <Route path="interviews" element={<InterviewSchedulerView />} />
        <Route path="interviews/schedule" element={<Navigate to="/interviews" replace />} />
        <Route path="interviews/:sessionId/observer" element={<HRLiveObserverView />} />
        <Route path="interviews/:sessionId/report" element={<InterviewReportView />} />
        <Route path="analytics" element={<AnalyticsView />} />
        <Route path="hiring-intelligence" element={<HiringIntelligenceView />} />
        <Route path="hiring-chat" element={<Navigate to="/hiring-intelligence?tab=chat" replace />} />
        <Route path="settings/email" element={<EmailSettingsView />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};
