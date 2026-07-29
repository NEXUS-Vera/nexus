import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { ProjectCurrentState, ProjectHistory } from '@nexus/contracts';
import {
  ApiClientError,
  getProject,
  getProjectHistory,
  submitProjectTurn,
} from '../api/client';
import { selectArtifactByType } from '../artifacts';
import { FunctionalArchitectureCard } from '../components/FunctionalArchitectureCard';
import { NextActionCard } from '../components/NextActionCard';
import { ProjectBriefCard } from '../components/ProjectBriefCard';
import { RequirementsCard } from '../components/RequirementsCard';

type Indicator = 'Updated' | 'Regenerated' | 'Unchanged' | 'Current';

function indicatorFor(
  artifactType: string,
  version: number,
  regenerated: string[],
  changed: string[],
): Indicator {
  if (regenerated.includes(artifactType)) return 'Regenerated';
  if (changed.includes(artifactType)) return 'Updated';
  if (version > 1) return 'Updated';
  return 'Unchanged';
}

export function ProjectPage() {
  const { projectId = '' } = useParams();
  const [state, setState] = useState<ProjectCurrentState | null>(null);
  const [history, setHistory] = useState<ProjectHistory | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [regenerated, setRegenerated] = useState<string[]>([]);
  const [changed, setChanged] = useState<string[]>([]);
  const [selectedRevision, setSelectedRevision] = useState<{
    artifactType: string;
    artifactVersion: number;
    artifactId: string;
  } | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [project, hist] = await Promise.all([
          getProject(projectId),
          getProjectHistory(projectId),
        ]);
        if (!cancelled) {
          setState(project);
          setHistory(hist);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiClientError ? err.message : 'Failed to load project');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const artifacts = useMemo(() => {
    if (!state) return null;
    return {
      brief: selectArtifactByType(state.artifacts, 'project-brief'),
      requirements: selectArtifactByType(state.artifacts, 'requirement-set'),
      architecture: selectArtifactByType(state.artifacts, 'functional-architecture'),
      nextAction: selectArtifactByType(state.artifacts, 'next-action'),
    };
  }, [state]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting || !message.trim() || !state) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitProjectTurn({
        projectId,
        message: message.trim(),
      });
      setState(result.currentState);
      setRegenerated(result.regeneratedArtifactTypes ?? []);
      setChanged(result.changedArtifactTypes ?? []);
      setMessage('');
      setHistory(await getProjectHistory(projectId));
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : 'Failed to submit turn');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className="page">
        <p>Loading project…</p>
      </main>
    );
  }

  if (!state || !artifacts?.brief || !artifacts.requirements || !artifacts.architecture || !artifacts.nextAction) {
    return (
      <main className="page">
        <p>{error ?? 'Project not found.'}</p>
        <Link to="/">Start a new project</Link>
      </main>
    );
  }

  const { brief, requirements, architecture, nextAction } = artifacts;

  const openQuestions = (state.openQuestions ?? []).filter((q) => q.status === 'open');

  return (
    <main className="page project-page">
      <header className="hero">
        <p className="eyebrow">
          <Link to="/">New project</Link> · {state.project.projectId}
        </p>
        <h1>{state.project.title}</h1>
        <p className="lede">
          State v{state.project.currentStateVersion} · {state.workflowRun.runStatus}
        </p>
      </header>

      <section className="vera-panel">
        <h2>Vera</h2>
        <p>{state.veraResponse.userFacingMessage}</p>
        <form onSubmit={onSubmit} className="prompt-form">
          <label htmlFor="turn">Continue the conversation</label>
          <textarea
            id="turn"
            rows={3}
            value={message}
            disabled={submitting}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="It should run for at least six months on battery power."
          />
          <button type="submit" disabled={submitting || !message.trim()}>
            {submitting ? 'Updating…' : 'Send to Vera'}
          </button>
        </form>
        {error ? (
          <p className="error-panel" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      {openQuestions.length ? (
        <section className="open-questions">
          <h2>Open questions</h2>
          <ul>
            {openQuestions.map((question) => (
              <li key={question.questionId}>
                <button
                  type="button"
                  className="chip"
                  onClick={() => setMessage(question.question)}
                >
                  Use in message
                </button>{' '}
                {question.question}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="artifact-grid">
        <div>
          <p className="revision-badge">
            Project Brief · v{brief.artifactVersion} ·{' '}
            {indicatorFor(
              'project-brief',
              brief.artifactVersion,
              regenerated,
              changed,
            )}
          </p>
          <ProjectBriefCard artifact={brief} />
        </div>
        <div>
          <p className="revision-badge">
            Requirements · v{requirements.artifactVersion} ·{' '}
            {indicatorFor(
              'requirement-set',
              requirements.artifactVersion,
              regenerated,
              changed,
            )}
          </p>
          <RequirementsCard artifact={requirements} />
        </div>
        <div>
          <p className="revision-badge">
            Architecture · v{architecture.artifactVersion} ·{' '}
            {indicatorFor(
              'functional-architecture',
              architecture.artifactVersion,
              regenerated,
              changed,
            )}
          </p>
          <FunctionalArchitectureCard artifact={architecture} />
        </div>
        <div>
          <p className="revision-badge">
            Next Action · v{nextAction.artifactVersion} ·{' '}
            {indicatorFor(
              'next-action',
              nextAction.artifactVersion,
              regenerated,
              changed,
            )}
          </p>
          <NextActionCard artifact={nextAction} />
        </div>
      </section>

      <section className="history-panel">
        <button type="button" className="chip" onClick={() => setShowHistory((v) => !v)}>
          {showHistory ? 'Hide history' : 'Show history'}
        </button>
        {showHistory && history ? (
          <div>
            <h2>History</h2>
            <h3>Turns</h3>
            <ul>
              {history.turns.map((turn) => (
                <li key={turn.turnId}>
                  <time>{turn.timestamp}</time> — {turn.rawUserMessage}
                </li>
              ))}
            </ul>
            <h3>Artifact revisions</h3>
            <ul>
              {history.artifactRevisions.map((rev) => (
                <li key={`${rev.artifactId}-${rev.artifactVersion}`}>
                  {rev.artifactType} v{rev.artifactVersion} ({rev.lifecycleStatus}){' '}
                  <button
                    type="button"
                    className="chip"
                    onClick={() =>
                      setSelectedRevision({
                        artifactType: rev.artifactType,
                        artifactVersion: rev.artifactVersion,
                        artifactId: rev.artifactId,
                      })
                    }
                  >
                    Inspect
                  </button>
                </li>
              ))}
            </ul>
            {selectedRevision ? (
              <aside className="error-panel">
                <h3>Historical revision (read-only)</h3>
                <p>
                  {selectedRevision.artifactType} v{selectedRevision.artifactVersion}
                </p>
                <p>ID: {selectedRevision.artifactId}</p>
                <button type="button" onClick={() => setSelectedRevision(null)}>
                  Close
                </button>
              </aside>
            ) : null}
          </div>
        ) : null}
      </section>
    </main>
  );
}
