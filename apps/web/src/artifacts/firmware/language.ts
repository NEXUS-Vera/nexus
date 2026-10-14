/** Monaco language ids for Firmware workspace text files. */

const EXTENSION_LANGUAGE: Record<string, string> = {
  c: 'c',
  h: 'c',
  cpp: 'cpp',
  cc: 'cpp',
  cxx: 'cpp',
  hpp: 'cpp',
  hh: 'cpp',
  ino: 'cpp',
  ini: 'ini',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  md: 'markdown',
  markdown: 'markdown',
  txt: 'plaintext',
  py: 'python',
  toml: 'ini',
  cmake: 'plaintext',
  ld: 'plaintext',
  s: 'plaintext',
  S: 'plaintext',
  asm: 'plaintext',
};

export function languageForPath(path: string): string {
  const base = path.split('/').pop() ?? path;
  const dot = base.lastIndexOf('.');
  if (dot <= 0 || dot === base.length - 1) {
    return 'plaintext';
  }
  const ext = base.slice(dot + 1).toLowerCase();
  return EXTENSION_LANGUAGE[ext] ?? 'plaintext';
}

/** Heuristic: treat as binary when UTF-8 decode fails or NUL bytes are present. */
export function isLikelyBinaryContent(bytesHint?: {
  encoding?: string;
  content?: string;
  contentBase64?: string;
}): boolean {
  if (!bytesHint) return false;
  if (bytesHint.encoding === 'base64' || bytesHint.contentBase64) {
    return true;
  }
  if (typeof bytesHint.content === 'string' && bytesHint.content.includes('\u0000')) {
    return true;
  }
  return false;
}
