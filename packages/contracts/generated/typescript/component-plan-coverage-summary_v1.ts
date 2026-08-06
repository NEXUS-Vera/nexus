/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ComponentPlanCoverageSummary {
  coveredArchitectureNodes: number;
  coveredRequirementIds: string[];
  rolesAwaitingApproval: number;
  rolesWithBlockedSelection: number;
  rolesWithoutArchitectureMapping: number;
  rolesWithoutCandidates: number;
  rolesWithoutRequirementMapping: number;
  totalArchitectureNodes: number;
  totalRelevantRequirements: number;
  uncoveredArchitectureNodeIds: string[];
  uncoveredRequirementIds: string[];
}
