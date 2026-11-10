import { LegalDocument } from '@/features/legal/legal-document';
import { TERMS_OF_SERVICE } from '@/features/legal/legal-texts';

export default function TermsPage() {
  return <LegalDocument title="用户协议" sections={TERMS_OF_SERVICE} />;
}
