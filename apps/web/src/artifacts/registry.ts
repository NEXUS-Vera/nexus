import type { LucideIcon } from 'lucide-react';
import {
  AlertOctagon,
  BarChart2,
  ClipboardCheck,
  Code2,
  Cpu,
  FileText,
  List,
  Network,
} from 'lucide-react';
import type { ArtifactRouteKey, ArtifactAvailability, LiveArtifactType, WorkflowPhase } from './types';

export type ArtifactUiAction =
  | 'select'
  | 'inspect'
  | 'request-change-via-vera'
  | 'view-history';

export type ArtifactDefinition = {
  routeKey: ArtifactRouteKey;
  /** Canonical backend artifactType when live/proof; null for future placeholders. */
  artifactType: LiveArtifactType | null;
  phase: WorkflowPhase;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  availability: ArtifactAvailability;
  dependencyLabels: string[];
  supportedActions: ArtifactUiAction[];
  placeholderTitle: string;
  placeholderBody: string;
};

export const ARTIFACT_ORDER: ArtifactRouteKey[] = [
  'project-brief',
  'requirement-set',
  'functional-architecture',
  'component-plan',
  'firmware-scaffold',
  'analysis-notebook',
  'test-plan',
  'risk-register',
];

export const ARTIFACT_REGISTRY: Record<ArtifactRouteKey, ArtifactDefinition> = {
  'project-brief': {
    routeKey: 'project-brief',
    artifactType: 'project-brief',
    phase: 'DEFINE',
    label: 'Project Brief',
    shortLabel: 'Brief',
    icon: FileText,
    availability: 'live',
    dependencyLabels: [],
    supportedActions: ['select', 'inspect', 'request-change-via-vera', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
  'requirement-set': {
    routeKey: 'requirement-set',
    artifactType: 'requirement-set',
    phase: 'DEFINE',
    label: 'Requirements',
    shortLabel: 'Requirements',
    icon: List,
    availability: 'live',
    dependencyLabels: ['Project Brief'],
    supportedActions: ['select', 'inspect', 'request-change-via-vera', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
  'functional-architecture': {
    routeKey: 'functional-architecture',
    artifactType: 'functional-architecture',
    phase: 'DESIGN',
    label: 'Architecture',
    shortLabel: 'Architecture',
    icon: Network,
    availability: 'live',
    dependencyLabels: ['Requirements'],
    supportedActions: ['select', 'inspect', 'request-change-via-vera', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
  /** Selectable via Architecture tabs / URL; not listed separately in the workflow rail. */
  'electrical-architecture': {
    routeKey: 'electrical-architecture',
    artifactType: 'electrical-architecture',
    phase: 'DESIGN',
    label: 'Electrical Architecture',
    shortLabel: 'Electrical',
    icon: Network,
    availability: 'live',
    dependencyLabels: ['Architecture', 'Components'],
    supportedActions: ['select', 'inspect', 'request-change-via-vera', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
  /** Selectable via Architecture tabs / URL; not listed separately in the workflow rail. */
  'physical-architecture': {
    routeKey: 'physical-architecture',
    artifactType: 'physical-architecture',
    phase: 'DESIGN',
    label: 'Physical Architecture',
    shortLabel: 'Physical',
    icon: Network,
    availability: 'live',
    dependencyLabels: ['Electrical Architecture'],
    supportedActions: ['select', 'inspect', 'request-change-via-vera', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
  'component-plan': {
    routeKey: 'component-plan',
    artifactType: 'component-plan',
    phase: 'DESIGN',
    label: 'Components',
    shortLabel: 'Components',
    icon: Cpu,
    availability: 'live',
    dependencyLabels: ['Architecture', 'Requirements'],
    supportedActions: ['select', 'inspect', 'request-change-via-vera', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
  'firmware-scaffold': {
    routeKey: 'firmware-scaffold',
    artifactType: 'firmware',
    phase: 'BUILD',
    label: 'Firmware',
    shortLabel: 'Firmware',
    icon: Code2,
    availability: 'live',
    dependencyLabels: ['Architecture', 'Components'],
    supportedActions: ['select', 'inspect', 'view-history'],
    placeholderTitle: 'Firmware scaffold unavailable',
    placeholderBody:
      'No firmware files have been generated. A file tree, editor, and runtime panel will replace this shell when scaffold generation exists.',
  },
  'analysis-notebook': {
    routeKey: 'analysis-notebook',
    artifactType: null,
    phase: 'BUILD',
    label: 'Analysis',
    shortLabel: 'Analysis',
    icon: BarChart2,
    availability: 'placeholder',
    dependencyLabels: ['Requirements', 'Firmware'],
    supportedActions: ['select'],
    placeholderTitle: 'Analysis notebook unavailable',
    placeholderBody:
      'No notebook runtime is connected. Future cells and outputs will appear here when analysis artifacts exist.',
  },
  'test-plan': {
    routeKey: 'test-plan',
    artifactType: null,
    phase: 'VERIFY',
    label: 'Test Plan',
    shortLabel: 'Test Plan',
    icon: ClipboardCheck,
    availability: 'placeholder',
    dependencyLabels: ['Requirements', 'Architecture'],
    supportedActions: ['select'],
    placeholderTitle: 'Test Plan is not generated yet',
    placeholderBody:
      'Verification cases and results will appear here once a canonical test-plan artifact exists.',
  },
  'risk-register': {
    routeKey: 'risk-register',
    artifactType: null,
    phase: 'VERIFY',
    label: 'Risk Register',
    shortLabel: 'Risks',
    icon: AlertOctagon,
    availability: 'placeholder',
    dependencyLabels: ['Requirements', 'Architecture'],
    supportedActions: ['select'],
    placeholderTitle: 'Risk Register is not generated yet',
    placeholderBody:
      'Project risks and mitigations will appear here once a canonical risk-register artifact exists.',
  },
};

export const WORKFLOW_GROUPS: { label: WorkflowPhase; artifacts: ArtifactRouteKey[] }[] = [
  { label: 'DEFINE', artifacts: ['project-brief', 'requirement-set'] },
  { label: 'DESIGN', artifacts: ['functional-architecture', 'component-plan'] },
  { label: 'BUILD', artifacts: ['firmware-scaffold', 'analysis-notebook'] },
  { label: 'VERIFY', artifacts: ['test-plan', 'risk-register'] },
];

export function isArtifactRouteKey(value: string | null | undefined): value is ArtifactRouteKey {
  return Boolean(value && value in ARTIFACT_REGISTRY);
}

export function getArtifactDefinition(key: ArtifactRouteKey): ArtifactDefinition {
  return ARTIFACT_REGISTRY[key];
}
