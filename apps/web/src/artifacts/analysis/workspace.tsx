import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from 'react';
import type { ArtifactCommand, ArtifactCommandResult } from '@nexus/contracts';
import { Clock, FilePlus, Play, RefreshCw, Save, Trash2, Wand2 } from 'lucide-react';
import {
  ApiClientError,
  applyAnalysisPatch,
  deleteWorkspaceRuntimeFile,
  discardAnalysisPatch,
  getWorkspaceRuntimeBinding,
  listWorkspaceRuntimeFiles,
  proposeAnalysisPatch,
  readWorkspaceRuntimeFile,
  generateAnalysisScaffold,
  runAnalysis,
  submitArtifactCommand,
  writeWorkspaceRuntimeFile,
  uploadAnalysisInputFile,
  listProducedOutputs,
  importProducedOutputIntoAnalysisInput,
} from '../../api/client';
import { themeColors } from '../../lib/theme';
import { AnalysisFileTree } from './FileTree';
import { AnalysisMonacoEditor } from './MonacoEditor';
import { AnalysisOutputPanel } from './AnalysisOutputPanel';
import { AnalysisHistoryPanel } from './AnalysisHistoryPanel';
import { AnalysisDiffEditor } from './AnalysisDiffEditor';
import { AnalysisModeTabs } from './AnalysisModeTabs';
import { AnalysisResultsView } from './AnalysisResultsView';
import { AnalysisDataView } from './AnalysisDataView';
import {
  INVESTIGATION_PATH,
  parseInvestigation,
  type AnalysisInvestigation,
  type AnalysisWorkspaceMode,
} from './modes';
import { buildFileTree, type WorkspaceFileMeta } from '../firmware/file-tree';
import { isLikelyBinaryContent } from '../firmware/language';

const ARTIFACT_TYPE = 'analysis';

type BindingInfo = {
  projectId: string;
  artifactId: string;
  artifactType: string;
  workspaceId: string;
  baseArtifactVersion: number;
  baseProjectStateVersion: number;
  filesystemEnabled: boolean;
  capabilities: {
    filesystem?: boolean;
    snapshots?: boolean;
    execution?: boolean;
    logs?: boolean;
  };
};

type DraftMeta = {
  draftVersion: number;
};

type FileBuffer = {
  content: string;
  baseline: string;
  dirty: boolean;
  unsupported: boolean;
  reason?: string;
};

type PatchOperation = {
  operationType: string;
  path: string;
  content?: string;
};

type PatchProposal = {
  proposalId: string;
  baseSnapshotId: string;
  operations: PatchOperation[];
};

type PatchPreview = {
  path: string;
  operationType: string;
  original: string;
  modified: string;
};

type Props = {
  projectId: string;
  isDark: boolean;
  onCommandResult?: (result: ArtifactCommandResult) => void;
};

function userActor() {
  return {
    schemaVersion: '1.0.0' as const,
    actorId: 'user_local',
    actorType: 'user' as const,
    displayName: 'User',
  };
}

function newCommandId(): string {
  return `cmd_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiClientError) {
    return err.body?.error.message ?? err.message;
  }
  if (err instanceof Error) return err.message;
  return fallback;
}

function parseBinding(payload: Record<string, unknown>): {
  binding: BindingInfo;
  draft: DraftMeta;
} | null {
  const bindingRaw = isRecord(payload.binding) ? payload.binding : payload;
  const draftRaw = isRecord(payload.draft) ? payload.draft : null;

  if (
    typeof bindingRaw.projectId !== 'string' ||
    typeof bindingRaw.artifactId !== 'string' ||
    typeof bindingRaw.workspaceId !== 'string'
  ) {
    return null;
  }

  return {
    binding: {
      projectId: bindingRaw.projectId,
      artifactId: bindingRaw.artifactId,
      artifactType: String(bindingRaw.artifactType ?? ARTIFACT_TYPE),
      workspaceId: bindingRaw.workspaceId,
      baseArtifactVersion: Number(bindingRaw.baseArtifactVersion ?? 1),
      baseProjectStateVersion: Number(bindingRaw.baseProjectStateVersion ?? 1),
      filesystemEnabled: Boolean(bindingRaw.filesystemEnabled),
      capabilities: isRecord(bindingRaw.capabilities)
        ? (bindingRaw.capabilities as BindingInfo['capabilities'])
        : {},
    },
    draft: {
      draftVersion: Number(draftRaw?.draftVersion ?? 1),
    },
  };
}

function parseFileList(payload: Record<string, unknown>): WorkspaceFileMeta[] {
  const files = payload.files;
  if (!Array.isArray(files)) return [];
  return files
    .filter(isRecord)
    .map((item) => ({
      path: String(item.path ?? ''),
      sizeBytes: typeof item.sizeBytes === 'number' ? item.sizeBytes : undefined,
      mediaType: typeof item.mediaType === 'string' ? item.mediaType : undefined,
      origin: typeof item.origin === 'string' ? item.origin : undefined,
      writePolicy: typeof item.writePolicy === 'string' ? item.writePolicy : undefined,
    }))
    .filter((item) => item.path.length > 0);
}

function extractDraftVersion(payload: Record<string, unknown>, fallback: number): number {
  return isRecord(payload.draft) && typeof payload.draft.draftVersion === 'number'
    ? payload.draft.draftVersion
    : fallback;
}

function extractBases(payload: Record<string, unknown>, binding: BindingInfo): Partial<BindingInfo> {
  const workspace = payload.workspace;
  if (!isRecord(workspace)) return {};
  return {
    baseArtifactVersion: typeof workspace.baseArtifactVersion === 'number' ? workspace.baseArtifactVersion : binding.baseArtifactVersion,
    baseProjectStateVersion:
      typeof workspace.baseProjectStateVersion === 'number'
        ? workspace.baseProjectStateVersion
        : binding.baseProjectStateVersion,
  };
}

function isLeaseHeldError(err: unknown): boolean {
  return err instanceof ApiClientError && err.body?.error.code === 'DRAFT_EDIT_LEASE_HELD';
}

function isLeaseHeldResult(result: ArtifactCommandResult): boolean {
  return result.error?.code === 'DRAFT_EDIT_LEASE_HELD';
}

export function AnalysisWorkspace({ projectId, isDark, onCommandResult }: Props) {
  const t = themeColors(isDark);
  const actor = useMemo(() => userActor(), []);

  const [binding, setBinding] = useState<BindingInfo | null>(null);
  const [draftVersion, setDraftVersion] = useState(1);
  const [files, setFiles] = useState<WorkspaceFileMeta[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [buffers, setBuffers] = useState<Record<string, FileBuffer>>({});
  const [leaseToken, setLeaseToken] = useState<string | null>(null);
  const [leaseBlocked, setLeaseBlocked] = useState(false);

  const [bindingLoading, setBindingLoading] = useState(true);
  const [filesLoading, setFilesLoading] = useState(false);
  const [fileLoading, setFileLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const [createPath, setCreatePath] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [importChoices, setImportChoices] = useState<
    Array<{ outputId: string; name: string; executionRunId: string }>
  >([]);
  const [importOutputId, setImportOutputId] = useState('');
  const [importing, setImporting] = useState(false);

  // execution session (Phase 16D)
  const [running, setRunning] = useState(false);
  const [execSession, setExecSession] = useState<{
    executionRunId: string;
    executionSnapshotId?: string;
    operation: string;
    baselineExecutionRunId?: string;
  } | null>(null);

  // Results | Code | Data | History (Phase 16I productization)
  const [mode, setMode] = useState<AnalysisWorkspaceMode>('results');
  const [investigation, setInvestigation] = useState<AnalysisInvestigation | null>(null);

  // patch proposal (Phase 16C/G)
  const [showPatchPanel, setShowPatchPanel] = useState(false);
  const [patchRequest, setPatchRequest] = useState('');
  const [patchProposing, setPatchProposing] = useState(false);
  const [patchProposal, setPatchProposal] = useState<PatchProposal | null>(null);
  const [patchPreviewIndex, setPatchPreviewIndex] = useState(0);
  const [patchPreviews, setPatchPreviews] = useState<PatchPreview[]>([]);
  const [patchApplying, setPatchApplying] = useState(false);
  const [patchDiscarding, setPatchDiscarding] = useState(false);
  const [lastCompletedRunId, setLastCompletedRunId] = useState<string | null>(null);

  const leaseTokenRef = useRef<string | null>(null);
  const bindingRef = useRef<BindingInfo | null>(null);
  useEffect(() => {
    leaseTokenRef.current = leaseToken;
  }, [leaseToken]);
  useEffect(() => {
    bindingRef.current = binding;
  }, [binding]);

  const dirtyPaths = useMemo(() => {
    const set = new Set<string>();
    for (const [path, buffer] of Object.entries(buffers)) {
      if (buffer.dirty) set.add(path);
    }
    return set;
  }, [buffers]);

  const hasCode = useMemo(
    () => files.some((f) => f.path === 'analysis.py' || f.path.endsWith('.py')),
    [files],
  );
  const hasData = useMemo(
    () => files.some((f) => f.path.startsWith('data/') && f.path !== 'data/'),
    [files],
  );
  const codeFiles = useMemo(
    () => files.filter((f) => !f.path.startsWith('data/')),
    [files],
  );
  const codeTree = useMemo(() => buildFileTree(codeFiles), [codeFiles]);

  const refreshInvestigation = useCallback(async () => {
    try {
      const payload = await readWorkspaceRuntimeFile(projectId, ARTIFACT_TYPE, INVESTIGATION_PATH);
      const content = typeof payload.content === 'string' ? payload.content : '';
      if (!content.trim()) {
        setInvestigation(null);
        return;
      }
      setInvestigation(parseInvestigation(JSON.parse(content)));
    } catch {
      setInvestigation(null);
    }
  }, [projectId]);

  const releaseLease = useCallback(async () => {
    const current = bindingRef.current;
    const token = leaseTokenRef.current;
    if (!current || !token) return;
    try {
      const result = await submitArtifactCommand(projectId, {
        schemaVersion: '1.0.0',
        commandId: newCommandId(),
        commandType: 'workspace.release-edit-lease',
        projectId,
        artifactId: current.artifactId,
        workspaceId: current.workspaceId,
        baseArtifactVersion: current.baseArtifactVersion,
        baseProjectStateVersion: current.baseProjectStateVersion,
        requestedAt: new Date().toISOString(),
        requestedBy: actor,
        input: { leaseToken: token },
      } as ArtifactCommand);
      onCommandResult?.(result);
    } catch {
      // Best-effort release on unmount.
    } finally {
      setLeaseToken(null);
      leaseTokenRef.current = null;
    }
  }, [actor, onCommandResult, projectId]);

  const refreshFiles = useCallback(async () => {
    setFilesLoading(true);
    try {
      const listed = await listWorkspaceRuntimeFiles(projectId, ARTIFACT_TYPE);
      setFiles(parseFileList(listed));
      if (isRecord(listed.binding)) {
        const parsed = parseBinding(listed);
        if (parsed) {
          setBinding(parsed.binding);
          setDraftVersion(parsed.draft.draftVersion);
        }
      }
    } catch (err) {
      setError(errorMessage(err, 'Failed to list analysis files.'));
    } finally {
      setFilesLoading(false);
    }
  }, [projectId]);

  const ensureEditLease = useCallback(async (): Promise<boolean> => {
    if (leaseBlocked) return false;
    if (leaseTokenRef.current) return true;
    const current = bindingRef.current;
    if (!current) return false;
    try {
      const result = await submitArtifactCommand(projectId, {
        schemaVersion: '1.0.0',
        commandId: newCommandId(),
        commandType: 'workspace.acquire-edit-lease',
        projectId,
        artifactId: current.artifactId,
        workspaceId: current.workspaceId,
        baseArtifactVersion: current.baseArtifactVersion,
        baseProjectStateVersion: current.baseProjectStateVersion,
        requestedAt: new Date().toISOString(),
        requestedBy: actor,
        input: {},
      } as ArtifactCommand);
      onCommandResult?.(result);
      if (isLeaseHeldResult(result)) {
        setLeaseBlocked(true);
        setError('Another editor holds the draft lease.');
        return false;
      }
      if (result.status === 'failed' || result.status === 'rejected') {
        setError(result.error?.message ?? `Lease acquire ${result.status}`);
        return false;
      }
      const token =
        (result.resultPayload?.editLease as { leaseToken?: string } | undefined)?.leaseToken ??
        null;
      if (token) {
        setLeaseToken(token);
        leaseTokenRef.current = token;
      }
      setLeaseBlocked(false);
      return true;
    } catch (err) {
      if (isLeaseHeldError(err)) {
        setLeaseBlocked(true);
        setError('Another editor holds the draft lease.');
        return false;
      }
      setError(errorMessage(err, 'Failed to acquire edit lease.'));
      return false;
    }
  }, [actor, leaseBlocked, onCommandResult, projectId]);

  useEffect(() => {
    let cancelled = false;
    async function openWorkspace() {
      setBindingLoading(true);
      setError(null);
      try {
        const payload = await getWorkspaceRuntimeBinding(projectId, ARTIFACT_TYPE);
        if (cancelled) return;
        const parsed = parseBinding(payload);
        if (!parsed) {
          setError('Unexpected workspace runtime binding response.');
          return;
        }
        if (!parsed.binding.filesystemEnabled && !parsed.binding.capabilities.filesystem) {
          setError('Analysis filesystem capability is not enabled.');
          setBinding(parsed.binding);
          return;
        }
        setBinding(parsed.binding);
        setDraftVersion(parsed.draft.draftVersion);
        bindingRef.current = parsed.binding;
        setFilesLoading(true);
        const listed = await listWorkspaceRuntimeFiles(projectId, ARTIFACT_TYPE);
        if (cancelled) return;
        setFiles(parseFileList(listed));
        await refreshInvestigation();
        // Hydrate latest Analysis ProducedOutput run so Results is default when results exist.
        try {
          const outputs = await listProducedOutputs(projectId);
          if (cancelled) return;
          const scoped = outputs
            .filter((item) => item.workspaceId === parsed.binding.workspaceId)
            .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
          const latest = scoped[0];
          if (latest?.executionRunId) {
            setExecSession({
              executionRunId: latest.executionRunId,
              operation: 'run',
            });
            setLastCompletedRunId(latest.executionRunId);
            setMode('results');
          }
        } catch {
          // No prior outputs — keep empty Results state.
        }
      } catch (err) {
        if (!cancelled) setError(errorMessage(err, 'Failed to open Analysis workspace.'));
      } finally {
        if (!cancelled) {
          setBindingLoading(false);
          setFilesLoading(false);
        }
      }
    }
    void openWorkspace();
    return () => {
      cancelled = true;
      void releaseLease();
    };
  }, [projectId, releaseLease, refreshInvestigation]);

  const loadFile = useCallback(
    async (path: string) => {
      setFileLoading(true);
      setError(null);
      try {
        const payload = await readWorkspaceRuntimeFile(projectId, ARTIFACT_TYPE, path);
        if (isLikelyBinaryContent(payload)) {
          setBuffers((prev) => ({
            ...prev,
            [path]: {
              content: '',
              baseline: '',
              dirty: false,
              unsupported: true,
              reason: 'Preview not yet supported for this file type.',
            },
          }));
          return;
        }
        const content = typeof payload.content === 'string' ? payload.content : '';
        setBuffers((prev) => ({
          ...prev,
          [path]: {
            content,
            baseline: content,
            dirty: false,
            unsupported: false,
          },
        }));
      } catch (err) {
        setError(errorMessage(err, `Failed to read ${path}.`));
      } finally {
        setFileLoading(false);
      }
    },
    [projectId],
  );

  const selectFile = useCallback(
    async (path: string) => {
      if (selectedPath === path) return;
      if (selectedPath && buffers[selectedPath]?.dirty) {
        const proceed = window.confirm(
          `${selectedPath} has unsaved changes. Discard and switch files?`,
        );
        if (!proceed) return;
      }
      setSelectedPath(path);
      if (!buffers[path]) await loadFile(path);
    },
    [buffers, loadFile, selectedPath],
  );

  const onEditorChange = useCallback(
    (value: string) => {
      if (!selectedPath) return;
      setBuffers((prev) => {
        const existing = prev[selectedPath];
        if (!existing) {
          return {
            ...prev,
            [selectedPath]: {
              content: value,
              baseline: value,
              dirty: false,
              unsupported: false,
            },
          };
        }
        return {
          ...prev,
          [selectedPath]: {
            ...existing,
            content: value,
            dirty: value !== existing.baseline,
          },
        };
      });
    },
    [selectedPath],
  );

  const activeBuffer = selectedPath ? buffers[selectedPath] : undefined;

  const saveSelected = useCallback(async () => {
    if (!selectedPath || !binding) return;
    const buffer = buffers[selectedPath];
    if (!buffer || buffer.unsupported || !buffer.dirty) return;
    const leased = await ensureEditLease();
    if (!leased) return;
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      const result = await writeWorkspaceRuntimeFile(projectId, ARTIFACT_TYPE, {
        path: selectedPath,
        content: buffer.content,
        encoding: 'utf-8',
        expectedDraftVersion: draftVersion,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
        requestedBy: actor,
        origin: 'USER',
        writePolicy: 'USER_EDITABLE',
      });
      const nextDraft = extractDraftVersion(result, draftVersion);
      const bases = extractBases(result, binding);
      setDraftVersion(nextDraft);
      setBinding((prev) => (prev ? { ...prev, ...bases } : prev));
      setBuffers((prev) => ({
        ...prev,
        [selectedPath]: {
          ...buffer,
          baseline: buffer.content,
          dirty: false,
          unsupported: false,
        },
      }));
      await refreshFiles();
      setStatusMessage(`Saved ${selectedPath}`);
    } catch (err) {
      setError(errorMessage(err, `Failed to save ${selectedPath}.`));
    } finally {
      setSaving(false);
    }
  }, [
    actor,
    binding,
    buffers,
    draftVersion,
    ensureEditLease,
    projectId,
    refreshFiles,
    selectedPath,
  ]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        void saveSelected();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [saveSelected]);

  const deleteSelected = useCallback(async () => {
    if (!selectedPath || !binding) return;
    if (buffers[selectedPath]?.dirty) {
      const proceed = window.confirm(`${selectedPath} has unsaved changes. Delete anyway?`);
      if (!proceed) return;
    } else {
      const proceed = window.confirm(`Delete ${selectedPath}?`);
      if (!proceed) return;
    }
    const leased = await ensureEditLease();
    if (!leased) return;
    setDeleting(true);
    setError(null);
    try {
      const result = await deleteWorkspaceRuntimeFile(
        projectId,
        ARTIFACT_TYPE,
        selectedPath,
        {
          expectedDraftVersion: draftVersion,
          baseArtifactVersion: binding.baseArtifactVersion,
          baseProjectStateVersion: binding.baseProjectStateVersion,
          actorId: actor.actorId,
        },
      );
      const nextDraft = extractDraftVersion(result, draftVersion + 1);
      const bases = extractBases(result, binding);
      setDraftVersion(nextDraft);
      setBinding((prev) => (prev ? { ...prev, ...bases } : prev));
      setBuffers((prev) => {
        const next = { ...prev };
        delete next[selectedPath];
        return next;
      });
      setSelectedPath(null);
      await refreshFiles();
      setStatusMessage(`Deleted ${selectedPath}`);
    } catch (err) {
      setError(errorMessage(err, `Failed to delete ${selectedPath}.`));
    } finally {
      setDeleting(false);
    }
  }, [actor.actorId, binding, buffers, draftVersion, ensureEditLease, projectId, refreshFiles, selectedPath]);

  const scaffoldAnalysis = useCallback(async () => {
    if (!binding) return;
    if (dirtyPaths.size > 0) {
      setError('Save or discard unsaved changes before scaffolding.');
      return;
    }
    const leased = await ensureEditLease();
    if (!leased) return;
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      const result = await generateAnalysisScaffold(projectId, {
        expectedDraftVersion: draftVersion,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
        requestedBy: actor,
      });
      const nextDraft = extractDraftVersion(result, draftVersion + 1);
      const bases = extractBases(result, binding);
      setDraftVersion(nextDraft);
      setBinding((prev) => (prev ? { ...prev, ...bases } : prev));
      await refreshFiles();
      const primary = typeof result.primaryPath === 'string' ? result.primaryPath : 'analysis.py';
      setSelectedPath(primary);
      await loadFile(primary);
      setMode('code');
      setStatusMessage('Analysis scaffold generated');
    } catch (err) {
      setError(errorMessage(err, 'Failed to generate analysis scaffold.'));
    } finally {
      setSaving(false);
    }
  }, [actor, binding, dirtyPaths.size, draftVersion, ensureEditLease, loadFile, projectId, refreshFiles]);

  const startRun = useCallback(async () => {
    if (!binding) return;
    if (dirtyPaths.size > 0) {
      setError('Save or discard unsaved changes before running.');
      return;
    }
    setRunning(true);
    setError(null);
    setStatusMessage(null);
    try {
      const result = await runAnalysis(projectId, {
        requestedBy: actor,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
      });
      const run = isRecord(result.executionRun) ? result.executionRun : null;
      const runId = run && typeof run.executionRunId === 'string' ? run.executionRunId : null;
      if (!runId) throw new Error('Run did not return an execution run.');
      setExecSession({
        executionRunId: runId,
        operation: 'run',
        executionSnapshotId:
          typeof result.executionSnapshotId === 'string'
            ? result.executionSnapshotId
            : undefined,
      });
      setLastCompletedRunId(runId);
      setMode('results');
      setStatusMessage('Analysis run started');
    } catch (err) {
      setError(errorMessage(err, 'Failed to start analysis run.'));
    } finally {
      setRunning(false);
    }
  }, [actor, binding, dirtyPaths.size, projectId]);

  const parsePatchProposal = (payload: Record<string, unknown>): PatchProposal | null => {
    const proposal = isRecord(payload.proposal) ? payload.proposal : payload;
    if (typeof proposal.proposalId !== 'string' || typeof proposal.baseSnapshotId !== 'string') {
      return null;
    }
    const opsRaw = Array.isArray(proposal.operations) ? proposal.operations : [];
    const operations: PatchOperation[] = opsRaw
      .filter((item): item is Record<string, unknown> => isRecord(item))
      .map((item) => ({
        operationType: String(item.operationType ?? ''),
        path: String(item.path ?? ''),
        content: typeof item.content === 'string' ? item.content : undefined,
      }))
      .filter((item) => item.path.length > 0);
    return {
      proposalId: proposal.proposalId,
      baseSnapshotId: proposal.baseSnapshotId,
      operations,
    };
  };

  const buildPatchPreviews = useCallback(
    async (proposal: PatchProposal): Promise<PatchPreview[]> => {
      const previews: PatchPreview[] = [];
      for (const operation of proposal.operations) {
        let original = '';
        const buffered = buffers[operation.path];
        if (buffered && !buffered.unsupported) {
          original = buffered.baseline;
        } else {
          try {
            const file = await readWorkspaceRuntimeFile(projectId, ARTIFACT_TYPE, operation.path);
            original = typeof file.content === 'string' ? file.content : '';
          } catch {
            original = '';
          }
        }
        previews.push({
          path: operation.path,
          operationType: operation.operationType,
          original,
          modified:
            operation.operationType === 'delete-file' ? '' : (operation.content ?? ''),
        });
      }
      return previews;
    },
    [buffers, projectId],
  );

  const proposePatch = useCallback(async () => {
    if (!binding) return;
    const request = patchRequest.trim();
    if (!request) {
      setError('Describe the analysis change you want.');
      return;
    }
    setPatchProposing(true);
    setError(null);
    setStatusMessage(null);
    try {
      const result = await proposeAnalysisPatch(projectId, {
        requestedChange: request,
        requestedBy: actor,
      });
      const parsed = parsePatchProposal(result);
      if (!parsed) throw new Error('Invalid patch proposal response.');
      const previews = await buildPatchPreviews(parsed);
      setPatchProposal(parsed);
      setPatchPreviews(previews);
      setPatchPreviewIndex(0);
      setShowPatchPanel(true);
      setStatusMessage(`Patch proposal ready (${parsed.operations.length} file changes)`);
    } catch (err) {
      setError(errorMessage(err, 'Failed to generate analysis patch proposal.'));
    } finally {
      setPatchProposing(false);
    }
  }, [actor, binding, buildPatchPreviews, patchRequest, projectId]);

  const applyPatch = useCallback(async () => {
    if (!binding || !patchProposal) return;
    const leased = await ensureEditLease();
    if (!leased) return;
    setPatchApplying(true);
    setError(null);
    try {
      const result = await applyAnalysisPatch(projectId, {
        proposalId: patchProposal.proposalId,
        expectedDraftVersion: draftVersion,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
        requestedBy: actor,
      });
      const nextDraft = extractDraftVersion(result, draftVersion + 1);
      const bases = extractBases(result, binding);
      setDraftVersion(nextDraft);
      setBinding((prev) => (prev ? { ...prev, ...bases } : prev));
      setPatchProposal(null);
      setPatchPreviews([]);
      setBuffers({});
      await refreshFiles();
      setStatusMessage('Applied analysis patch');
    } catch (err) {
      if (err instanceof ApiClientError && err.body?.error.code === 'ANALYSIS_PATCH_STALE') {
        setError(
          'This patch is stale — workspace files changed since the proposal. Regenerate the patch.',
        );
      } else {
        setError(errorMessage(err, 'Failed to apply analysis patch.'));
      }
    } finally {
      setPatchApplying(false);
    }
  }, [
    actor,
    binding,
    draftVersion,
    ensureEditLease,
    patchProposal,
    projectId,
    refreshFiles,
  ]);

  const discardPatch = useCallback(async () => {
    if (!binding || !patchProposal) return;
    setPatchDiscarding(true);
    try {
      await discardAnalysisPatch(projectId, {
        proposalId: patchProposal.proposalId,
        requestedBy: actor,
      });
      setPatchProposal(null);
      setPatchPreviews([]);
      setStatusMessage('Discarded analysis patch proposal');
    } catch (err) {
      setError(errorMessage(err, 'Failed to discard analysis patch.'));
    } finally {
      setPatchDiscarding(false);
    }
  }, [actor, binding, patchProposal, projectId]);

  const onUpload = useCallback(async () => {
    if (!binding || !uploadFile) return;
    const leased = await ensureEditLease();
    if (!leased) return;
    setUploading(true);
    setError(null);
    setStatusMessage(null);
    try {
      const arrayBuffer = await uploadFile.arrayBuffer();
      const bytes = new Uint8Array(arrayBuffer);
      const base64 = btoa(String.fromCharCode(...bytes));
      const safeName = uploadFile.name.replace(/[\\/]/g, '_').trim() || 'upload.bin';
      const targetPath = `data/${safeName}`;
      const result = await uploadAnalysisInputFile(projectId, {
        path: targetPath,
        contentBase64: base64,
        expectedDraftVersion: draftVersion,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
        requestedBy: actor,
        mediaType: uploadFile.type || 'application/octet-stream',
      });
      const nextDraft = extractDraftVersion(result, draftVersion + 1);
      const bases = extractBases(result, binding);
      setDraftVersion(nextDraft);
      setBinding((prev) => (prev ? { ...prev, ...bases } : prev));
      await refreshFiles();
      setSelectedPath(targetPath);
      await loadFile(targetPath);
      setStatusMessage(`Uploaded ${safeName}`);
      setUploadFile(null);
    } catch (err) {
      setError(errorMessage(err, 'Failed to upload analysis input.'));
    } finally {
      setUploading(false);
    }
  }, [actor, binding, draftVersion, ensureEditLease, loadFile, projectId, refreshFiles, uploadFile]);

  const refreshImportChoices = useCallback(async () => {
    try {
      const listed = await listProducedOutputs(projectId);
      setImportChoices(
        listed
          .filter((item) => typeof item.outputId === 'string' && item.outputId.length > 0)
          .map((item) => ({
            outputId: item.outputId,
            name: String(item.name ?? item.outputId),
            executionRunId: String(item.executionRunId ?? ''),
          }))
          .slice(0, 40),
      );
    } catch {
      setImportChoices([]);
    }
  }, [projectId]);

  useEffect(() => {
    if (mode === 'data') void refreshImportChoices();
  }, [mode, refreshImportChoices]);

  const onImportProduced = useCallback(async () => {
    if (!binding || !importOutputId) return;
    const leased = await ensureEditLease();
    if (!leased) return;
    setImporting(true);
    setError(null);
    setStatusMessage(null);
    try {
      const chosen = importChoices.find((c) => c.outputId === importOutputId);
      const safeName = (chosen?.name ?? importOutputId).replace(/[\\/]/g, '_').split('/').pop() || 'imported.bin';
      const result = await importProducedOutputIntoAnalysisInput(projectId, {
        outputId: importOutputId,
        path: `data/${safeName}`,
        expectedDraftVersion: draftVersion,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
        requestedBy: actor,
      });
      const nextDraft = extractDraftVersion(result, draftVersion + 1);
      const bases = extractBases(result, binding);
      setDraftVersion(nextDraft);
      setBinding((prev) => (prev ? { ...prev, ...bases } : prev));
      await refreshFiles();
      setStatusMessage(`Imported ProducedOutput ${safeName}`);
      setImportOutputId('');
      await refreshImportChoices();
    } catch (err) {
      setError(errorMessage(err, 'Failed to import ProducedOutput.'));
    } finally {
      setImporting(false);
    }
  }, [
    actor,
    binding,
    draftVersion,
    ensureEditLease,
    importChoices,
    importOutputId,
    projectId,
    refreshFiles,
    refreshImportChoices,
  ]);

  const createFile = useCallback(async () => {
    if (!binding) return;
    const path = createPath.trim().replace(/^\/+/, '');
    if (!path) {
      setError('Enter a workspace-relative file path.');
      return;
    }
    if (files.some((f) => f.path === path)) {
      setError(`File already exists: ${path}`);
      return;
    }
    const leased = await ensureEditLease();
    if (!leased) return;
    setSaving(true);
    setError(null);
    try {
      const result = await writeWorkspaceRuntimeFile(projectId, ARTIFACT_TYPE, {
        path,
        content: '',
        encoding: 'utf-8',
        expectedDraftVersion: draftVersion,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
        requestedBy: actor,
        origin: 'USER',
        writePolicy: 'USER_EDITABLE',
      });
      const nextDraft = extractDraftVersion(result, draftVersion + 1);
      const bases = extractBases(result, binding);
      setDraftVersion(nextDraft);
      setBinding((prev) => (prev ? { ...prev, ...bases } : prev));
      setBuffers((prev) => ({
        ...prev,
        [path]: { content: '', baseline: '', dirty: false, unsupported: false },
      }));
      setSelectedPath(path);
      setShowCreate(false);
      setCreatePath('');
      await refreshFiles();
      setStatusMessage(`Created ${path}`);
    } catch (err) {
      setError(errorMessage(err, `Failed to create ${path}.`));
    } finally {
      setSaving(false);
    }
  }, [actor, binding, createPath, draftVersion, ensureEditLease, files, projectId, refreshFiles]);

  const panelStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0,
    background: t.surface,
    borderRight: `1px solid ${t.border}`,
  };

  if (bindingLoading) {
    return (
      <div data-testid="analysis-workspace-loading" style={{ padding: 24, color: t.textMuted }}>
        Opening Analysis workspace…
      </div>
    );
  }

  if (error && !binding) {
    return (
      <div data-testid="analysis-workspace-error" style={{ padding: 24, color: t.text }}>
        <h3 style={{ marginTop: 0 }}>Analysis workspace unavailable</h3>
        <p style={{ color: t.textSec }}>{error}</p>
      </div>
    );
  }

  const uploadSlot = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <input
        data-testid="analysis-upload-input"
        type="file"
        onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
        style={{ fontSize: 12, color: t.textSec }}
        disabled={uploading || saving || importing}
      />
      <button
        type="button"
        data-testid="analysis-upload-submit"
        onClick={() => void onUpload()}
        disabled={!uploadFile || uploading || saving || importing}
        style={btn(t, !uploadFile || uploading || saving || importing)}
      >
        Upload
      </button>
      <label style={{ fontSize: 10, color: t.textMuted, marginTop: 4 }} htmlFor="analysis-import-output">
        Import ProducedOutput
      </label>
      <select
        id="analysis-import-output"
        data-testid="analysis-import-output"
        value={importOutputId}
        onChange={(e) => setImportOutputId(e.target.value)}
        disabled={importing || saving || uploading || importChoices.length === 0}
        style={{ fontSize: 11, padding: 4 }}
      >
        <option value="">
          {importChoices.length === 0 ? 'No outputs available' : 'Select output…'}
        </option>
        {importChoices.map((item) => (
          <option key={item.outputId} value={item.outputId}>
            {item.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        data-testid="analysis-import-submit"
        onClick={() => void onImportProduced()}
        disabled={!importOutputId || importing || saving || uploading}
        style={btn(t, !importOutputId || importing || saving || uploading)}
      >
        {importing ? 'Importing…' : 'Import'}
      </button>
    </div>
  );

  return (
    <div data-testid="analysis-workspace" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div
        data-testid="analysis-toolbar"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          borderBottom: `1px solid ${t.border}`,
          background: t.surface2,
          flexWrap: 'wrap',
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 12, color: t.text }}>Analysis</span>
        <AnalysisModeTabs
          mode={mode}
          isDark={isDark}
          onChange={(next) => {
            setMode(next);
            if (next === 'code' && !selectedPath && files.some((f) => f.path === 'analysis.py')) {
              void selectFile('analysis.py');
            }
          }}
        />
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" data-testid="analysis-refresh" onClick={() => void refreshFiles()} style={{ ...btn(t) }}>
            <RefreshCw size={14} /> Refresh
          </button>
          {mode === 'code' ? (
            <>
              <button type="button" data-testid="analysis-create-toggle" onClick={() => setShowCreate((v) => !v)} style={btn(t)}>
                <FilePlus size={14} /> Create
              </button>
              <button
                type="button"
                data-testid="analysis-scaffold"
                disabled={saving || dirtyPaths.size > 0 || files.length > 0}
                onClick={() => void scaffoldAnalysis()}
                style={btn(t, saving || dirtyPaths.size > 0 || files.length > 0)}
              >
                Generate
              </button>
              <button
                type="button"
                data-testid="analysis-patch-toggle"
                disabled={files.length === 0}
                onClick={() => setShowPatchPanel((v) => !v)}
                style={btn(t, files.length === 0)}
              >
                <Wand2 size={14} /> Patch
              </button>
              {selectedPath ? (
                <>
                  <button
                    type="button"
                    data-testid="analysis-save"
                    disabled={!activeBuffer?.dirty || saving || Boolean(activeBuffer?.unsupported)}
                    onClick={() => void saveSelected()}
                    style={btn(t, !activeBuffer?.dirty || saving || Boolean(activeBuffer?.unsupported))}
                  >
                    <Save size={14} /> Save
                  </button>
                  <button
                    type="button"
                    data-testid="analysis-delete"
                    disabled={deleting || saving}
                    onClick={() => void deleteSelected()}
                    style={btn(t, deleting || saving)}
                  >
                    <Trash2 size={14} /> Delete
                  </button>
                </>
              ) : null}
            </>
          ) : null}
          <button
            type="button"
            data-testid="analysis-run"
            disabled={running || saving || dirtyPaths.size > 0 || !hasCode}
            onClick={() => void startRun()}
            style={btn(t, running || saving || dirtyPaths.size > 0 || !hasCode)}
          >
            <Play size={14} /> {running ? 'Running…' : 'Run Current'}
          </button>
          {mode !== 'history' ? (
            <button type="button" data-testid="analysis-history-toggle" onClick={() => setMode('history')} style={btn(t, false)}>
              <Clock size={14} /> History
            </button>
          ) : null}
        </div>
      </div>

      {mode === 'code' && showCreate ? (
        <div style={{ padding: '10px 12px', borderBottom: `1px solid ${t.border}`, display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            data-testid="analysis-create-path"
            value={createPath}
            onChange={(e) => setCreatePath(e.target.value)}
            placeholder="e.g. notes.md"
            style={{ flex: 1, padding: 6, border: `1px solid ${t.border}`, borderRadius: 6 }}
          />
          <button type="button" data-testid="analysis-create-submit" onClick={() => void createFile()} style={btn(t)}>
            Create
          </button>
        </div>
      ) : null}

      {mode === 'code' && showPatchPanel && files.length > 0 ? (
        <div
          data-testid="analysis-patch-panel"
          style={{
            padding: '10px 12px',
            borderBottom: `1px solid ${t.border}`,
            background: t.surface2,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          {!patchProposal ? (
            <>
              <label style={{ fontSize: 11, color: t.textMuted }} htmlFor="analysis-patch-request">
                Describe the analysis change
              </label>
              <textarea
                id="analysis-patch-request"
                data-testid="analysis-patch-request"
                value={patchRequest}
                onChange={(e) => setPatchRequest(e.target.value)}
                rows={3}
                style={{ width: '100%', padding: 8, borderRadius: 6, border: `1px solid ${t.border}` }}
              />
              <button
                type="button"
                data-testid="analysis-patch-propose"
                disabled={patchProposing}
                onClick={() => void proposePatch()}
                style={btn(t, patchProposing)}
              >
                {patchProposing ? 'Proposing…' : 'Propose patch'}
              </button>
            </>
          ) : (
            <>
              <div style={{ fontSize: 12, color: t.textSec }}>
                Proposal {patchProposal.proposalId} · {patchProposal.operations.length} operations
              </div>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {patchProposal.operations.map((op, index) => (
                  <li key={`${op.path}-${index}`}>
                    <button type="button" data-testid={`analysis-patch-op-${index}`} onClick={() => setPatchPreviewIndex(index)} style={btn(t, false)}>
                      {op.operationType} · {op.path}
                    </button>
                  </li>
                ))}
              </ul>
              {patchPreviews[patchPreviewIndex] ? (
                <AnalysisDiffEditor
                  path={patchPreviews[patchPreviewIndex].path}
                  original={patchPreviews[patchPreviewIndex].original}
                  modified={patchPreviews[patchPreviewIndex].modified}
                  isDark={isDark}
                />
              ) : null}
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" data-testid="analysis-patch-apply" disabled={patchApplying} onClick={() => void applyPatch()} style={btn(t, patchApplying)}>
                  Apply
                </button>
                <button type="button" data-testid="analysis-patch-discard" disabled={patchDiscarding} onClick={() => void discardPatch()} style={btn(t, patchDiscarding)}>
                  Discard
                </button>
              </div>
            </>
          )}
        </div>
      ) : null}

      {leaseBlocked || error || statusMessage ? (
        <div data-testid="analysis-status-banner" style={{ padding: '8px 12px', fontSize: 12, borderBottom: `1px solid ${t.border}`, background: error || leaseBlocked ? t.cobaltTint : t.surface2, color: t.textSec }}>
          {error ?? statusMessage}
        </div>
      ) : null}

      {mode === 'results' ? (
        <AnalysisResultsView
          projectId={projectId}
          isDark={isDark}
          investigation={investigation}
          session={execSession}
          hasCode={hasCode}
          hasData={hasData}
          running={running}
          onRunCurrent={() => void startRun()}
          onOpenCode={() => {
            setMode('code');
            if (files.some((f) => f.path === 'analysis.py')) void selectFile('analysis.py');
          }}
          onOpenData={() => setMode('data')}
          onGenerateScaffold={() => void scaffoldAnalysis()}
        />
      ) : null}

      {mode === 'data' ? (
        <AnalysisDataView
          projectId={projectId}
          isDark={isDark}
          files={files}
          uploadSlot={uploadSlot}
          onOpenPath={(path) => {
            setMode('code');
            void selectFile(path);
          }}
        />
      ) : null}

      {mode === 'history' ? (
        <div data-testid="analysis-history-mode" style={{ flex: 1, minHeight: 0, display: 'flex' }}>
          <AnalysisHistoryPanel
            projectId={projectId}
            isDark={isDark}
            hasDirtyBuffers={dirtyPaths.size > 0}
            onRequireCleanWorkspace={() => {
              if (dirtyPaths.size === 0) return true;
              return window.confirm('You have unsaved changes. Proceed anyway?');
            }}
            onRestored={async () => {
              setBuffers({});
              setSelectedPath(null);
              await refreshFiles();
              await refreshInvestigation();
            }}
            onRerun={(session) => {
              setExecSession({
                ...session,
                baselineExecutionRunId: lastCompletedRunId ?? undefined,
              });
              setMode('results');
            }}
            actor={actor}
          />
        </div>
      ) : null}

      {mode === 'code' ? (
        <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
          <aside style={{ ...panelStyle, width: 240, flexShrink: 0 }}>
            <div style={{ padding: '8px 10px', fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: t.textMuted, borderBottom: `1px solid ${t.border}` }}>
              Files {filesLoading ? '…' : `(${codeFiles.length})`}
            </div>
            {investigation?.stageVocabulary?.length ? (
              <div data-testid="analysis-code-stage-summary" style={{ padding: '8px 10px', borderBottom: `1px solid ${t.border}`, fontSize: 10, color: t.textMuted }}>
                Stages: {(investigation.stageVocabulary ?? []).join(' → ')}
              </div>
            ) : null}
            <AnalysisFileTree nodes={codeTree} selectedPath={selectedPath} dirtyPaths={dirtyPaths} isDark={isDark} onSelectFile={(path) => void selectFile(path)} />
          </aside>
          <section style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
            {!selectedPath ? (
              <div data-testid="analysis-editor-empty" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: t.textMuted, fontSize: 13, padding: 24, textAlign: 'center', gap: 12 }}>
                {files.length === 0 ? <div>No analysis implementation yet. Generate a scaffold or create a file.</div> : <div>Select a file to start editing.</div>}
                {fileLoading ? <div>Loading…</div> : null}
              </div>
            ) : activeBuffer?.unsupported ? (
              <div data-testid="analysis-unsupported-preview" style={{ flex: 1, padding: 24, overflow: 'auto', color: t.textMuted, fontSize: 13, lineHeight: 1.5 }}>
                Preview not yet supported for this file type.
              </div>
            ) : (
              <AnalysisMonacoEditor path={selectedPath} content={activeBuffer?.content ?? ''} isDark={isDark} readOnly={leaseBlocked} onChange={onEditorChange} />
            )}
            {execSession ? (
              <AnalysisOutputPanel
                projectId={projectId}
                session={execSession}
                isDark={isDark}
                actor={actor}
                onClear={() => setExecSession(null)}
              />
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}

function btn(t: ReturnType<typeof themeColors>, disabled = false): CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    border: `1px solid ${t.border}`,
    background: t.surface2,
    color: disabled ? t.textMuted : t.text,
    borderRadius: 6,
    padding: '5px 8px',
    fontSize: 12,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
  };
}

