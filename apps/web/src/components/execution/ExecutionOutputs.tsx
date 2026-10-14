import type { ProducedOutput } from '@nexus/contracts';

export function ExecutionOutputs({ outputs }: { outputs: ProducedOutput[] }) {
  if (outputs.length === 0) {
    return <p data-testid="execution-outputs-empty">No outputs</p>;
  }
  return (
    <ul data-testid="execution-outputs">
      {outputs.map((output) => (
        <li key={output.outputId}>
          {output.name} ({output.outputType})
        </li>
      ))}
    </ul>
  );
}
