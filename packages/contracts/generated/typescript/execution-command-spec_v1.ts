/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ExecutionCommandSpec {
  /**
   * @maxItems 64
   */
  arguments: string[];
  /**
   * @maxItems 32
   */
  declaredOutputs: {
    kind: 'result' | 'artifact' | 'log';
    path: string;
  }[];
  /**
   * Explicit non-secret environment values. Backend secrets must never appear here.
   *
   * @maxItems 64
   */
  environment: {
    name: string;
    value: string;
  }[];
  /**
   * Executable name or workspace-relative path. Must not be a host absolute path.
   */
  executable: string;
  schemaVersion: '1.0.0';
  /**
   * Workspace-relative working directory scoped to the materialized snapshot. Empty string means snapshot root.
   */
  workingDirectory: string;
}
