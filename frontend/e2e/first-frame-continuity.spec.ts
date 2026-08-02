import { expect, test } from '@playwright/test';

import { previousSelectedShotId } from '@/features/series-runs/first-frame-continuity';

test('later chapter first frames inherit only the immediately preceding selected shot', () => {
  const selected = ['chapter-1-shot', 'chapter-2-shot', 'chapter-3-shot'];

  expect(previousSelectedShotId(selected, 'chapter-1-shot')).toBeUndefined();
  expect(previousSelectedShotId(selected, 'chapter-2-shot')).toBe('chapter-1-shot');
  expect(previousSelectedShotId(selected, 'chapter-3-shot')).toBe('chapter-2-shot');
  expect(previousSelectedShotId(selected, 'foreign-shot')).toBeUndefined();
});
