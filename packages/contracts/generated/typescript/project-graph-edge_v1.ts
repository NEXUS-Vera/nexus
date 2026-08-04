/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
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
