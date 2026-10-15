import { DiffEditor } from '@monaco-editor/react';
import { themeColors } from '../../lib/theme';
import { languageForPath } from '../firmware/language';

type Props = {
  path: string;
  original: string;
  modified: string;
  isDark: boolean;
};

/** Read-only Monaco diff preview for analysis patch operations. */
export function AnalysisDiffEditor({ path, original, modified, isDark }: Props) {
  const t = themeColors(isDark);
  return (
    <div
      data-testid="analysis-diff-host"
      data-path={path}
      style={{ flex: 1, minHeight: 180, background: t.bg }}
    >
      <DiffEditor
        original={original}
        modified={modified}
        language={languageForPath(path)}
        theme={isDark ? 'vs-dark' : 'light'}
        options={{
          readOnly: true,
          renderSideBySide: true,
          minimap: { enabled: false },
          fontSize: 12,
          scrollBeyondLastLine: false,
          wordWrap: 'on',
          automaticLayout: true,
        }}
        loading={
          <div style={{ padding: 12, color: t.textMuted, fontSize: 12 }}>Loading diff…</div>
        }
      />
    </div>
  );
}
