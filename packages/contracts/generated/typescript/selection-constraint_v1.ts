/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface SelectionConstraint {
  componentRoleId: string;
  confirmationStatus: 'confirmed' | 'inferred' | 'proposed' | 'unknown';
  constraintId: string;
  constraintType:
    | 'measurement-range'
    | 'accuracy'
    | 'resolution'
    | 'sample-rate'
    | 'bandwidth'
    | 'latency'
    | 'supply-voltage'
    | 'logic-voltage'
    | 'active-current'
    | 'sleep-current'
    | 'peak-current'
    | 'interface'
    | 'bus-bandwidth'
    | 'operating-temperature'
    | 'humidity-rating'
    | 'size'
    | 'weight'
    | 'cost'
    | 'availability'
    | 'driver-support'
    | 'platform-support'
    | 'environment'
    | 'mechanical-mounting';
  importance: 'required' | 'preferred' | 'nice-to-have';
  operator: 'eq' | 'neq' | 'gte' | 'lte' | 'gt' | 'lt' | 'in' | 'contains' | 'unknown';
  rationale: string;
  sourceArchitectureNodeIds: string[];
  sourceRequirementIds: string[];
  targetValue:
    | number
    | string
    | boolean
    | {
        kind: 'unknown';
      };
  unit: string | null;
}
