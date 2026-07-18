import { MainLayout } from '@/components/layout/main-layout';
import { Suspense } from 'react';
import { ModelCenterShell } from '@/features/model-center/components/model-center-shell';

export default function LLMConfigPage() {
  return <MainLayout wide><Suspense fallback={null}><ModelCenterShell /></Suspense></MainLayout>;
}
