import type { StudioSnapshot } from '@/lib/studio-types';
import { STUDIO_QUICK_ACTIONS } from '@/lib/studio-quick-actions';

export type BoardItem = {
  actionId: string;
  href: string;
  label: string;
  value: string;
  meta?: string;
  ready: boolean;
  warning?: boolean;
  details?: string[];
  testId?: string;
};

export type BoardLane = {
  id: 'assets' | 'story' | 'shots' | 'review';
  title: string;
  items: BoardItem[];
};

function warningRows(snapshot: StudioSnapshot) {
  return (snapshot.shots || [])
    .filter((shot) => (shot.quality_report?.warnings || []).length > 0)
    .slice(0, 2)
    .map((shot) => `镜头 ${shot.shot_number || '-'} · ${shot.quality_report?.warnings?.[0]}`);
}

export function buildEpisodeBoard(snapshot: StudioSnapshot): BoardLane[] {
  const bible = snapshot.production_bible_summary;
  const counts = bible?.counts || {};
  const assets = snapshot.assets || {};
  const jobs = snapshot.jobs?.summary || {};
  const shots = snapshot.shots || [];
  const shotCount = snapshot.production?.shot_count || shots.length;
  const completedShots = shots.filter((shot) => shot.video_status === 'succeeded').length;
  const warnings = warningRows(snapshot);
  const qualityScores = shots.map((shot) => Number(shot.quality_report?.score)).filter(Number.isFinite);
  const averageScore = qualityScores.length ? Math.round(qualityScores.reduce((sum, score) => sum + score, 0) / qualityScores.length) : 0;
  const subtitleCount = snapshot.workflow?.metadata?.subtitle_track_ids?.length || 0;
  const assetCoverage = Math.round((snapshot.production?.asset_lock_coverage || 0) * 100);
  const entityCoverage = Math.round((snapshot.production?.entity_ref_coverage || 0) * 100);
  const consistencyScore = Math.round(snapshot.consistency_ledger?.overall_score || 0);
  const modelHint = snapshot.workflow?.latest_recommended_model_hint || '未记录推荐模型';

  return [
    {
      id: 'assets', title: '设定与资产',
      items: [
        { ...STUDIO_QUICK_ACTIONS.entities, value: `${counts.characters || 0} 个角色 · ${counts.props || 0} 个道具`, meta: bible?.story_bible_id ? 'Story Bible 已绑定' : 'Story Bible 待生成', ready: Boolean(bible?.story_bible_id) },
        { ...STUDIO_QUICK_ACTIONS.sceneAssets, value: `${counts.scenes || 0} 个场景 · ${bible?.asset_readiness?.asset_count || assets.total_count || 0} 项资产`, meta: bible?.asset_readiness?.ready ? '参考资产已就绪' : '仍有资产待补齐', ready: Boolean(bible?.asset_readiness?.ready) },
        { ...STUDIO_QUICK_ACTIONS.referenceLocks, value: `资产覆盖 ${assetCoverage}% · 实体引用 ${entityCoverage}%`, meta: `已锁 ${assets.locked_count || 0} / 总计 ${assets.total_count || 0}`, ready: assetCoverage >= 100 && entityCoverage >= 100 },
      ],
    },
    {
      id: 'story', title: '分镜与配音',
      items: [
        { ...STUDIO_QUICK_ACTIONS.storyboard, value: `${shotCount} 个镜头`, meta: snapshot.story_context?.script?.status ? `剧本状态 ${snapshot.story_context.script.status}` : '剧本状态未记录', ready: shotCount > 0 },
        { ...STUDIO_QUICK_ACTIONS.voices, value: `${jobs.tts_count || 0} 个 TTS 任务`, meta: `${bible?.voices?.length || 0} 个角色声线`, ready: (jobs.tts_count || 0) > 0 },
        { ...STUDIO_QUICK_ACTIONS.subtitles, value: `${subtitleCount} 条字幕轨`, meta: subtitleCount ? '可进入时间轴校对' : '尚未生成字幕', ready: subtitleCount > 0 },
      ],
    },
    {
      id: 'shots', title: '镜头生成',
      items: [
        { ...STUDIO_QUICK_ACTIONS.videoGeneration, label: `镜头生成（已完成 ${completedShots}/${shotCount}）`, value: `模型 ${modelHint}`, meta: `${jobs.video_count || 0} 个视频任务`, ready: completedShots === shotCount && shotCount > 0, warning: completedShots < shotCount, details: warnings, testId: 'studio-shot-generation-summary' },
        { ...STUDIO_QUICK_ACTIONS.shotReferences, value: warnings.length ? `${warnings.length} 个镜头示例待处理` : '当前没有镜头警告', meta: warnings.length ? '优先修复角色、场景与道具引用' : '参考证据完整', ready: !warnings.length, warning: warnings.length > 0 },
        { ...STUDIO_QUICK_ACTIONS.shotQuality, value: qualityScores.length ? `平均 ${averageScore} 分` : '尚未评分', meta: `${shots.filter((shot) => shot.quality_report?.status === 'ready').length} 个镜头可直接复审`, ready: averageScore >= 90 && !warnings.length },
      ],
    },
    {
      id: 'review', title: '复审与成片',
      items: [
        { ...STUDIO_QUICK_ACTIONS.continuityReview, value: `${consistencyScore} 分`, meta: `${snapshot.consistency_ledger?.findings?.length || 0} 个一致性发现`, ready: consistencyScore >= 80 },
        { ...STUDIO_QUICK_ACTIONS.timeline, href: `${STUDIO_QUICK_ACTIONS.timeline.href}&step=synthesis`, value: `${snapshot.timeline?.clip_count || 0} 个片段`, meta: snapshot.timeline?.preview_url ? '预览已生成' : '等待时间线同步', ready: (snapshot.timeline?.clip_count || 0) > 0 },
        { ...STUDIO_QUICK_ACTIONS.output, href: `${STUDIO_QUICK_ACTIONS.output.href}&step=export`, value: `${jobs.synthesis_count || 0} 个合成任务`, meta: snapshot.jobs?.synthesis_jobs?.some((job) => job.is_publishable) ? '存在可发布成片' : '尚无可发布成片', ready: snapshot.jobs?.synthesis_jobs?.some((job) => job.is_publishable) || false },
      ],
    },
  ];
}
