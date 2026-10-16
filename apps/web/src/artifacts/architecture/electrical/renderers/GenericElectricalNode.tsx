import type { Node, NodeProps } from '@xyflow/react';
import type { ElectricalNodeData } from '../registry/node-renderers';
import { ElectricalNodeShell } from './ElectricalNodeShell';

export function GenericElectricalNode(props: NodeProps<Node<ElectricalNodeData>>) {
  return <ElectricalNodeShell {...props} accent="#667085" icon="EL" />;
}
