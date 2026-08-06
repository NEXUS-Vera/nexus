/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ComponentCategory =
  | 'sensor'
  | 'compute'
  | 'power'
  | 'communication'
  | 'storage'
  | 'interface'
  | 'actuation'
  | 'protection'
  | 'mechanical'
  | 'supporting-electronics';

export interface ComponentRole {
  architectureNodeIds: string[];
  category: ComponentCategory;
  componentRoleId: string;
  description: string;
  displayId: string;
  name: string;
  openQuestionIds?: string[];
  priority: 'low' | 'medium' | 'high' | 'blocking';
  rationale: string;
  requiredCapabilities: string[];
  requirementIds: string[];
  source: 'user-explicit' | 'inferred' | 'agent-proposed' | 'fixture';
  status:
    | 'identified'
    | 'needs-clarification'
    | 'ready-for-candidates'
    | 'candidate-review'
    | 'selection-proposed'
    | 'selected'
    | 'blocked'
    | 'superseded';
}
