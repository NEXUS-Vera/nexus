import { useEffect, useMemo, useRef, useState } from 'react';
import type { ProjectCurrentState } from '@nexus/contracts';
import { ARTIFACT_ORDER, ARTIFACT_REGISTRY } from '../../artifacts/registry';
import type { ArtifactRouteKey, GlobalView } from '../../artifacts/types';
import { selectArtifactByType } from '../../artifacts';
import { themeColors } from '../../lib/theme';

type Command = {
  id: string;
  label: string;
  group: string;
  run: () => void;
};

type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
  isDark: boolean;
  state: ProjectCurrentState;
  onSetGlobalView: (view: GlobalView) => void;
  onSelectArtifact: (key: ArtifactRouteKey) => void;
  onSelectRequirement: (id: string) => void;
  onOpenNextAction: () => void;
  onOpenHistory: () => void;
  onFocusVera: () => void;
};

export function CommandPalette({
  open,
  onClose,
  isDark,
  state,
  onSetGlobalView,
  onSelectArtifact,
  onSelectRequirement,
  onOpenNextAction,
  onOpenHistory,
  onFocusVera,
}: CommandPaletteProps) {
  const t = themeColors(isDark);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = useMemo(() => {
    const items: Command[] = [
      {
        id: 'overview',
        label: 'Open Overview',
        group: 'Views',
        run: () => onSetGlobalView('overview'),
      },
      {
        id: 'workspace',
        label: 'Open Workspace',
        group: 'Views',
        run: () => onSetGlobalView('workspace'),
      },
      {
        id: 'mind-graph',
        label: 'Open Mind Graph',
        group: 'Views',
        run: () => onSetGlobalView('mind-graph'),
      },
      {
        id: 'history',
        label: 'Open project history',
        group: 'Project',
        run: () => onOpenHistory(),
      },
      {
        id: 'vera',
        label: 'Focus Vera input',
        group: 'Project',
        run: () => onFocusVera(),
      },
      {
        id: 'next-action',
        label: 'Open Next Action',
        group: 'Project',
        run: () => onOpenNextAction(),
      },
    ];

    for (const key of ARTIFACT_ORDER) {
      const def = ARTIFACT_REGISTRY[key];
      items.push({
        id: `artifact-${key}`,
        label: `Select ${def.label}`,
        group: 'Artifacts',
        run: () => onSelectArtifact(key),
      });
    }

    const requirements = selectArtifactByType(state.artifacts, 'requirement-set');
    for (const req of requirements?.content.requirements ?? []) {
      items.push({
        id: `req-${req.requirementId}`,
        label: `${req.displayId}: ${req.statement.slice(0, 72)}`,
        group: 'Requirements',
        run: () => onSelectRequirement(req.requirementId),
      });
    }

    return items;
  }, [
    onFocusVera,
    onOpenHistory,
    onOpenNextAction,
    onSelectArtifact,
    onSelectRequirement,
    onSetGlobalView,
    state.artifacts,
  ]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) => c.label.toLowerCase().includes(q) || c.group.toLowerCase().includes(q),
    );
  }, [commands, query]);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setActiveIndex(0);
    const id = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(id);
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  if (!open) return null;

  function runCommand(command: Command) {
    command.run();
    onClose();
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(15, 23, 42, 0.45)',
        display: 'flex',
        justifyContent: 'center',
        paddingTop: 80,
      }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: 'min(560px, calc(100vw - 32px))',
          maxHeight: 'min(420px, calc(100vh - 120px))',
          background: t.surface,
          border: `1px solid ${t.border}`,
          borderRadius: 12,
          boxShadow: '0 16px 48px rgba(0,0,0,0.2)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search views, artifacts, requirements…"
          aria-label="Command search"
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              onClose();
            } else if (event.key === 'ArrowDown') {
              event.preventDefault();
              setActiveIndex((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
            } else if (event.key === 'ArrowUp') {
              event.preventDefault();
              setActiveIndex((i) => Math.max(i - 1, 0));
            } else if (event.key === 'Enter' && filtered[activeIndex]) {
              event.preventDefault();
              runCommand(filtered[activeIndex]);
            }
          }}
          style={{
            border: 'none',
            borderBottom: `1px solid ${t.border}`,
            padding: '14px 16px',
            fontSize: 14,
            outline: 'none',
            background: 'transparent',
            color: t.text,
          }}
        />
        <ul
          role="listbox"
          aria-label="Commands"
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 8,
            overflow: 'auto',
          }}
        >
          {filtered.length === 0 ? (
            <li style={{ padding: 12, fontSize: 13, color: t.textMuted }}>No matching commands</li>
          ) : (
            filtered.map((command, index) => {
              const active = index === activeIndex;
              return (
                <li key={command.id} role="option" aria-selected={active}>
                  <button
                    type="button"
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => runCommand(command)}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      border: 'none',
                      borderRadius: 8,
                      padding: '10px 12px',
                      cursor: 'pointer',
                      background: active ? t.cobaltSelected : 'transparent',
                      color: t.text,
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 12,
                      fontSize: 13,
                    }}
                  >
                    <span>{command.label}</span>
                    <span style={{ color: t.textMuted, fontSize: 11 }}>{command.group}</span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>
  );
}
