export const fourChapterNovel = {
  id: 'novel-four-chapter-mist-harbor',
  title: '雾港铜铃',
  chapters: [
    { id: 'chapter-mist-harbor-01', chapterNumber: 1, title: '第一章 雾港来客', content: '沈砚穿着深蓝旧呢大衣抵达雾港。沈砚说：“我会查清失踪船队的去向。”' },
    { id: 'chapter-mist-harbor-02', chapterNumber: 2, title: '第二章 铜铃示警', content: '沈砚在旧码头发现一枚铜铃；铃声响起后，他转向北岸追查。' },
    { id: 'chapter-mist-harbor-03', chapterNumber: 3, title: '第三章 破损提灯', content: '仓库门前的提灯已经破损，沈砚由碎玻璃判断有人刚刚逃离。' },
    { id: 'chapter-mist-harbor-04', chapterNumber: 4, title: '第四章 北岬余波', content: '沈砚抵达北岬灯塔并敲响铜铃。沈砚说：“所有人立刻撤离灯塔。”灯塔平台坍塌，港口因此永久封航。' },
  ],
  entities: [
    { id: 'entity-character-shen-yan', type: 'character', name: '沈砚', expectedFirstEvidenceChapter: 1 },
    { id: 'entity-prop-blue-coat', type: 'prop', name: '深蓝旧呢大衣', expectedFirstEvidenceChapter: 1 },
    { id: 'entity-prop-copper-bell', type: 'prop', name: '铜铃', expectedFirstEvidenceChapter: 2 },
    { id: 'entity-prop-damaged-lantern', type: 'prop', name: '破损提灯', expectedFirstEvidenceChapter: 3 },
    { id: 'entity-location-north-cape-lighthouse', type: 'location', name: '北岬灯塔', expectedFirstEvidenceChapter: 4 },
  ],
  events: [
    { id: 'event-arrive-mist-harbor', name: '沈砚抵达雾港', expectedFirstEvidenceChapter: 1 },
    { id: 'event-bell-warning', name: '铜铃示警', expectedFirstEvidenceChapter: 2 },
    { id: 'event-lantern-damaged', name: '发现破损提灯', expectedFirstEvidenceChapter: 3 },
    { id: 'event-lighthouse-collapse', name: '灯塔平台坍塌并导致港口封航', expectedFirstEvidenceChapter: 4 },
  ],
} as const;

export const fourChapterApiContract = {
  workflows: [{ workflow_id: 'wf-four-chapter-current', title: '雾港铜铃 第二集', status: 'active' }],
  seriesPlan: {
    novel_id: fourChapterNovel.id,
    current_episode: { episode_index: 2, title: '第二集', chapter_ids: [fourChapterNovel.chapters[1].id] },
    episodes: fourChapterNovel.chapters.map((chapter) => ({
      episode_index: chapter.chapterNumber,
      title: `第${chapter.chapterNumber}集`,
      chapter_ids: [chapter.id],
      chapter_range: { start_number: chapter.chapterNumber, end_number: chapter.chapterNumber, label: String(chapter.chapterNumber) },
      status: 'planned',
      summary: chapter.content,
      carry_over_state: {
        characters: ['沈砚'],
        props: fourChapterNovel.entities
          .filter((entity) => entity.type === 'prop' && entity.expectedFirstEvidenceChapter <= chapter.chapterNumber)
          .map((entity) => entity.name),
        events: fourChapterNovel.events
          .filter((event) => event.expectedFirstEvidenceChapter <= chapter.chapterNumber)
          .map((event) => event.name),
      },
      workflow_id: chapter.chapterNumber === 2 ? 'wf-four-chapter-current' : null,
    })),
  },
  wholeBookGaps: {
    story_bible: null,
    story_state_machine: null,
    voice_locks: [],
    cross_episode_shot_selection: null,
  },
} as const;

export const syntheticVideoCatalog = {
  task: 'shot_video',
  display_name: '镜头视频生成',
  required_capabilities: ['video'],
  default_model_id: 'test.video-model-001',
  models: [{
    id: 'test.video-model-001',
    name: 'E2E Synthetic Video Model',
    name_cn: 'E2E 合成测试视频模型',
    display_name: 'E2E 合成测试视频模型',
    provider_id: 'test.synthetic-provider',
    provider_name: 'E2E Synthetic Provider',
    api_model_id: 'test.synthetic-video-v1',
    model_id: 'test.synthetic-video-v1',
    config_model_id: 'test.video-model-001',
    config_id: 'test.config-video-001',
    model_config_id: 'test.config-video-001',
    model_type: 'video-generation',
    model_capabilities: ['video'],
    capabilities: ['video'],
    desc: 'E2E synthetic fixture only',
    limits: { durations: [4, 5, 8, 10], resolutions: ['480p', '720p', '1080p'], reference_images: 1 },
    protocol: { input_mode: 'image_text' },
    lane: 'recommended',
    adapter_status: 'available',
    is_configured: true,
    is_default: true,
    test_status: 'success',
    key_available: true,
  }],
} as const;
