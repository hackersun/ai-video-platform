'use client';

import { useEffect, useState } from 'react';

type StoryBibleRequestContext = {
  ready: boolean;
  novelId: string;
  createRequested: boolean;
};

export function useStoryBibleRequestContext(): StoryBibleRequestContext {
  const [context, setContext] = useState<StoryBibleRequestContext>({
    ready: false,
    novelId: '',
    createRequested: false,
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setContext({
      ready: true,
      novelId: params.get('novel_id')?.trim() || '',
      createRequested: params.get('action') === 'create',
    });
  }, []);

  return context;
}
