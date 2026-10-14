import { describe, expect, it } from 'vitest';
import { parseCompilerDiagnostics } from './diagnostics';

describe('parseCompilerDiagnostics', () => {
  it('extracts gcc-style error lines', () => {
    const text = 'src/main.cpp:4:5: error: expected \';\' before \'}\'\n';
    const items = parseCompilerDiagnostics(text);
    expect(items).toHaveLength(1);
    expect(items[0].path).toBe('src/main.cpp');
    expect(items[0].line).toBe(4);
    expect(items[0].severity).toBe('error');
  });
});
