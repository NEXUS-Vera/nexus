import { PlaceholderWorkspace } from '../components/layout/PlaceholderWorkspace';
import { WorkspaceHeader } from '../components/layout/WorkspaceHeader';
import { ARTIFACT_REGISTRY } from './registry';
import type { ArtifactRouteKey } from './types';

type Props = {
  routeKey: Extract<
    ArtifactRouteKey,
    | 'firmware-scaffold'
    | 'analysis-notebook'
    | 'test-plan'
    | 'risk-register'
  >;
  isDark: boolean;
  nextActionTitle?: string;
};

const SHELL_HINTS: Partial<Record<ArtifactRouteKey, string>> = {
  'firmware-scaffold':
    'Visual shell reserved for file tree, editor, and terminal panels. No project files are generated yet.',
  'analysis-notebook':
    'Visual shell reserved for notebook cells and outputs. No runtime is connected.',
  'test-plan': 'Visual shell reserved for verification tables and case detail.',
  'risk-register': 'Visual shell reserved for risk tables and mitigation detail.',
};

export function FutureArtifactPlaceholder({ routeKey, isDark, nextActionTitle }: Props) {
  const def = ARTIFACT_REGISTRY[routeKey];
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <WorkspaceHeader
        title={def.label}
        subtitle="Future artifact — not produced by the backend yet"
        lifecycleStatus="unavailable"
        isDark={isDark}
      />
      <PlaceholderWorkspace
        title={def.placeholderTitle}
        body={def.placeholderBody}
        prerequisites={def.dependencyLabels}
        nextActionTitle={nextActionTitle}
        isDark={isDark}
        shellHint={SHELL_HINTS[routeKey]}
      />
    </div>
  );
}
