'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { legacyModelCenterHref } from '../navigation';
import type { ModelCenterSection } from '../types';

export function LegacyModelCenterRedirect({ section }: { section: ModelCenterSection }) {
  const router = useRouter();
  const params = useSearchParams();
  useEffect(() => { router.replace(legacyModelCenterHref(section, params)); }, [params, router, section]);
  return <div className="min-h-screen bg-slate-950 px-6 pt-28 text-center text-sm text-slate-400">正在打开模型中心…</div>;
}
