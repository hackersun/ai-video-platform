import Link from 'next/link';
import { CheckCircle2, ChevronRight } from 'lucide-react';

import { modelCenterSectionHref, type ModelCenterLocation } from '../navigation';

const steps = [
  { number: 1, title: '保存供应商账号', description: '填写 API Key，并给账号起一个容易识别的名称。', section: 'connections' as const },
  { number: 2, title: '添加模型', description: '选择用途、Model ID 和兼容适配器。', section: 'catalog' as const },
  { number: 3, title: '验证可用性', description: '先免费校验配置，再按需发起实模测试。', section: 'test-lab' as const },
  { number: 4, title: '设为默认模型', description: '指定文本、图片、视频和配音实际使用哪个模型。', section: 'bindings' as const },
];

export function ModelSetupGuide({ location }: { location: ModelCenterLocation }) {
  return <section className="rounded-lg border border-violet-400/20 bg-violet-500/[0.055] p-5 lg:col-span-2">
    <div className="flex items-center gap-2">
      <CheckCircle2 className="h-5 w-5 text-violet-300" />
      <h2 className="font-semibold text-white">四步完成模型接入</h2>
    </div>
    <p className="mt-1 text-sm text-slate-400">新增供应商或模型时按顺序完成；已有模型可直接到“默认模型”中切换。</p>
    <ol className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {steps.map((step) => <li key={step.number}>
        <Link href={modelCenterSectionHref(step.section, location)} className="group block rounded-lg border border-white/10 bg-slate-950/25 p-3 hover:border-violet-400/40 hover:bg-violet-500/[0.08]">
          <span className="flex items-center justify-between text-sm font-medium text-white">
            {step.number}. {step.title}<ChevronRight className="h-4 w-4 text-slate-500 group-hover:text-violet-300" />
          </span>
          <span className="mt-1 block text-xs leading-5 text-slate-400">{step.description}</span>
        </Link>
      </li>)}
    </ol>
  </section>;
}
