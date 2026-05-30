'use client';

import { useEffect } from 'react';
import { applyAppearancePreferences, getAppearancePreferences } from '@/lib/user-preferences';

export function UserPreferencesHydrator() {
  useEffect(() => {
    const applySavedPreferences = () => {
      applyAppearancePreferences(getAppearancePreferences());
    };

    applySavedPreferences();
    window.addEventListener('app-preferences-change', applySavedPreferences);
    window.addEventListener('storage', applySavedPreferences);

    return () => {
      window.removeEventListener('app-preferences-change', applySavedPreferences);
      window.removeEventListener('storage', applySavedPreferences);
    };
  }, []);

  return null;
}
