import type { Node, NodeProps } from '@xyflow/react';
import type { ElectricalNodeData } from '../registry/node-renderers';
import { ElectricalNodeShell } from './ElectricalNodeShell';

export function PowerNode(props: NodeProps<Node<ElectricalNodeData>>) {
  return <ElectricalNodeShell {...props} accent="#DC6B20" icon="PWR" />;
}
