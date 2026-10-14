export type ExecutionLogChunkView = {
  sequence: number;
  stream: 'stdout' | 'stderr' | 'system';
  content: string;
  truncated?: boolean;
};

export function ExecutionLogViewer({
  chunks,
  truncated,
}: {
  chunks: ExecutionLogChunkView[];
  truncated?: boolean;
}) {
  return (
    <div data-testid="execution-log-viewer">
      {truncated ? <p>Log truncated</p> : null}
      <pre>
        {chunks.map((chunk) => (
          <div key={chunk.sequence} data-stream={chunk.stream}>
            [{chunk.stream}#{chunk.sequence}] {chunk.content}
          </div>
        ))}
      </pre>
    </div>
  );
}
