export type InspectorSelection =
  | { kind: 'project-brief-item'; id: string; label?: string }
  | { kind: 'requirement'; id: string }
  | { kind: 'architecture-node'; id: string }
  | { kind: 'functional-edge'; id: string }
  | { kind: 'electrical-node'; id: string }
  | { kind: 'electrical-connection'; id: string }
  | { kind: 'power-domain'; id: string }
  | { kind: 'physical-node'; id: string }
  | { kind: 'physical-relationship'; id: string }
  | { kind: 'architecture-view'; id: string }
  | { kind: 'component-role'; id: string }
  | { kind: 'open-question'; id: string }
  | { kind: 'validation-issue'; id: string }
  | { kind: 'artifact-revision'; artifactType: string; version: number }
  | { kind: 'next-action' }
  | { kind: 'none' };

export function selectionKey(selection: InspectorSelection): string {
  switch (selection.kind) {
    case 'none':
      return 'none';
    case 'next-action':
      return 'next-action';
    case 'artifact-revision':
      return `${selection.kind}:${selection.artifactType}:${selection.version}`;
    default:
      return `${selection.kind}:${selection.id}`;
  }
}
