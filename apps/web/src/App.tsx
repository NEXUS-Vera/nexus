import { FormEvent, useMemo, useState } from 'react';
import type { ProjectInitializationResult } from '@nexus/contracts';
import { ApiClientError, initializeProject } from './api/client';
import { selectArtifactByType } from './artifacts';
import { FunctionalArchitectureCard } from './components/FunctionalArchitectureCard';
import { NextActionCard } from './components/NextActionCard';
import { ProjectBriefCard } from './components/ProjectBriefCard';
import { RequirementsCard } from './components/RequirementsCard';

const EXAMPLE_PROMPTS = [
  {
    label: 'Indoor environmental rover',
    text: 'I want to build a small indoor rover that drives around a room and maps temperature, humidity, and air quality.',
  },
  {
    label: 'Wearable tremor monitor',
    text: 'I want to build a wrist-worn device that measures hand tremors and records the motion data for later analysis.',
  },
  {
    label: 'Greenhouse sensing node',
    text: 'I want to build a greenhouse monitoring node that measures temperature, humidity, soil moisture, and light, and reports the readings remotely.',
  },
  {
    label: 'Vibration-monitoring device',
    text: 'I want to build a device that attaches to a machine and records vibration so I can detect changes in how the machine is operating.',
  },
  {
    label: 'Robot obstacle-detection module',
    text: 'I want to build an obstacle-detection module for a small indoor robot so it can detect objects in front of it and react before it hits them.',
  },
] as const;

const LOADING_STAGES = [
  'Understanding your project',
  'Preparing the initial project package',
  'Validating the artifacts',
] as const;

type UiError = {
  kind: 'unsupported' | 'ambiguous' | 'server' | 'network' | 'validation';
  message: string;
  supportedFamilies?: Array<{ family: string; examplePrompt: string }>;
};

export default function App() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ProjectInitializationResult | null>(null);
  const [error, setError] = useState<UiError | null>(null);
  const [stageIndex, setStageIndex] = useState(0);

  const artifacts = useMemo(() => {
    if (!result) return null;
    return {
      brief: selectArtifactByType(result.artifacts, 'project-brief'),
      requirements: selectArtifactByType(result.artifacts, 'requirement-set'),
      architecture: selectArtifactByType(result.artifacts, 'functional-architecture'),
      nextAction: selectArtifactByType(result.artifacts, 'next-action'),
    };
  }, [result]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (loading || !message.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setStageIndex(0);
    const timer = window.setInterval(() => {
      setStageIndex((current) => Math.min(current + 1, LOADING_STAGES.length - 1));
    }, 700);

    try {
      const payload = await initializeProject({ message: message.trim() });
      setResult(payload);
    } catch (err) {
      if (err instanceof ApiClientError) {
        const code = err.body?.error.code;
        if (code === 'UNSUPPORTED_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE') {
          setError({
            kind: 'unsupported',
            message: err.body?.error.message ?? err.message,
            supportedFamilies: err.body?.error.supportedFamilies,
          });
        } else if (code === 'AMBIGUOUS_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE') {
          setError({
            kind: 'ambiguous',
            message: err.body?.error.message ?? err.message,
          });
        } else if (err.status === 0) {
          setError({ kind: 'network', message: err.message });
        } else {
          setError({
            kind: 'server',
            message:
              'Project initialization failed. No valid package was created. You can retry.',
          });
        }
      } else {
        setError({
          kind: 'validation',
          message: err instanceof Error ? err.message : 'Unexpected client error',
        });
      }
    } finally {
      window.clearInterval(timer);
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <main className="conversation">
        <header className="vera-header">
          <p className="brand">Vera</p>
          <h1>Embedded project initialization</h1>
          <p className="lede">
            Tell Vera what embedded product you want to build.
          </p>
        </header>

        <form className="prompt-form" onSubmit={onSubmit} aria-describedby={error ? 'form-error' : undefined}>
          <label htmlFor="prompt">Product idea</label>
          <textarea
            id="prompt"
            name="prompt"
            rows={5}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Describe the embedded product you want to initialize…"
            disabled={loading}
          />
          <div className="example-row">
            <span className="muted">Examples:</span>
            {EXAMPLE_PROMPTS.map((example) => (
              <button
                key={example.label}
                type="button"
                className="example-chip"
                onClick={() => setMessage(example.text)}
                disabled={loading}
              >
                {example.label}
              </button>
            ))}
          </div>
          <button type="submit" disabled={loading || !message.trim()}>
            {loading ? 'Initializing…' : 'Initialize project'}
          </button>
        </form>

        <div aria-live="polite" className="status-region">
          {loading ? (
            <p className="loading-state">
              {LOADING_STAGES[stageIndex]}
            </p>
          ) : null}
          {error ? (
            <div id="form-error" className={`error-banner kind-${error.kind}`} role="alert">
              <p>{error.message}</p>
              {error.kind === 'unsupported' && error.supportedFamilies ? (
                <ul>
                  {error.supportedFamilies.map((family) => (
                    <li key={family.family}>
                      <button
                        type="button"
                        onClick={() => setMessage(family.examplePrompt)}
                      >
                        {family.family}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
              {error.kind === 'ambiguous' ? (
                <p>Narrow the prompt to one supported project family. Vera will not choose for you.</p>
              ) : null}
              {error.kind === 'server' || error.kind === 'network' ? (
                <button
                  type="button"
                  onClick={() => {
                    const form = document.querySelector('form.prompt-form');
                    form?.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                  }}
                >
                  Retry
                </button>
              ) : null}
            </div>
          ) : null}
          {result ? (
            <section className="vera-response" aria-labelledby="vera-response-heading">
              <h2 id="vera-response-heading">Vera</h2>
              <p>{result.veraResponse.userFacingMessage}</p>
            </section>
          ) : null}
        </div>
      </main>

      <aside className="artifacts-panel" aria-label="Initialization artifacts">
        {!artifacts ? (
          <p className="empty-artifacts">Artifact cards will appear after a successful initialization.</p>
        ) : (
          <>
            {artifacts.brief ? <ProjectBriefCard artifact={artifacts.brief} /> : null}
            {artifacts.requirements ? <RequirementsCard artifact={artifacts.requirements} /> : null}
            {artifacts.architecture ? (
              <FunctionalArchitectureCard artifact={artifacts.architecture} />
            ) : null}
            {artifacts.nextAction ? <NextActionCard artifact={artifacts.nextAction} /> : null}
          </>
        )}
      </aside>
    </div>
  );
}
