import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Database, Upload, FileSpreadsheet, Layers, HelpCircle, CheckCircle2 } from 'lucide-react';
import { interviewDatasetsApi, jobsApi } from '../../core/api/endpoints';
import { PageHeader } from '../../shared/components/PageHeader';
import { Skeleton } from '../../shared/components/Skeleton';
import { EmptyState } from '../../shared/components/EmptyState';
import { Modal } from '../../shared/components/Modal';

export const DatasetLibraryView: React.FC = () => {
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);

  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);

  const { data: datasets, isLoading, refetch } = useQuery({
    queryKey: ['interviewDatasets'],
    queryFn: interviewDatasetsApi.list,
  });

  const { data: jobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: jobsApi.list,
  });

  const { data: activeDatasetDetail } = useQuery({
    queryKey: ['interviewDatasetDetail', selectedFileId],
    queryFn: () => interviewDatasetsApi.get(selectedFileId!),
    enabled: !!selectedFileId,
  });

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setUploadMessage(null);
    try {
      const res = await interviewDatasetsApi.upload(file, selectedJobId || undefined);
      setUploadMessage(`Successfully parsed ${res.total_questions} questions across ${res.datasets.length} datasets!`);
      setTimeout(() => {
        setIsUploadOpen(false);
        setFile(null);
        setUploadMessage(null);
        refetch();
      }, 1500);
    } catch (err: any) {
      alert(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Interview Question Datasets"
        description="Upload and maintain standardized domain question banks (.xlsx) for dynamic interview plan generation."
        actions={
          <button
            onClick={() => setIsUploadOpen(true)}
            className="btn btn-primary"
          >
            <Upload size={16} />
            Upload Dataset (.xlsx)
          </button>
        }
      />

      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <Skeleton height={60} />
          <Skeleton height={60} />
        </div>
      ) : !datasets || datasets.length === 0 ? (
        <EmptyState
          icon={FileSpreadsheet}
          title="No Question Datasets Uploaded"
          description="Upload an Excel workbook containing question sheets to enrich candidate interview plans with standardized questions."
          actionText="Upload Dataset"
          onAction={() => setIsUploadOpen(true)}
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
          {datasets.map((ds) => (
            <div key={ds.id} className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ width: 34, height: 34, borderRadius: 'var(--radius-md)', backgroundColor: '#ECFDF5', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <FileSpreadsheet size={18} />
                    </div>
                    <div>
                      <h4 style={{ fontSize: '0.95rem' }}>{ds.filename}</h4>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Uploaded {new Date(ds.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem', padding: '0.75rem', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Questions</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                      {ds.total_questions}
                    </div>
                  </div>
                  <div style={{ width: 1, backgroundColor: 'var(--border-base)' }} />
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Concept Datasets</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
                      {ds.dataset_count}
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setSelectedFileId(ds.id)}
                  className="btn btn-secondary btn-sm"
                >
                  <Layers size={13} />
                  Inspect Questions
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Dataset Detail Modal */}
      {selectedFileId && activeDatasetDetail && (
        <Modal
          isOpen={!!selectedFileId}
          onClose={() => setSelectedFileId(null)}
          title={`Question Bank: ${activeDatasetDetail.filename}`}
          subtitle={`${activeDatasetDetail.total_questions} questions across ${activeDatasetDetail.dataset_count} concepts`}
          maxWidth="750px"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {activeDatasetDetail.datasets.map((sub) => (
              <div key={sub.id} style={{ border: '1px solid var(--border-base)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <h4 style={{ fontSize: '0.95rem' }}>{sub.name} ({sub.concept})</h4>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--primary-700)', backgroundColor: 'var(--primary-50)', padding: '0.15rem 0.5rem', borderRadius: 'var(--radius-full)' }}>
                    {sub.question_count} questions
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '200px', overflowY: 'auto' }}>
                  {sub.questions.map((q) => (
                    <div key={q.id} style={{ fontSize: '0.8125rem', padding: '0.5rem', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{q.question_text}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                        Type: {q.question_type} • Difficulty: {q.difficulty}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Modal>
      )}

      {/* Upload Modal */}
      <Modal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        title="Upload Interview Question Dataset"
        subtitle="Upload an Excel (.xlsx) file with concept sheets and interview questions"
      >
        <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {uploadMessage && (
            <div style={{ padding: '0.75rem', backgroundColor: '#ECFDF5', color: '#047857', borderRadius: 'var(--radius-md)', fontSize: '0.8125rem', border: '1px solid #A7F3D0' }}>
              {uploadMessage}
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Target Job Position (Optional)
            </label>
            <select
              style={{ width: '100%' }}
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
            >
              <option value="">-- Global / Any Position --</option>
              {jobs?.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.35rem' }}>
              Select Excel Workbook (.xlsx) *
            </label>
            <input
              type="file"
              accept=".xlsx,.xls"
              required
              style={{ width: '100%' }}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setIsUploadOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={uploading || !file}
              className="btn btn-primary"
            >
              {uploading ? 'Parsing Excel...' : 'Upload & Parse'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
