'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { BrainCircuit, Loader2, Settings } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { listPromptSkills, type PromptSkill } from '@/lib/prompt-skills-api';

export function PromptSkillPanel() {
  const [skills, setSkills] = useState<PromptSkill[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    listPromptSkills('shot_video', { active: true })
      .then((data) => {
        if (mounted) setSkills(data.items || []);
      })
      .catch(() => {
        if (mounted) setSkills([]);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const activeSkill = skills[0];

  return (
    <Card className="border-white/10 bg-white/5">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <CardTitle className="flex items-center gap-2 text-white">
            <BrainCircuit className="h-4 w-4 text-cyan-300" />
            当前激活 Prompt 技能
          </CardTitle>
          <Button asChild size="sm" variant="outline" className="border-white/20 text-white">
            <Link href="/prompt-skills">
              <Settings className="mr-2 h-4 w-4" />
              管理 Prompt 技能
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-white/55">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在读取激活技能…
          </div>
        ) : activeSkill ? (
          <div className="rounded-lg border border-cyan-400/20 bg-cyan-500/10 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="text-sm font-medium text-white">{activeSkill.name}</div>
              <Badge variant="outline" className="border-cyan-200/40 text-cyan-100">
                v{activeSkill.version || 1}
              </Badge>
              <Badge variant="outline" className="border-white/20 text-white/60">
                {activeSkill.task}
              </Badge>
            </div>
            <div className="mt-1 line-clamp-2 text-xs leading-5 text-white/60">
              {activeSkill.description || activeSkill.content || '当前任务会注入该技能片段。'}
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm text-white/55">
            暂无激活技能。生成仍会使用默认提示词，建议先在测试验证模式预览自定义技能。
          </div>
        )}
      </CardContent>
    </Card>
  );
}
