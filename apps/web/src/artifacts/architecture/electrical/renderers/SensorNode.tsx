import type { Node, NodeProps } from '@xyflow/react';
import type { ElectricalNodeData } from '../registry/node-renderers';
import { ElectricalNodeShell } from './ElectricalNodeShell';

export function SensorNode(props: NodeProps<Node<ElectricalNodeData>>) {
  return <ElectricalNodeShell {...props} accent="#159A7A" icon="SNS" />;
}
