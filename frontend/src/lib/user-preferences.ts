'use client';

export type NotificationPreferences = {
  generationComplete: boolean;
  failedTasks: boolean;
  weeklySummary: boolean;
  browserNotifications: boolean;
  quietHours: boolean;
};

export type AppearancePreferences = {
  theme: 'dark';
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

export function getNotificationPreferences() {
  return readJson(NOTIFICATION_PREFS_KEY, defaultNotificationPreferences);
}

export function saveNotificationPreferences(value: NotificationPreferences) {
  writeJson(NOTIFICATION_PREFS_KEY, value);
}

export function getAppearancePreferences() {
  return readJson(APPEARANCE_PREFS_KEY, defaultAppearancePreferences);
}

export function saveAppearancePreferences(value: AppearancePreferences) {
  writeJson(APPEARANCE_PREFS_KEY, value);
}

export function applyAppearancePreferences(value: AppearancePreferences) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.dataset.accent = value.accentColor;
  root.dataset.compact = value.compactMode ? 'true' : 'false';
  root.dataset.denseCards = value.denseCards ? 'true' : 'false';
  root.dataset.reduceMotion = value.reduceMotion ? 'true' : 'false';
}
