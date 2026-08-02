'use client';

import { useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { applyAppearancePreferences, getAppearancePreferences } from '@/lib/user-preferences';

export function UserPreferencesHydrator() {
  const { user, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: light)');
    const applySavedPreferences = () => {
      applyAppearancePreferences(getAppearancePreferences(user?.id));
    };

    applySavedPreferences();
    window.addEventListener('app-preferences-change', applySavedPreferences);
    window.addEventListener('storage', applySavedPreferences);
    mediaQuery.addEventListener('change', applySavedPreferences);

    return () => {
      window.removeEventListener('app-preferences-change', applySavedPreferences);
      window.removeEventListener('storage', applySavedPreferences);
      mediaQuery.removeEventListener('change', applySavedPreferences);
    };
  }, [isLoading, user?.id]);

  return null;
}
