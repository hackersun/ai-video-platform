'use client';

export type NotificationPreferences = {
  generationComplete: boolean;
  failedTasks: boolean;
  weeklySummary: boolean;
  browserNotifications: boolean;
  quietHours: boolean;
};

export type AppearancePreferences = {
  theme: 'dark' | 'light' | 'system';
  compactMode: boolean;
  reduceMotion: boolean;
  accentColor: 'violet' | 'cyan' | 'emerald' | 'amber';
  denseCards: boolean;
};

export const NOTIFICATION_PREFS_KEY = 'settings.notifications';
export const APPEARANCE_PREFS_KEY = 'settings.appearance';

export const defaultNotificationPreferences: NotificationPreferences = {
  generationComplete: true,
  failedTasks: true,
  weeklySummary: false,
  browserNotifications: false,
  quietHours: false,
};

export const defaultAppearancePreferences: AppearancePreferences = {
  theme: 'dark',
  compactMode: false,
  reduceMotion: false,
  accentColor: 'violet',
  denseCards: false,
};

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback;
  } catch {
    return fallback;
  }
}

function writeJson<T>(key: string, value: T) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(key, JSON.stringify(value));
  window.dispatchEvent(new CustomEvent('app-preferences-change'));
}

function currentUserId() {
  if (typeof window === 'undefined') return undefined;
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    return typeof user?.id === 'string' && user.id.trim() ? user.id.trim() : undefined;
  } catch {
    return undefined;
  }
}

function appearancePreferenceKey(userId = currentUserId()) {
  return userId ? `${APPEARANCE_PREFS_KEY}:${userId}` : APPEARANCE_PREFS_KEY;
}

export function getNotificationPreferences() {
  return readJson(NOTIFICATION_PREFS_KEY, defaultNotificationPreferences);
}

export function saveNotificationPreferences(value: NotificationPreferences) {
  writeJson(NOTIFICATION_PREFS_KEY, value);
}

export function getAppearancePreferences(userId?: string) {
  const scopedKey = appearancePreferenceKey(userId);
  const scoped = readJson(scopedKey, defaultAppearancePreferences);
  if (
    typeof window === 'undefined'
    || scopedKey === APPEARANCE_PREFS_KEY
    || localStorage.getItem(scopedKey)
  ) return scoped;
  return readJson(APPEARANCE_PREFS_KEY, defaultAppearancePreferences);
}

export function saveAppearancePreferences(value: AppearancePreferences, userId?: string) {
  writeJson(appearancePreferenceKey(userId), value);
}

export function applyAppearancePreferences(value: AppearancePreferences) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  const resolvedTheme = value.theme === 'system'
    ? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
    : value.theme;
  root.dataset.themePreference = value.theme;
  root.dataset.theme = resolvedTheme;
  root.style.colorScheme = resolvedTheme;
  root.dataset.accent = value.accentColor;
  root.dataset.compact = value.compactMode ? 'true' : 'false';
  root.dataset.denseCards = value.denseCards ? 'true' : 'false';
  root.dataset.reduceMotion = value.reduceMotion ? 'true' : 'false';
}
