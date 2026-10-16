import { describe, expect, it } from 'vitest';
import { buildFileTree } from './file-tree';
import { isLikelyBinaryContent, languageForPath } from './language';

describe('firmware language mapping', () => {
  it('maps common firmware extensions', () => {
    expect(languageForPath('src/main.c')).toBe('c');
    expect(languageForPath('include/board.h')).toBe('c');
    expect(languageForPath('src/app.cpp')).toBe('cpp');
    expect(languageForPath('include/util.hpp')).toBe('cpp');
    expect(languageForPath('platformio.ini')).toBe('ini');
    expect(languageForPath('manifest.json')).toBe('json');
    expect(languageForPath('config.yaml')).toBe('yaml');
    expect(languageForPath('config.yml')).toBe('yaml');
    expect(languageForPath('README.md')).toBe('markdown');
    expect(languageForPath('notes.txt')).toBe('plaintext');
  });

  it('falls back to plaintext for unknown text extensions', () => {
    expect(languageForPath('linker.ld')).toBe('plaintext');
    expect(languageForPath('weird.foo')).toBe('plaintext');
    expect(languageForPath('Makefile')).toBe('plaintext');
  });

  it('treats base64 payloads as unsupported binary', () => {
    expect(isLikelyBinaryContent({ encoding: 'base64', contentBase64: 'AAAA' })).toBe(true);
    expect(isLikelyBinaryContent({ content: 'hello' })).toBe(false);
    expect(isLikelyBinaryContent({ content: 'a\u0000b' })).toBe(true);
  });
});

describe('firmware file tree', () => {
  it('renders nested folders and files', () => {
    const tree = buildFileTree([
      { path: 'src/main.cpp' },
      { path: 'src/util/helpers.cpp' },
      { path: 'include/board.h' },
      { path: 'README.md' },
    ]);
    expect(tree.map((n) => n.name)).toEqual(['include', 'src', 'README.md']);
    const src = tree.find((n) => n.name === 'src');
    expect(src?.kind).toBe('folder');
    expect(src?.children?.map((c) => c.name)).toEqual(['util', 'main.cpp']);
  });

  it('handles an empty workspace', () => {
    expect(buildFileTree([])).toEqual([]);
  });
});
