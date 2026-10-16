import Editor from '@monaco-editor/react';
import { themeColors } from '../../lib/theme';
import { languageForPath } from '../firmware/language';

type Props = {
  path: string;
  content: string;
  readOnly?: boolean;
  isDark: boolean;
  onChange: (value: string) => void;
};

/** Presentation-only Monaco wrapper for Analysis text editing. */
export function AnalysisMonacoEditor({
  path,
  content,
  readOnly = false,
  isDark,
  onChange,
}: Props) {
  const t = themeColors(isDark);
  return (
    <div
      data-testid="analysis-monaco-host"
      data-path={path}
      style={{ flex: 1, minHeight: 0, background: t.bg }}
    >
      <Editor
        path={path}
        language={languageForPath(path)}
        value={content}
        theme={isDark ? 'vs-dark' : 'light'}
        onChange={(value) => onChange(value ?? '')}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          wordWrap: 'on',
          automaticLayout: true,
          tabSize: 2,
          renderWhitespace: 'selection',
        }}
        loading={
          <div
            data-testid="analysis-monaco-loading"
            style={{ padding: 16, color: t.textMuted, fontSize: 13 }}
          >
            Loading editor…
          </div>
        }
      />
    </div>
  );
}

