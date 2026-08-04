/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';

export interface GraphTraversalResult {
  direction: 'upstream' | 'downstream' | 'neighbors' | 'subgraph';
  edgeLimitReached: boolean;
  edges: ProjectGraphEdge[];
  maxDepth: number;
  nodeLimitReached: boolean;
  nodes: ProjectGraphNode[];
  projectId: string;
  rootNodeId: string;
  schemaVersion: '1.0.0';
  truncated: boolean;
}
export interface ProjectGraphEdge {
  createdByEventId: string;
  edgeId: string;
  edgeType:
    | 'depends-on'
    | 'derives-from'
    | 'constrains'
    | 'covers'
    | 'blocks'
    | 'invalidates'
    | 'supports'
    | 'contradicts'
    | 'supersedes'
    | 'produced-by'
    | 'belongs-to'
    | 'answers';
  projectId: string;
  reason?: string;
  schemaVersion: '1.0.0';
  sourceNodeId: string;
  targetNodeId: string;
  validFrom: string;
  validUntil?: string;
}
export interface ProjectGraphNode {
  artifactType?: ArtifactType;
  createdAt: string;
  createdByEventId?: string;
  label: string;
  nodeId: string;
  nodeType:
    | 'artifact'
    | 'artifact-revision'
    | 'requirement'
    | 'architecture-node'
    | 'question'
    | 'validation-issue'
    | 'decision'
    | 'evidence'
    | 'execution'
    | 'output'
    | 'workspace';
  projectId: string;
  refId?: string;
  schemaVersion: '1.0.0';
}
