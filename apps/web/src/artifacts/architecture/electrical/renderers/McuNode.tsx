import type { Node, NodeProps } from '@xyflow/react';
import type { ElectricalNodeData } from '../registry/node-renderers';
import { ElectricalNodeShell } from './ElectricalNodeShell';

export function McuNode(props: NodeProps<Node<ElectricalNodeData>>) {
  return <ElectricalNodeShell {...props} accent="#3563E9" icon="MCU" />;
}
