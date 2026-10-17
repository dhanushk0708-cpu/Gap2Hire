import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Mail, RefreshCw, Plus, Trash2, CheckCircle2, ShieldAlert } from 'lucide-react';
import { emailApi, jobsApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { Skeleton } from '../../shared/components/Skeleton';
import { Modal } from '../../shared/components/Modal';

export const EmailSettingsView: React.FC = () => {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [accountEmail, setAccountEmail] = useState('');
  const [provider, setProvider] = useState('FAKE');
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncDetails, setSyncDetails] = useState<any | null>(null);

  const { data: connections, isLoading, refetch } = useQuery({
    queryKey: ['emailConnections'],
    queryFn: emailApi.listConnections,
  });

  const { data: jobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: jobsApi.list,
  });

  const handleCreateConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accountEmail.trim()) return;
    try {
      await emailApi.createConnection({
        account_email: accountEmail.trim(),
        provider,
      });
      setIsAddOpen(false);
      setAccountEmail('');
      refetch();
    } catch (err: any) {
      alert(err.message || 'Failed to create connection');
    }
  };

  const handleDeleteConnection = async (id: string) => {
    if (!confirm('Are you sure you want to remove this email connection?')) return;
    try {
      await emailApi.deleteConnection(id);
      refetch();
    } catch (err: any) {
      alert(err.message || 'Failed to delete connection');
    }
  };

  const handleSyncEmails = async () => {
    setIsSyncing(true);
    setSyncDetails(null);
    try {
      const res = await emailApi.sync(10);
      setSyncDetails(res);
    } catch (err: any) {
      alert(err.message || 'Failed to synchronize emails');
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Email Intake & Candidate Ingestion"
        description="Configure automated mailbox connections for applicant resume intake and processing."
        actions={
          <>
            <button
              onClick={handleSyncEmails}
              disabled={isSyncing}
              className="btn btn-secondary"
            >
              <RefreshCw size={15} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Synchronizing...' : 'Sync Mailbox Now'}
            </button>
            <button
              onClick={() => setIsAddOpen(true)}
              className="btn btn-primary"
            >
              <Plus size={15} />
              Connect Mailbox
            </button>
          </>
        }
      />

      {/* Sync Results Banner */}
      {syncDetails && (
        <div
          className="card"
          style={{
            backgroundColor: '#EFF6FF',
            borderColor: '#BFDBFE',
            marginBottom: '1.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <CheckCircle2 size={18} color="#1D4ED8" />
            <h4 style={{ fontSize: '1rem', color: '#1D4ED8' }}>Email Intake Batch Complete</h4>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginTop: '0.75rem' }}>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Emails Fetched:</span>{' '}
              <strong>{syncDetails.emails_fetched}</strong>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Resumes Found:</span>{' '}
              <strong>{syncDetails.resumes_found}</strong>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Resumes Processed:</span>{' '}
              <strong style={{ color: '#059669' }}>{syncDetails.resumes_processed}</strong>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Duplicates Skipped:</span>{' '}
              <strong>{syncDetails.duplicates_skipped}</strong>
            </div>
          </div>
        </div>
      )}

      {/* Connected Accounts Card */}
      <div className="card">
        <h3 style={{ fontSize: '1.1rem', marginBottom: '0.35rem' }}>Connected Mailboxes</h3>
        <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
          Configured applicant intake channels.
        </p>

        {isLoading ? (
          <Skeleton height={80} />
        ) : !connections || connections.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
            <Mail size={32} color="var(--text-tertiary)" style={{ margin: '0 auto 0.5rem' }} />
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              No email connections configured. Click 'Connect Mailbox' above to add an intake email address.
            </p>
          </div>
        ) : (
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Account Email</th>
                  <th>Provider</th>
                  <th>Status</th>
                  <th>Configured Date</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {connections.map((conn) => (
                  <tr key={conn.id}>
                    <td><strong>{conn.account_email}</strong></td>
                    <td><span style={{ fontSize: '0.8125rem' }}>{conn.provider}</span></td>
                    <td>
                      <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#059669', backgroundColor: '#ECFDF5', padding: '0.15rem 0.5rem', borderRadius: '9999px', border: '1px solid #A7F3D0' }}>
                        {conn.status}
                      </span>
                    </td>
                    <td><span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{new Date(conn.created_at).toLocaleDateString()}</span></td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => handleDeleteConnection(conn.id)}
                        className="btn btn-ghost btn-sm"
                        style={{ color: '#EF4444' }}
                        title="Delete connection"
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

      {/* Add Connection Modal */}
      <Modal
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        title="Connect Mailbox for Candidate Intake"
        subtitle="Configure applicant mailbox address"
      >
        <form onSubmit={handleCreateConnection} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Account Email Address *
            </label>
            <input
              type="email"
              required
              placeholder="e.g. jobs@acmecorp.com"
              style={{ width: '100%' }}
              value={accountEmail}
              onChange={(e) => setAccountEmail(e.target.value)}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Provider Mode
            </label>
            <select
              style={{ width: '100%' }}
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              <option value="FAKE">Synthetic Test Provider (Sandbox)</option>
              <option value="GMAIL">Google Workspace / Gmail OAuth</option>
            </select>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsAddOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Connect Mailbox
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
