import { LegacyModelCenterRedirect } from '@/features/model-center/components/legacy-model-center-redirect';
import { Suspense } from 'react';

export default function ProductionAdaptersPage() {
  return <Suspense fallback={null}><LegacyModelCenterRedirect section="connections" /></Suspense>;
}
