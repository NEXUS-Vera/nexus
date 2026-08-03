import { FormEvent, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiClientError, initializeProject } from '../api/client';

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

type UiError = {
  kind: 'unsupported' | 'ambiguous' | 'server' | 'network' | 'validation';
  message: string;
  supportedFamilies?: Array<{ family: string; examplePrompt: string }>;
};

export function HomePage() {
  const navigate = useNavigate();
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<UiError | null>(null);

  const examples = useMemo(() => EXAMPLE_PROMPTS, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (loading || !message.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await initializeProject({ message: message.trim() });
      navigate(`/projects/${payload.project.projectId}`);
    } catch (err) {
      if (err instanceof ApiClientError) {
        const code = err.body?.error.code;
        if (code === 'UNSUPPORTED_EMBEDDED_PROJECT_FOR_FIXTURE_PHASE') {
          setError({
            kind: 'unsupported',
            message: err.message,
            supportedFamilies: err.body?.error.supportedFamilies,
          });
        } else if (code === 'AMBIGUOUS_EMBEDDED_PROJECT_FAMILY') {
          setError({ kind: 'ambiguous', message: err.message });
        } else if (err.status === 0) {
          setError({ kind: 'network', message: err.message });
        } else {
          setError({ kind: 'server', message: err.message });
        }
      } else {
        setError({
          kind: 'validation',
          message: err instanceof Error ? err.message : 'Unexpected client error',
        });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">Nexus · Embedded initialization</p>
        <h1>Start a new embedded project</h1>
        <p className="lede">
          Describe what you want to build. Vera will create a persisted project you can continue later.
        </p>
      </header>

      <form className="prompt-form" onSubmit={onSubmit}>
        <label htmlFor="prompt">Project idea</label>
        <textarea
          id="prompt"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={5}
          placeholder="I want to build..."
          disabled={loading}
        />
        <div className="example-row">
          {examples.map((example) => (
            <button
              key={example.label}
              type="button"
              className="chip"
              disabled={loading}
              onClick={() => setMessage(example.text)}
            >
              {example.label}
            </button>
          ))}
        </div>
        <button type="submit" disabled={loading || !message.trim()}>
          {loading ? 'Creating project…' : 'Create project'}
        </button>
      </form>

      {error ? (
        <section className="error-panel" role="alert">
          <h2>{error.kind === 'network' ? 'Network error' : 'Could not create project'}</h2>
          <p>{error.message}</p>
          {error.supportedFamilies?.length ? (
            <ul>
              {error.supportedFamilies.map((family) => (
                <li key={family.family}>
                  <strong>{family.family}</strong>: {family.examplePrompt}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
