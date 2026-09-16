import { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  VdaApiClient,
  VdaApiError,
  type ProfileCreated,
} from '../../../packages/contracts/generated/ts/api';
import './styles.css';

const WORKSPACE_ID = 'sales';
const PRINCIPAL_ID = 'minh-local';
const MAX_UPLOAD_BYTES = 256 * 1024 * 1024;

type Phase = 'idle' | 'uploading' | 'profiling' | 'completed' | 'failed';

type Activity = {
  id: string;
  title: string;
  detail: string;
  tone: 'neutral' | 'running' | 'success' | 'error';
};

function App() {
  const api = useMemo(() => new VdaApiClient(''), []);
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [profile, setProfile] = useState<ProfileCreated | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);

  const datasetId = file ? toDatasetId(file.name) : 'dataset';
  const profileSource = async () => {
    if (!file) {
      setError('Select a CSV or flat Parquet source.');
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError('The selected source exceeds the 256 MiB R1 input limit.');
      return;
    }
    if (!isSupportedFile(file)) {
      setError('Only CSV and flat Parquet sources are supported.');
      return;
    }

    setError(null);
    setProfile(null);
    setPhase('uploading');
    setActivities([
      {
        id: 'uploading',
        title: 'Artifact admission',
        detail: `${file.name} is being checked and pinned as an immutable source.`,
        tone: 'running',
      },
    ]);

    try {
      await api.createDataset(WORKSPACE_ID, PRINCIPAL_ID, { dataset_id: datasetId });
      const artifact = await api.uploadDataset(
        WORKSPACE_ID,
        datasetId,
        crypto.randomUUID(),
        PRINCIPAL_ID,
        file.name,
        file,
      );
      setPhase('profiling');
      setActivities([
        {
          id: 'artifact-ready',
          title: 'Artifact ready',
          detail: `${artifact.row_count.toLocaleString()} rows, ${artifact.headers.length} columns, SHA-256 ${shortHash(artifact.source_sha256)}.`,
          tone: 'success',
        },
        {
          id: 'profiling',
          title: 'Deterministic profile',
          detail: 'Computing aggregate metrics from the immutable artifact.',
          tone: 'running',
        },
      ]);
      const completed = await api.profileDataset(WORKSPACE_ID, datasetId, PRINCIPAL_ID, {
        artifact_id: artifact.artifact_id,
      });
      setProfile(completed);
      setPhase('completed');
      setActivities([
        {
          id: 'artifact-ready',
          title: 'Artifact ready',
          detail: `${artifact.row_count.toLocaleString()} rows, ${artifact.headers.length} columns, SHA-256 ${shortHash(artifact.source_sha256)}.`,
          tone: 'success',
        },
        {
          id: 'profile-completed',
          title: 'Profile completed',
          detail: `${completed.column_count} columns profiled with ${completed.method_version}.`,
          tone: 'success',
        },
      ]);
    } catch (reason) {
      const message = apiErrorMessage(reason);
      setError(message);
      setPhase('failed');
      setActivities((current) => [
        ...current.filter((activity) => activity.tone !== 'running'),
        { id: 'failed', title: 'Profile failed', detail: message, tone: 'error' },
      ]);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="workspace navigation">
        <div className="brand">VDaAgent</div>
        <div className="workspace-label">Sales workspace</div>
        <nav className="room-list" aria-label="rooms">
          <button className="room active" type="button">Sales profiling</button>
          <button className="room" type="button">Data quality</button>
          <button className="room" type="button">Reports</button>
        </nav>
        <div className="sidebar-note">Local demo</div>
      </aside>

      <main className="workspace-main">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">DataSteward</p>
            <h1>Sales profiling</h1>
            <p className="header-meta">Workspace-scoped artifact and profile run</p>
          </div>
          <span className={`run-status ${phase}`}>{phaseLabel(phase)}</span>
        </header>

        <section className="upload-surface" aria-labelledby="upload-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Source</p>
              <h2 id="upload-title">Upload and profile</h2>
            </div>
            <span className="bound">256 MiB max</span>
          </div>
          <div className="upload-controls">
            <label className="file-picker">
              <span>Choose file</span>
              <input
                type="file"
                accept=".csv,.parquet,text/csv,application/vnd.apache.parquet"
                onChange={(event) => {
                  const selected = event.target.files?.[0] ?? null;
                  setFile(selected);
                  setProfile(null);
                  setError(null);
                  setPhase('idle');
                  setActivities([]);
                }}
              />
            </label>
            <div className="file-summary" aria-live="polite">
              {file ? (
                <>
                  <strong>{file.name}</strong>
                  <span>
                    {formatBytes(file.size)} | {file.name.toLowerCase().endsWith('.parquet') ? 'Parquet' : 'CSV'}
                  </span>
                </>
              ) : (
                <span>No source selected</span>
              )}
            </div>
            <button
              className="primary-action"
              type="button"
              onClick={profileSource}
              disabled={!file || phase === 'uploading' || phase === 'profiling'}
            >
              {phase === 'uploading' ? 'Uploading' : phase === 'profiling' ? 'Profiling' : 'Profile source'}
            </button>
          </div>
          {error && <p className="error-message" role="alert">{error}</p>}
        </section>

        <section className="activity-surface" aria-labelledby="activity-title">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">Run activity</p>
              <h2 id="activity-title">Profile lifecycle</h2>
            </div>
          </div>
          {activities.length ? (
            <ol className="activity-list">
              {activities.map((activity) => (
                <li className={`activity ${activity.tone}`} key={activity.id}>
                  <span className="activity-marker" aria-hidden="true" />
                  <div>
                    <strong>{activity.title}</strong>
                    <p>{activity.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="empty-state">No profile run is active.</p>
          )}
        </section>
      </main>

      <aside className="inspector" aria-label="profile inspector">
        <div className="inspector-heading">
          <p className="eyebrow">Evidence</p>
          <h2>Profile inspector</h2>
        </div>
        {profile ? <ProfileInspector profile={profile} /> : <EmptyInspector file={file} />}
      </aside>
    </div>
  );
}

function EmptyInspector({ file }: { file: File | null }) {
  return (
    <div className="empty-inspector">
      <strong>{file ? file.name : 'No immutable artifact'}</strong>
      <p>
        {file
          ? 'Run the profile to create an evidence-bound summary.'
          : 'Artifact metadata and aggregate profile metrics appear here.'}
      </p>
    </div>
  );
}

function ProfileInspector({ profile }: { profile: ProfileCreated }) {
  const piiSignals = profile.columns.reduce(
    (total, column) => total + Object.values(column.pii_signal_counts).reduce((sum, count) => sum + count, 0),
    0,
  );
  return (
    <>
      <section className="profile-summary" aria-label="profile summary">
        <dl>
          <div><dt>Rows</dt><dd>{profile.row_count.toLocaleString()}</dd></div>
          <div><dt>Columns</dt><dd>{profile.column_count}</dd></div>
          <div><dt>PII signals</dt><dd>{piiSignals}</dd></div>
        </dl>
        <p className="artifact-hash">SHA-256 {shortHash(profile.source_sha256)}</p>
      </section>
      <section className="evidence-note">
        <strong>Profile evidence</strong>
        <span>{profile.evidence.method_version}</span>
        <p>{profile.evidence.limitations[0]}</p>
      </section>
      <section className="column-section" aria-labelledby="column-title">
        <div className="column-heading">
          <h3 id="column-title">Columns</h3>
          <span>{profile.columns.length}</span>
        </div>
        <div className="column-list">
          {profile.columns.map((column) => {
            const pii = Object.values(column.pii_signal_counts).reduce(
              (sum, count) => sum + count,
              0,
            );
            return (
              <article className="column-row" key={column.name}>
                <div className="column-name">
                  <strong>{column.name}</strong>
                  <span>{column.physical_type}</span>
                </div>
                <dl>
                  <div><dt>Null</dt><dd>{column.null_count}</dd></div>
                  <div><dt>Distinct</dt><dd>{column.distinct_non_null_count}</dd></div>
                  <div><dt>PII</dt><dd>{pii}</dd></div>
                </dl>
              </article>
            );
          })}
        </div>
      </section>
    </>
  );
}

function toDatasetId(filename: string) {
  const withoutExtension = filename.replace(/\.(csv|parquet)$/i, '');
  const normalized = withoutExtension
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return (normalized || 'dataset').slice(0, 128);
}

function isSupportedFile(file: File) {
  return /\.(csv|parquet)$/i.test(file.name);
}

function phaseLabel(phase: Phase) {
  return {
    idle: 'Ready',
    uploading: 'Uploading',
    profiling: 'Profiling',
    completed: 'Completed',
    failed: 'Failed',
  }[phase];
}

function shortHash(value: string) {
  return `${value.slice(0, 12)}...${value.slice(-8)}`;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function apiErrorMessage(reason: unknown) {
  if (reason instanceof VdaApiError) return reason.message;
  return 'The local profile service is unavailable.';
}

createRoot(document.getElementById('root')!).render(<App />);
