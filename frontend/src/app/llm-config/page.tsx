'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { MainLayout } from '@/components/layout/main-layout';
import { ModelCenterShell } from '@/features/model-center/components/model-center-shell';
import { SimpleModelSetup } from '@/features/model-settings/simple-model-setup';

function LLMConfigContent() {
  const searchParams = useSearchParams();
  // 默认进入「模型设置」简易视图；带 section 参数（高级设置、旧链接）进入完整模型中心。
  if (!searchParams.get('section')) return <SimpleModelSetup />;
  return <ModelCenterShell />;
}

export default function LLMConfigPage() {
  return <MainLayout wide><Suspense fallback={null}><LLMConfigContent /></Suspense></MainLayout>;
}
