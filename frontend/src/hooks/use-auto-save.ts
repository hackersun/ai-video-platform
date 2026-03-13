import { useState, useEffect, useCallback, useRef } from 'react';
import { novelApi } from '@/lib/api';

interface UseAutoSaveOptions {
  novelId: string;
  chapterId?: string;
  title?: string;
  content: string;
  autoSaveKey?: string;
  delay?: number;
  enabled?: boolean;
}

interface UseAutoSaveResult {
  isSaving: boolean;
  lastSaved: Date | null;
  error: Error | null;
  save: () => Promise<void>;
  content: string;
  setContent: (content: string) => void;
}

export function useAutoSave({
  novelId,
  chapterId,
  title,
  content,
  autoSaveKey,
  delay = 2000,
  enabled = true,
}: UseAutoSaveOptions): UseAutoSaveResult {
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [localContent, setLocalContent] = useState(content);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const initialContentRef = useRef(content);

  useEffect(() => {
    setLocalContent(content);
    initialContentRef.current = content;
  }, [content]);

  const save = useCallback(async () => {
    if (!enabled || !novelId) return;
    if (localContent === initialContentRef.current) return;

    setIsSaving(true);
    setError(null);

    try {
      await novelApi.saveDraft({
        novel_id: novelId,
        chapter_id: chapterId,
        title,
        content: localContent,
        auto_save_key: autoSaveKey,
      });

      initialContentRef.current = localContent;
      setLastSaved(new Date());
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Auto-save failed'));
    } finally {
      setIsSaving(false);
    }
  }, [novelId, chapterId, title, localContent, autoSaveKey, enabled]);

  useEffect(() => {
    if (!enabled || !novelId) return;

    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    if (localContent !== initialContentRef.current) {
      timerRef.current = setTimeout(() => {
        save();
      }, delay);
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [localContent, delay, enabled, novelId, save]);

  const handleSetContent = useCallback((newContent: string) => {
    setLocalContent(newContent);
  }, []);

  return {
    isSaving,
    lastSaved,
    error,
    save,
    content: localContent,
    setContent: handleSetContent,
  };
}

interface UseAutoSaveLocalOptions {
  key: string;
  delay?: number;
  enabled?: boolean;
}

interface UseAutoSaveLocalResult {
  isSaving: boolean;
  lastSaved: Date | null;
  error: Error | null;
  content: string;
  setContent: (content: string) => void;
  clearSaved: () => void;
}

export function useAutoSaveLocal({
  key,
  delay = 2000,
  enabled = true,
}: UseAutoSaveLocalOptions): UseAutoSaveLocalResult {
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [content, setContentState] = useState('');
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = localStorage.getItem(`autosave_${key}`);
    if (saved) {
      try {
        setContentState(JSON.parse(saved));
      } catch {
        setContentState('');
      }
    }
  }, [key]);

  const saveToLocal = useCallback((value: string) => {
    if (!enabled) return;

    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(() => {
      setIsSaving(true);
      try {
        localStorage.setItem(`autosave_${key}`, JSON.stringify(value));
        setLastSaved(new Date());
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Local save failed'));
      } finally {
        setIsSaving(false);
      }
    }, delay);
  }, [key, delay, enabled]);

  const setContent = useCallback((value: string) => {
    setContentState(value);
    saveToLocal(value);
  }, [saveToLocal]);

  const clearSaved = useCallback(() => {
    localStorage.removeItem(`autosave_${key}`);
    setContentState('');
    setLastSaved(null);
  }, [key]);

  return {
    isSaving,
    lastSaved,
    error,
    content,
    setContent,
    clearSaved,
  };
}