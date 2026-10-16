import { describe, expect, it } from 'vitest';
import { EditSessionHistory } from './edit-session-history';

describe('EditSessionHistory', () => {
  it('supports undo/redo of semantic content snapshots', () => {
    const history = new EditSessionHistory<{ name: string }>();
    history.reset({ name: 'a' });
    history.push({ name: 'b' }, 'rename');
    history.push({ name: 'c' }, 'rename');
    expect(history.getCurrent()).toEqual({ name: 'c' });
    expect(history.undo()).toEqual({ name: 'b' });
    expect(history.undo()).toEqual({ name: 'a' });
    expect(history.canUndo()).toBe(false);
    expect(history.redo()).toEqual({ name: 'b' });
    expect(history.redo()).toEqual({ name: 'c' });
    expect(history.canRedo()).toBe(false);
  });

  it('clears redo stack on new push after undo', () => {
    const history = new EditSessionHistory<{ n: number }>();
    history.reset({ n: 1 });
    history.push({ n: 2 }, 'edit');
    history.undo();
    history.push({ n: 3 }, 'edit');
    expect(history.canRedo()).toBe(false);
    expect(history.getCurrent()).toEqual({ n: 3 });
  });

  it('bounds history length', () => {
    const history = new EditSessionHistory<{ n: number }>(3);
    history.reset({ n: 0 });
    history.push({ n: 1 }, '1');
    history.push({ n: 2 }, '2');
    history.push({ n: 3 }, '3');
    history.push({ n: 4 }, '4');
    // past retains last 3 baselines behind current → undo thrice max to n=1
    expect(history.undo()?.n).toBe(3);
    expect(history.undo()?.n).toBe(2);
    expect(history.undo()?.n).toBe(1);
    expect(history.canUndo()).toBe(false);
  });
});
