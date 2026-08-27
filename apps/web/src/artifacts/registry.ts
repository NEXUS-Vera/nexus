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
  'firmware',
  'analysis',
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
  'firmware': {
    routeKey: 'firmware',
    artifactType: 'firmware',
    phase: 'BUILD',
    label: 'Firmware',
    shortLabel: 'Firmware',
    icon: Code2,
    availability: 'live',
    dependencyLabels: ['Architecture', 'Components'],
    supportedActions: ['select', 'inspect', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
  'analysis': {
    routeKey: 'analysis',
    artifactType: 'analysis',
    phase: 'BUILD',
    label: 'Analysis',
    shortLabel: 'Analysis',
    icon: BarChart2,
    availability: 'live',
    dependencyLabels: ['Architecture', 'Components'],
    supportedActions: ['select', 'inspect', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
  'test-plan': {
    routeKey: 'test-plan',
    artifactType: 'test-plan',
    phase: 'VERIFY',
    label: 'Test Plan',
    shortLabel: 'Test Plan',
    icon: ClipboardCheck,
    availability: 'live',
    dependencyLabels: ['Requirements', 'Architecture', 'Analysis'],
    supportedActions: ['select', 'inspect', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
  'risk-register': {
    routeKey: 'risk-register',
    artifactType: 'risk-register',
    phase: 'VERIFY',
    label: 'Risk Register',
    shortLabel: 'Risks',
    icon: AlertOctagon,
    availability: 'live',
    dependencyLabels: ['Requirements', 'Architecture', 'Test Plan'],
    supportedActions: ['select', 'inspect', 'view-history'],
    placeholderTitle: '',
    placeholderBody: '',
  },
};

export const WORKFLOW_GROUPS: { label: WorkflowPhase; artifacts: ArtifactRouteKey[] }[] = [
  { label: 'DEFINE', artifacts: ['project-brief', 'requirement-set'] },
  { label: 'DESIGN', artifacts: ['functional-architecture', 'component-plan'] },
  { label: 'BUILD', artifacts: ['firmware', 'analysis'] },
  { label: 'VERIFY', artifacts: ['test-plan', 'risk-register'] },
];

export function isArtifactRouteKey(value: string | null | undefined): value is ArtifactRouteKey {
  return Boolean(value && value in ARTIFACT_REGISTRY);
}

export function getArtifactDefinition(key: ArtifactRouteKey): ArtifactDefinition {
  return ARTIFACT_REGISTRY[key];
}
