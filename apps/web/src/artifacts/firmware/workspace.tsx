import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from 'react';
import type { ArtifactCommand, ArtifactCommandResult } from '@nexus/contracts';
import {
  FilePlus,
  FolderOpen,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react';
import {
  ApiClientError,
  applyFirmwarePatch,
  compileFirmware,
  deleteWorkspaceRuntimeFile,
  discardFirmwarePatch,
  generateFirmwareScaffold,
  getWorkspaceRuntimeBinding,
  listWorkspaceRuntimeFiles,
  proposeFirmwarePatch,
  readWorkspaceRuntimeFile,
  submitArtifactCommand,
  testFirmware,
  writeWorkspaceRuntimeFile,
} from '../../api/client';
import { themeColors } from '../../lib/theme';
import { FirmwareDiffEditor } from './FirmwareDiffEditor';
import { FirmwareFileTree } from './FileTree';
import {
  FirmwareOutputPanel,
  type FirmwareExecutionSession,
} from './FirmwareOutputPanel';
import { FirmwareHistoryPanel } from './FirmwareHistoryPanel';
import { FirmwareMonacoEditor } from './MonacoEditor';
import { buildFileTree, type WorkspaceFileMeta } from './file-tree';
import { isLikelyBinaryContent } from './language';

const ARTIFACT_TYPE = 'firmware';

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

type PatchOperation = {
  operationType: 'create-file' | 'replace-file' | 'delete-file';
  path: string;
  content?: string;
  expectedBaseHash?: string;
  contentHash?: string;
};

type PatchProposal = {
  proposalId: string;
  baseSnapshotId: string;
  requestedChange: string;
  operations: PatchOperation[];
  status: string;
};

type PatchPreview = {
  path: string;
  operationType: PatchOperation['operationType'];
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
  if (isRecord(payload.draft) && typeof payload.draft.draftVersion === 'number') {
    return payload.draft.draftVersion;
  }
  return fallback;
}

function extractBases(
  payload: Record<string, unknown>,
  binding: BindingInfo,
): Pick<BindingInfo, 'baseArtifactVersion' | 'baseProjectStateVersion'> {
  const workspace = isRecord(payload.workspace) ? payload.workspace : null;
  return {
    baseArtifactVersion: Number(
      workspace?.baseArtifactVersion ?? binding.baseArtifactVersion,
    ),
    baseProjectStateVersion: Number(
      workspace?.baseProjectStateVersion ?? binding.baseProjectStateVersion,
    ),
  };
}

type FileBuffer = {
  content: string;
  baseline: string;
  dirty: boolean;
  unsupported: boolean;
  reason?: string;
};

function parsePatchProposal(payload: Record<string, unknown>): PatchProposal | null {
  const proposal = isRecord(payload.proposal) ? payload.proposal : payload;
  if (typeof proposal.proposalId !== 'string' || !Array.isArray(proposal.operations)) {
    return null;
  }
  const operations = proposal.operations.filter(isRecord).map((op) => ({
    operationType: String(op.operationType) as PatchOperation['operationType'],
    path: String(op.path ?? ''),
    content: typeof op.content === 'string' ? op.content : undefined,
    expectedBaseHash: typeof op.expectedBaseHash === 'string' ? op.expectedBaseHash : undefined,
    contentHash: typeof op.contentHash === 'string' ? op.contentHash : undefined,
  }));
  return {
    proposalId: proposal.proposalId,
    baseSnapshotId: String(proposal.baseSnapshotId ?? ''),
    requestedChange: String(proposal.requestedChange ?? ''),
    operations,
    status: String(proposal.status ?? 'proposed'),
  };
}

function isPatchStaleError(err: unknown): boolean {
  return err instanceof ApiClientError && err.body?.error.code === 'FIRMWARE_PATCH_STALE';
}

function isLeaseHeldError(err: unknown): boolean {
  return err instanceof ApiClientError && err.body?.error.code === 'DRAFT_EDIT_LEASE_HELD';
}

function isLeaseHeldResult(result: ArtifactCommandResult): boolean {
  return result.error?.code === 'DRAFT_EDIT_LEASE_HELD';
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiClientError) {
    return err.body?.error.message ?? err.message;
  }
  if (err instanceof Error) return err.message;
  return fallback;
}

export function FirmwareWorkspace({ projectId, isDark, onCommandResult }: Props) {
  const t = themeColors(isDark);
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
  const [scaffolding, setScaffolding] = useState(false);
  const [patchRequest, setPatchRequest] = useState('');
  const [patchProposing, setPatchProposing] = useState(false);
  const [patchProposal, setPatchProposal] = useState<PatchProposal | null>(null);
  const [patchPreviewIndex, setPatchPreviewIndex] = useState(0);
  const [patchPreviews, setPatchPreviews] = useState<PatchPreview[]>([]);
  const [patchApplying, setPatchApplying] = useState(false);
  const [patchDiscarding, setPatchDiscarding] = useState(false);
  const [showPatchPanel, setShowPatchPanel] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [execSession, setExecSession] = useState<FirmwareExecutionSession | null>(null);
  const [compiling, setCompiling] = useState(false);
  const [testing, setTesting] = useState(false);

  const leaseTokenRef = useRef<string | null>(null);
  const bindingRef = useRef<BindingInfo | null>(null);
  const actor = useMemo(() => userActor(), []);

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

  const tree = useMemo(() => buildFileTree(files), [files]);
  const activeBuffer = selectedPath ? buffers[selectedPath] : undefined;

  const releaseLease = useCallback(async () => {
    const current = bindingRef.current;
    const token = leaseTokenRef.current;
    if (!current || !token) return;
    // Cleanup owns this lease; clear it before awaiting the best-effort release.
    leaseTokenRef.current = null;
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
      // Best-effort release on unmount / navigation.
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
      setError(errorMessage(err, 'Failed to list firmware files.'));
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
          setError('Firmware filesystem capability is not enabled.');
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
      } catch (err) {
        if (!cancelled) {
          setError(errorMessage(err, 'Failed to open Firmware workspace.'));
        }
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
  }, [projectId, releaseLease]);

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
              reason: 'Binary or unsupported content cannot be opened in the text editor.',
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
        setBuffers((prev) => {
          const next = { ...prev };
          const current = next[selectedPath];
          if (current) {
            next[selectedPath] = {
              ...current,
              content: current.baseline,
              dirty: false,
            };
          }
          return next;
        });
      }
      setSelectedPath(path);
      setStatusMessage(null);
      if (!buffers[path]) {
        await loadFile(path);
      }
    },
    [buffers, loadFile, selectedPath],
  );

  const onEditorChange = useCallback(
    (value: string) => {
      if (!selectedPath) return;
      setBuffers((prev) => {
        const existing = prev[selectedPath];
        if (!existing || existing.unsupported) return prev;
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
      const nextDraft = extractDraftVersion(result, draftVersion + 1);
      const bases = extractBases(result, binding);
      setDraftVersion(nextDraft);
      setBinding((prev) =>
        prev
          ? {
              ...prev,
              ...bases,
            }
          : prev,
      );
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
  }, [
    actor,
    binding,
    createPath,
    draftVersion,
    ensureEditLease,
    files,
    projectId,
    refreshFiles,
  ]);

  const deleteSelected = useCallback(async () => {
    if (!selectedPath || !binding) return;
    if (buffers[selectedPath]?.dirty) {
      const proceed = window.confirm(
        `${selectedPath} has unsaved changes. Delete anyway?`,
      );
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
  }, [
    actor.actorId,
    binding,
    buffers,
    draftVersion,
    ensureEditLease,
    projectId,
    refreshFiles,
    selectedPath,
  ]);

  const generateScaffold = useCallback(async () => {
    if (!binding) return;
    const leased = await ensureEditLease();
    if (!leased) return;
    setScaffolding(true);
    setError(null);
    setStatusMessage(null);
    try {
      const result = await generateFirmwareScaffold(projectId, {
        expectedDraftVersion: draftVersion,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
        requestedBy: actor,
      });
      const nextDraft = extractDraftVersion(result, draftVersion);
      const bases = extractBases(result, binding);
      setDraftVersion(nextDraft);
      setBinding((prev) => (prev ? { ...prev, ...bases } : prev));
      await refreshFiles();
      const primary =
        typeof result.primaryPath === 'string'
          ? result.primaryPath
          : 'src/main.cpp';
      const status = String(result.status ?? 'generated');
      setStatusMessage(
        status === 'already-generated'
          ? 'Firmware scaffold already present'
          : `Generated ${primary}`,
      );
      setSelectedPath(primary);
      await loadFile(primary);
    } catch (err) {
      setError(errorMessage(err, 'Failed to generate firmware scaffold.'));
    } finally {
      setScaffolding(false);
    }
  }, [
    actor,
    binding,
    draftVersion,
    ensureEditLease,
    loadFile,
    projectId,
    refreshFiles,
  ]);

  const buildPatchPreviews = useCallback(
    async (proposal: PatchProposal): Promise<PatchPreview[]> => {
      const previews: PatchPreview[] = [];
      for (const operation of proposal.operations) {
        if (operation.operationType === 'create-file') {
          previews.push({
            path: operation.path,
            operationType: operation.operationType,
            original: '',
            modified: operation.content ?? '',
          });
          continue;
        }
        let original = buffers[operation.path]?.baseline ?? '';
        if (!original) {
          try {
            const payload = await readWorkspaceRuntimeFile(
              projectId,
              ARTIFACT_TYPE,
              operation.path,
            );
            original = typeof payload.content === 'string' ? payload.content : '';
          } catch {
            original = '';
          }
        }
        if (operation.operationType === 'replace-file') {
          previews.push({
            path: operation.path,
            operationType: operation.operationType,
            original,
            modified: operation.content ?? '',
          });
        } else {
          previews.push({
            path: operation.path,
            operationType: operation.operationType,
            original,
            modified: '',
          });
        }
      }
      return previews;
    },
    [buffers, projectId],
  );

  const proposePatch = useCallback(async () => {
    if (!binding) return;
    const request = patchRequest.trim();
    if (!request) {
      setError('Describe the firmware change you want.');
      return;
    }
    const leased = await ensureEditLease();
    if (!leased) return;
    setPatchProposing(true);
    setError(null);
    setStatusMessage(null);
    try {
      const result = await proposeFirmwarePatch(projectId, {
        requestedChange: request,
        requestedBy: actor,
      });
      const parsed = parsePatchProposal(result);
      if (!parsed) {
        throw new Error('Invalid patch proposal response.');
      }
      const previews = await buildPatchPreviews(parsed);
      setPatchProposal(parsed);
      setPatchPreviews(previews);
      setPatchPreviewIndex(0);
      setShowPatchPanel(true);
      setStatusMessage(`Patch proposal ready (${parsed.operations.length} file changes)`);
    } catch (err) {
      setError(errorMessage(err, 'Failed to generate firmware patch proposal.'));
    } finally {
      setPatchProposing(false);
    }
  }, [actor, binding, buildPatchPreviews, ensureEditLease, patchRequest, projectId]);

  const applyPatch = useCallback(async () => {
    if (!binding || !patchProposal) return;
    const leased = await ensureEditLease();
    if (!leased) return;
    setPatchApplying(true);
    setError(null);
    setStatusMessage(null);
    try {
      const result = await applyFirmwarePatch(projectId, {
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
      setShowPatchPanel(false);
      setPatchRequest('');
      setBuffers({});
      await refreshFiles();
      const firstOp = patchProposal.operations[0];
      if (firstOp) {
        setSelectedPath(firstOp.path);
        await loadFile(firstOp.path);
      }
      setStatusMessage('Applied firmware patch');
    } catch (err) {
      if (isPatchStaleError(err)) {
        setError(
          'This patch is stale — workspace files changed since the proposal. Regenerate the patch.',
        );
      } else {
        setError(errorMessage(err, 'Failed to apply firmware patch.'));
      }
    } finally {
      setPatchApplying(false);
    }
  }, [
    actor,
    binding,
    draftVersion,
    ensureEditLease,
    loadFile,
    patchProposal,
    projectId,
    refreshFiles,
  ]);

  const discardPatch = useCallback(async () => {
    if (!binding || !patchProposal) return;
    setPatchDiscarding(true);
    setError(null);
    try {
      await discardFirmwarePatch(projectId, {
        proposalId: patchProposal.proposalId,
        requestedBy: actor,
      });
      setPatchProposal(null);
      setPatchPreviews([]);
      setShowPatchPanel(false);
      setStatusMessage('Discarded firmware patch proposal');
    } catch (err) {
      setError(errorMessage(err, 'Failed to discard firmware patch proposal.'));
    } finally {
      setPatchDiscarding(false);
    }
  }, [actor, binding, patchProposal, projectId]);

  const requireCleanWorkspace = useCallback((): boolean => {
    if (dirtyPaths.size === 0) return true;
    const proceed = window.confirm(
      'You have unsaved changes. Save or discard them before continuing.',
    );
    return proceed;
  }, [dirtyPaths.size]);

  const startCompile = useCallback(async () => {
    if (!binding) return;
    if (dirtyPaths.size > 0) {
      setError('Save or discard unsaved changes before compiling.');
      return;
    }
    const leased = await ensureEditLease();
    if (!leased) return;
    setCompiling(true);
    setError(null);
    try {
      const result = await compileFirmware(projectId, {
        requestedBy: actor,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
      });
      const run = isRecord(result.executionRun) ? result.executionRun : null;
      const runId = run && typeof run.executionRunId === 'string' ? run.executionRunId : null;
      if (!runId) throw new Error('Compile did not return an execution run.');
      setExecSession({
        executionRunId: runId,
        toolchainMode: isRecord(result.toolchainProfile)
          ? String(result.toolchainProfile.executionMode ?? 'unknown')
          : 'unknown',
        operation: 'compile',
        executionSnapshotId:
          typeof result.executionSnapshotId === 'string'
            ? result.executionSnapshotId
            : undefined,
      });
      setStatusMessage('Compile started');
    } catch (err) {
      setError(errorMessage(err, 'Failed to start firmware compile.'));
    } finally {
      setCompiling(false);
    }
  }, [actor, binding, dirtyPaths.size, ensureEditLease, projectId]);

  const startTest = useCallback(async () => {
    if (!binding) return;
    if (dirtyPaths.size > 0) {
      setError('Save or discard unsaved changes before testing.');
      return;
    }
    const leased = await ensureEditLease();
    if (!leased) return;
    setTesting(true);
    setError(null);
    try {
      const result = await testFirmware(projectId, {
        requestedBy: actor,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
      });
      const run = isRecord(result.executionRun) ? result.executionRun : null;
      const runId = run && typeof run.executionRunId === 'string' ? run.executionRunId : null;
      if (!runId) throw new Error('Test did not return an execution run.');
      setExecSession({
        executionRunId: runId,
        toolchainMode: isRecord(result.toolchainProfile)
          ? String(result.toolchainProfile.executionMode ?? 'unknown')
          : 'unknown',
        operation: 'test',
        executionSnapshotId:
          typeof result.executionSnapshotId === 'string'
            ? result.executionSnapshotId
            : undefined,
      });
      setStatusMessage('Test started');
    } catch (err) {
      setError(errorMessage(err, 'Failed to start firmware test.'));
    } finally {
      setTesting(false);
    }
  }, [actor, binding, dirtyPaths.size, ensureEditLease, projectId]);

  const openDiagnosticLocation = useCallback(
    async (path: string, _line: number) => {
      await selectFile(path);
    },
    [selectFile],
  );

  const panelStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0,
    background: t.surface,
    borderRight: `1px solid ${t.border}`,
  };

  if (bindingLoading) {
    return (
      <div data-testid="firmware-workspace-loading" style={{ padding: 24, color: t.textMuted }}>
        Opening Firmware workspace…
      </div>
    );
  }

  if (error && !binding) {
    return (
      <div data-testid="firmware-workspace-error" style={{ padding: 24, color: t.text }}>
        <h3 style={{ marginTop: 0 }}>Firmware workspace unavailable</h3>
        <p style={{ color: t.textSec }}>{error}</p>
      </div>
    );
  }

  return (
    <div
      data-testid="firmware-workspace"
      style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}
    >
      <div
        data-testid="firmware-toolbar"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          borderBottom: `1px solid ${t.border}`,
          background: t.surface,
          flexShrink: 0,
          flexWrap: 'wrap',
        }}
      >
        <button type="button" data-testid="firmware-refresh" onClick={() => void refreshFiles()} style={btn(t)}>
          <RefreshCw size={14} /> Refresh
        </button>
        <button
          type="button"
          data-testid="firmware-create-toggle"
          onClick={() => setShowCreate((v) => !v)}
          style={btn(t)}
        >
          <FilePlus size={14} /> New file
        </button>
        {files.length === 0 ? (
          <button
            type="button"
            data-testid="firmware-generate-scaffold"
            disabled={scaffolding}
            onClick={() => void generateScaffold()}
            style={btn(t, scaffolding)}
          >
            <Sparkles size={14} /> {scaffolding ? 'Generating…' : 'Generate firmware scaffold'}
          </button>
        ) : null}
        {files.length > 0 ? (
          <button
            type="button"
            data-testid="firmware-patch-toggle"
            onClick={() => setShowPatchPanel((v) => !v)}
            style={btn(t)}
          >
            <Sparkles size={14} /> Request firmware change
          </button>
        ) : null}
        {files.length > 0 ? (
          <>
            <button
              type="button"
              data-testid="firmware-compile"
              disabled={compiling || dirtyPaths.size > 0}
              onClick={() => void startCompile()}
              style={btn(t, compiling || dirtyPaths.size > 0)}
            >
              {compiling ? 'Compiling…' : 'Compile'}
            </button>
            <button
              type="button"
              data-testid="firmware-test"
              disabled={testing || dirtyPaths.size > 0}
              onClick={() => void startTest()}
              style={btn(t, testing || dirtyPaths.size > 0)}
            >
              {testing ? 'Testing…' : 'Test'}
            </button>
            <button
              type="button"
              data-testid="firmware-history-toggle"
              onClick={() => setShowHistory((v) => !v)}
              style={btn(t)}
            >
              History
            </button>
          </>
        ) : null}
        <button
          type="button"
          data-testid="firmware-save"
          disabled={!activeBuffer?.dirty || saving || Boolean(activeBuffer?.unsupported)}
          onClick={() => void saveSelected()}
          style={btn(t, !activeBuffer?.dirty || saving)}
        >
          <Save size={14} /> {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          data-testid="firmware-delete"
          disabled={!selectedPath || deleting}
          onClick={() => void deleteSelected()}
          style={btn(t, !selectedPath || deleting)}
        >
          <Trash2 size={14} /> {deleting ? 'Deleting…' : 'Delete'}
        </button>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: t.textMuted }}>
          {selectedPath ? (
            <>
              <FolderOpen size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              {selectedPath}
              {activeBuffer?.dirty ? ' · unsaved' : ''}
            </>
          ) : (
            'No file selected'
          )}
        </span>
      </div>

      {showCreate ? (
        <div
          data-testid="firmware-create-form"
          style={{
            display: 'flex',
            gap: 8,
            padding: '8px 12px',
            borderBottom: `1px solid ${t.border}`,
            background: t.surface2,
          }}
        >
          <input
            data-testid="firmware-create-path"
            value={createPath}
            onChange={(e) => setCreatePath(e.target.value)}
            placeholder="src/main.cpp"
            style={{
              flex: 1,
              border: `1px solid ${t.border}`,
              borderRadius: 6,
              padding: '6px 8px',
              background: t.surface,
              color: t.text,
              fontSize: 12,
            }}
          />
          <button
            type="button"
            data-testid="firmware-create-submit"
            onClick={() => void createFile()}
            style={btn(t, saving)}
          >
            Create
          </button>
        </div>
      ) : null}

      {showPatchPanel && files.length > 0 ? (
        <div
          data-testid="firmware-patch-panel"
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
              <label style={{ fontSize: 11, color: t.textMuted }} htmlFor="firmware-patch-request">
                Describe the firmware change
              </label>
              <textarea
                id="firmware-patch-request"
                data-testid="firmware-patch-request"
                value={patchRequest}
                onChange={(e) => setPatchRequest(e.target.value)}
                placeholder="e.g. Change serial baud to 9600."
                rows={2}
                style={{
                  width: '100%',
                  resize: 'vertical',
                  border: `1px solid ${t.border}`,
                  borderRadius: 6,
                  padding: '8px 10px',
                  background: t.surface,
                  color: t.text,
                  fontSize: 12,
                  fontFamily: 'inherit',
                }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  data-testid="firmware-patch-propose"
                  disabled={patchProposing}
                  onClick={() => void proposePatch()}
                  style={btn(t, patchProposing)}
                >
                  {patchProposing ? 'Generating…' : 'Generate patch proposal'}
                </button>
              </div>
            </>
          ) : (
            <>
              <div data-testid="firmware-patch-summary" style={{ fontSize: 12, color: t.textSec }}>
                <strong style={{ color: t.text }}>{patchProposal.operations.length}</strong> file
                {patchProposal.operations.length === 1 ? '' : 's'} changed · base{' '}
                {patchProposal.baseSnapshotId.slice(0, 12)}…
              </div>
              <ul
                data-testid="firmware-patch-operations"
                style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.textSec }}
              >
                {patchProposal.operations.map((op, index) => (
                  <li key={`${op.path}-${index}`}>
                    <button
                      type="button"
                      data-testid={`firmware-patch-op-${index}`}
                      onClick={() => setPatchPreviewIndex(index)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: index === patchPreviewIndex ? t.cobalt : t.textSec,
                        cursor: 'pointer',
                        padding: 0,
                        font: 'inherit',
                      }}
                    >
                      {op.operationType} · {op.path}
                    </button>
                  </li>
                ))}
              </ul>
              {patchPreviews[patchPreviewIndex] ? (
                <FirmwareDiffEditor
                  path={patchPreviews[patchPreviewIndex].path}
                  original={patchPreviews[patchPreviewIndex].original}
                  modified={patchPreviews[patchPreviewIndex].modified}
                  isDark={isDark}
                />
              ) : null}
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  data-testid="firmware-patch-apply"
                  disabled={patchApplying}
                  onClick={() => void applyPatch()}
                  style={btn(t, patchApplying)}
                >
                  {patchApplying ? 'Applying…' : 'Apply patch'}
                </button>
                <button
                  type="button"
                  data-testid="firmware-patch-discard"
                  disabled={patchDiscarding}
                  onClick={() => void discardPatch()}
                  style={btn(t, patchDiscarding)}
                >
                  {patchDiscarding ? 'Discarding…' : 'Discard'}
                </button>
              </div>
            </>
          )}
        </div>
      ) : null}

      {leaseBlocked || error || statusMessage ? (
        <div
          data-testid="firmware-status-banner"
          style={{
            padding: '8px 12px',
            fontSize: 12,
            borderBottom: `1px solid ${t.border}`,
            background: error || leaseBlocked ? t.cobaltTint : t.surface2,
            color: t.textSec,
          }}
        >
          {error ?? statusMessage}
        </div>
      ) : null}

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {showHistory ? (
          <FirmwareHistoryPanel
            projectId={projectId}
            isDark={isDark}
            hasDirtyBuffers={dirtyPaths.size > 0}
            onRequireCleanWorkspace={requireCleanWorkspace}
            onRestored={async () => {
              setBuffers({});
              setSelectedPath(null);
              await refreshFiles();
            }}
            actor={actor}
          />
        ) : null}
        <aside style={{ ...panelStyle, width: 240, flexShrink: 0 }}>
          <div
            style={{
              padding: '8px 10px',
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: t.textMuted,
              borderBottom: `1px solid ${t.border}`,
            }}
          >
            Files {filesLoading ? '…' : `(${files.length})`}
          </div>
          <FirmwareFileTree
            nodes={tree}
            selectedPath={selectedPath}
            dirtyPaths={dirtyPaths}
            isDark={isDark}
            onSelectFile={(path) => void selectFile(path)}
          />
        </aside>

        <section style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
          {!selectedPath ? (
            <div
              data-testid="firmware-editor-empty"
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: t.textMuted,
                fontSize: 13,
                padding: 24,
                textAlign: 'center',
                gap: 12,
              }}
            >
              {files.length === 0 ? (
                <>
                  <div>
                    This Firmware workspace is empty. Generate a PlatformIO · ESP32 · Arduino
                    scaffold, or create a file manually.
                  </div>
                  <button
                    type="button"
                    data-testid="firmware-generate-scaffold-empty"
                    disabled={scaffolding}
                    onClick={() => void generateScaffold()}
                    style={{
                      ...btn(t, scaffolding),
                      padding: '8px 14px',
                      fontSize: 13,
                      background: t.cobaltTint,
                      color: t.cobalt,
                      borderColor: t.cobalt,
                    }}
                  >
                    <Sparkles size={14} />{' '}
                    {scaffolding ? 'Generating…' : 'Generate firmware scaffold'}
                  </button>
                  <div style={{ fontSize: 11, color: t.textMuted }}>
                    Fixed profile: platformio-arduino-esp32-v1
                  </div>
                </>
              ) : (
                'Select a file from the tree to open it in the editor.'
              )}
            </div>
          ) : fileLoading && !activeBuffer ? (
            <div data-testid="firmware-file-loading" style={{ padding: 24, color: t.textMuted }}>
              Loading {selectedPath}…
            </div>
          ) : activeBuffer?.unsupported ? (
            <div
              data-testid="firmware-unsupported-preview"
              style={{ padding: 24, color: t.textSec, fontSize: 13, lineHeight: 1.5 }}
            >
              <strong style={{ color: t.text }}>{selectedPath}</strong>
              <p>{activeBuffer.reason ?? 'This file cannot be previewed as text.'}</p>
            </div>
          ) : (
            <FirmwareMonacoEditor
              path={selectedPath}
              content={activeBuffer?.content ?? ''}
              isDark={isDark}
              onChange={onEditorChange}
              readOnly={leaseBlocked}
            />
          )}

          <FirmwareOutputPanel
            projectId={projectId}
            isDark={isDark}
            session={execSession}
            actor={actor}
            onClear={() => setExecSession(null)}
            onOpenFile={(path, line) => void openDiagnosticLocation(path, line)}
          />
        </section>
      </div>
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
