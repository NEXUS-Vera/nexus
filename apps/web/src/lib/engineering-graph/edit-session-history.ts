/**
 * Bounded in-session undo/redo for Architecture workspace semantic drafts.
 * Layout mutations use a separate stack and must not mix with semantic history.
 */

export type HistoryEntry<T> = {
  label: string;
  content: T;
};

export class EditSessionHistory<T> {
  private past: HistoryEntry<T>[] = [];
  private future: HistoryEntry<T>[] = [];
  private current: HistoryEntry<T> | null = null;
  readonly maxEntries: number;

  constructor(maxEntries = 50) {
    this.maxEntries = maxEntries;
  }

  reset(content: T, label = 'baseline'): void {
    this.past = [];
    this.future = [];
    this.current = { label, content: structuredClone(content) };
  }

  getCurrent(): T | null {
    return this.current ? structuredClone(this.current.content) : null;
  }

  canUndo(): boolean {
    return this.past.length > 0;
  }

  canRedo(): boolean {
    return this.future.length > 0;
  }

  push(content: T, label: string): T {
    if (this.current) {
      this.past.push(this.current);
      if (this.past.length > this.maxEntries) this.past.shift();
    }
    this.future = [];
    this.current = { label, content: structuredClone(content) };
    return structuredClone(content);
  }

  undo(): T | null {
    if (!this.canUndo() || !this.current) return null;
    this.future.unshift(this.current);
    this.current = this.past.pop() ?? null;
    return this.getCurrent();
  }

  redo(): T | null {
    if (!this.canRedo()) return null;
    if (this.current) this.past.push(this.current);
    this.current = this.future.shift() ?? null;
    return this.getCurrent();
  }
}
