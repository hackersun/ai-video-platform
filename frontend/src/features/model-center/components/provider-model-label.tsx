export function ProviderModelLabel({
  providerName,
  providerCode,
}: {
  providerName: string;
  providerCode: string;
}) {
  return <span><span className="block text-slate-200">{providerName}</span><span className="block text-[11px] text-slate-500">{providerCode}</span></span>;
}
