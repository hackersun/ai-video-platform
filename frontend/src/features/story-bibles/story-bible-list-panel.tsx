import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export type StoryBibleListItem = {
  id: string;
  novel_id?: string;
  title: string;
  character_rules?: unknown[];
  scene_rules?: unknown[];
  prop_rules?: unknown[];
  event_timeline?: unknown[];
  updated_at: string;
};

type NovelListItem = { id: string; title: string };

function contentCount(bible: StoryBibleListItem) {
  return (bible.character_rules?.length || 0)
    + (bible.scene_rules?.length || 0)
    + (bible.prop_rules?.length || 0)
    + (bible.event_timeline?.length || 0);
}

export function StoryBibleListPanel<T extends StoryBibleListItem>({
  items,
  novels,
  selectedId,
  contextualNovelId,
  onSelect,
  onGenerate,
}: {
  items: T[];
  novels: NovelListItem[];
  selectedId?: string;
  contextualNovelId?: string;
  onSelect: (bible: T) => void;
  onGenerate: () => void;
}) {
  const novelName = novels.find((novel) => novel.id === contextualNovelId)?.title;
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium uppercase tracking-wider text-white/60">
          {contextualNovelId ? '当前小说的 Story Bible' : '全部 Story Bible'}
        </h3>
        {contextualNovelId ? (
          <p className="mt-2 rounded-lg border border-violet-400/25 bg-violet-500/10 px-3 py-2 text-sm text-violet-100">
            正在处理《{novelName || '当前小说'}》
          </p>
        ) : null}
      </div>
      <div className="space-y-2">
        {items.length === 0 ? (
          <Card className="border-white/10 bg-white/5">
            <CardContent className="p-4 text-center">
              <p className="text-sm text-white/55">
                {contextualNovelId ? '当前小说还没有 Story Bible' : '还没有 Story Bible'}
              </p>
              <p className="mt-1 text-xs leading-5 text-white/40">
                从小说生成后，角色、场景、道具和事件会在这里统一维护。
              </p>
              <Button size="sm" variant="link" className="mt-2 text-violet-400" onClick={onGenerate}>
                为当前小说生成
              </Button>
            </CardContent>
          </Card>
        ) : items.map((bible) => {
          const total = contentCount(bible);
          const linkedNovel = novels.find((novel) => novel.id === bible.novel_id)?.title;
          return (
            <Card
              key={bible.id}
              className={`cursor-pointer border-white/10 bg-white/5 transition-colors hover:border-white/20 ${selectedId === bible.id ? 'border-violet-500 bg-violet-500/10' : ''}`}
              onClick={() => onSelect(bible)}
            >
              <CardContent className="space-y-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <h4 className="min-w-0 truncate font-medium text-white">{bible.title}</h4>
                  <Badge variant="outline" className={total ? 'border-emerald-400/30 text-emerald-300' : 'border-amber-400/30 text-amber-300'}>
                    {total ? '可使用' : '内容为空'}
                  </Badge>
                </div>
                <p className="text-xs text-white/50">
                  所属小说：{linkedNovel || (bible.novel_id ? '当前小说' : '未关联小说（历史记录）')}
                </p>
                <p className="text-xs text-white/45">
                  角色 {bible.character_rules?.length || 0} · 场景 {bible.scene_rules?.length || 0} · 道具 {bible.prop_rules?.length || 0} · 事件 {bible.event_timeline?.length || 0}
                </p>
                <p className="text-xs text-white/30">更新于 {new Date(bible.updated_at).toLocaleDateString('zh-CN')}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
