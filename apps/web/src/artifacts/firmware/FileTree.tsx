import { ChevronDown, ChevronRight, FileCode2, Folder } from 'lucide-react';
import { useState } from 'react';
import { themeColors } from '../../lib/theme';
import type { FileTreeNode } from './file-tree';

type Props = {
  nodes: FileTreeNode[];
  selectedPath: string | null;
  dirtyPaths: Set<string>;
  isDark: boolean;
  onSelectFile: (path: string) => void;
};

function TreeNodeRow({
  node,
  depth,
  selectedPath,
  dirtyPaths,
  isDark,
  onSelectFile,
}: {
  node: FileTreeNode;
  depth: number;
  selectedPath: string | null;
  dirtyPaths: Set<string>;
  isDark: boolean;
  onSelectFile: (path: string) => void;
}) {
  const t = themeColors(isDark);
  const [open, setOpen] = useState(true);
  const selected = node.kind === 'file' && node.path === selectedPath;
  const dirty = node.kind === 'file' && dirtyPaths.has(node.path);

  if (node.kind === 'folder') {
    return (
      <div>
        <button
          type="button"
          data-testid={`firmware-tree-folder-${node.path}`}
          onClick={() => setOpen((v) => !v)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            width: '100%',
            border: 'none',
            background: 'transparent',
            color: t.textSec,
            fontSize: 12,
            padding: '3px 8px 3px',
            paddingLeft: 8 + depth * 12,
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <Folder size={12} />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{node.name}</span>
        </button>
        {open
          ? (node.children ?? []).map((child) => (
              <TreeNodeRow
                key={child.path}
                node={child}
                depth={depth + 1}
                selectedPath={selectedPath}
                dirtyPaths={dirtyPaths}
                isDark={isDark}
                onSelectFile={onSelectFile}
              />
            ))
          : null}
      </div>
    );
  }

  return (
    <button
      type="button"
      data-testid={`firmware-tree-file-${node.path}`}
      onClick={() => onSelectFile(node.path)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        width: '100%',
        border: 'none',
        background: selected ? t.cobaltSelected : 'transparent',
        color: selected ? t.text : t.textSec,
        fontSize: 12,
        padding: '3px 8px',
        paddingLeft: 8 + depth * 12 + 16,
        cursor: 'pointer',
        textAlign: 'left',
      }}
    >
      <FileCode2 size={12} />
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>{node.name}</span>
      {dirty ? (
        <span data-testid={`firmware-dirty-${node.path}`} style={{ color: t.cobalt, fontSize: 10 }}>
          ●
        </span>
      ) : null}
    </button>
  );
}

export function FirmwareFileTree({
  nodes,
  selectedPath,
  dirtyPaths,
  isDark,
  onSelectFile,
}: Props) {
  const t = themeColors(isDark);
  if (nodes.length === 0) {
    return (
      <div
        data-testid="firmware-file-tree-empty"
        style={{ padding: 12, fontSize: 12, color: t.textMuted, lineHeight: 1.45 }}
      >
        No files yet. Create a file to begin editing this Firmware workspace.
      </div>
    );
  }
  return (
    <div data-testid="firmware-file-tree" style={{ overflow: 'auto', flex: 1, minHeight: 0 }}>
      {nodes.map((node) => (
        <TreeNodeRow
          key={node.path}
          node={node}
          depth={0}
          selectedPath={selectedPath}
          dirtyPaths={dirtyPaths}
          isDark={isDark}
          onSelectFile={onSelectFile}
        />
      ))}
    </div>
  );
}
