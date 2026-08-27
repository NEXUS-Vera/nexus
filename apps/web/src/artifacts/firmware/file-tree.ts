export type WorkspaceFileMeta = {
  path: string;
  sizeBytes?: number;
  mediaType?: string;
  origin?: string;
  writePolicy?: string;
};

export type FileTreeNode = {
  name: string;
  path: string;
  kind: 'file' | 'folder';
  children?: FileTreeNode[];
};

/** Build a hierarchical tree from workspace-relative file paths. */
export function buildFileTree(files: WorkspaceFileMeta[]): FileTreeNode[] {
  type Mutable = {
    name: string;
    path: string;
    kind: 'file' | 'folder';
    children?: Map<string, Mutable>;
  };

  const root = new Map<string, Mutable>();

  for (const file of [...files].sort((a, b) => a.path.localeCompare(b.path))) {
    const parts = file.path.split('/').filter(Boolean);
    if (parts.length === 0) continue;
    let cursor = root;
    let prefix = '';
    for (let i = 0; i < parts.length; i += 1) {
      const part = parts[i]!;
      prefix = prefix ? `${prefix}/${part}` : part;
      const isFile = i === parts.length - 1;
      let node = cursor.get(part);
      if (!node) {
        node = {
          name: part,
          path: prefix,
          kind: isFile ? 'file' : 'folder',
          children: isFile ? undefined : new Map(),
        };
        cursor.set(part, node);
      } else if (!isFile && node.kind === 'file') {
        // Path conflict: prefer folder container for nested entries.
        node.kind = 'folder';
        node.children = node.children ?? new Map();
      }
      if (!isFile) {
        node.children = node.children ?? new Map();
        cursor = node.children;
      }
    }
  }

  function freeze(map: Map<string, Mutable>): FileTreeNode[] {
    return [...map.values()]
      .sort((a, b) => {
        if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1;
        return a.name.localeCompare(b.name);
      })
      .map((node) => ({
        name: node.name,
        path: node.path,
        kind: node.kind,
        children: node.children ? freeze(node.children) : undefined,
      }));
  }

  return freeze(root);
}
