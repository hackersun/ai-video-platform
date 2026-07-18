import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import { useModelCenterQuery } from './use-model-center-query';

export function usePromptProfileDetail(profileId?: string) {
  const request = useCallback(
    () => profileId
      ? modelCenterApi.getPromptProfile(profileId)
      : Promise.reject(new Error('请先选择提示词模板')),
    [profileId],
  );
  return useModelCenterQuery(`prompt-profile:${profileId || 'none'}`, request);
}
