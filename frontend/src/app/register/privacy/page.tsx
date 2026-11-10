import { LegalDocument } from '@/features/legal/legal-document';
import { PRIVACY_POLICY } from '@/features/legal/legal-texts';

export default function PrivacyPage() {
  return <LegalDocument title="隐私政策" sections={PRIVACY_POLICY} />;
}
