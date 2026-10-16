import type { ComponentType } from 'react';
import type { NodeProps } from '@xyflow/react';
import { GenericElectricalNode } from '../renderers/GenericElectricalNode';
import { McuNode } from '../renderers/McuNode';
import { PowerNode } from '../renderers/PowerNode';
import { SensorNode } from '../renderers/SensorNode';
import type { ElectricalVisualCategory, ElectricalVisualNode } from '../types';

export type ElectricalNodeData = {
  visual: ElectricalVisualNode;
  isDark: boolean;
  selected: boolean;
};

/** XYFlow nodeTypes registry uses untyped NodeProps; node components narrow data at runtime. */
export type ElectricalNodeComponent = ComponentType<NodeProps>;

const BY_CATEGORY: Record<ElectricalVisualCategory, ElectricalNodeComponent> = {
  compute: McuNode as ElectricalNodeComponent,
  sensor: SensorNode as ElectricalNodeComponent,
  power: PowerNode as ElectricalNodeComponent,
  communication: GenericElectricalNode as ElectricalNodeComponent,
  storage: GenericElectricalNode as ElectricalNodeComponent,
  actuation: GenericElectricalNode as ElectricalNodeComponent,
  protection: PowerNode as ElectricalNodeComponent,
  connector: GenericElectricalNode as ElectricalNodeComponent,
  junction: GenericElectricalNode as ElectricalNodeComponent,
  supporting: GenericElectricalNode as ElectricalNodeComponent,
  external: GenericElectricalNode as ElectricalNodeComponent,
  unknown: GenericElectricalNode as ElectricalNodeComponent,
};

export function resolveElectricalNodeRenderer(
  category: ElectricalVisualCategory,
): ElectricalNodeComponent {
  return BY_CATEGORY[category] ?? (GenericElectricalNode as ElectricalNodeComponent);
}

export function electricalNodeTypes(): Record<string, ElectricalNodeComponent> {
  return {
    'electrical-compute': McuNode as ElectricalNodeComponent,
    'electrical-sensor': SensorNode as ElectricalNodeComponent,
    'electrical-power': PowerNode as ElectricalNodeComponent,
    'electrical-generic': GenericElectricalNode as ElectricalNodeComponent,
  };
}

export function flowTypeForCategory(category: ElectricalVisualCategory): string {
  if (category === 'compute') return 'electrical-compute';
  if (category === 'sensor') return 'electrical-sensor';
  if (category === 'power' || category === 'protection') return 'electrical-power';
  return 'electrical-generic';
}
