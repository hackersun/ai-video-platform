import { LegacyModelCenterRedirect } from '@/features/model-center/components/legacy-model-center-redirect';
import { Suspense } from 'react';

export default function PromptSkillsPage() {
  return <Suspense fallback={null}><LegacyModelCenterRedirect section="prompts" /></Suspense>;
}
