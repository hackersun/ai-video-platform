export function previousSelectedShotId(selected: string[], shotId: string): string | undefined {
  const index = selected.indexOf(shotId);
  return index > 0 ? selected[index - 1] : undefined;
}
