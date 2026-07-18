import type { ModelCapability, ModelCenterSection } from './types';

export type ModelCenterLocation = {
  section?: ModelCenterSection;
  capability?: ModelCapability;
  runId?: string;
  returnTo?: string;
};

const sections = new Set<ModelCenterSection>([
  'overview', 'connections', 'catalog', 'bindings', 'recipes', 'prompts', 'test-lab',
]);

const capabilities = new Set<ModelCapability>([
  'text_generation', 'vision_analysis', 'image_generation', 'speech_generation',
  'video_generation', 'subtitle_generation', 'media_render', 'object_storage',
]);

function safeReturnTo(value?: string) {
  return value?.startsWith('/') && !value.startsWith('//') ? value : undefined;
}

export function modelCenterHref(location: ModelCenterLocation = {}) {
  const params = new URLSearchParams();
  params.set('section', location.section && sections.has(location.section) ? location.section : 'overview');
  if (location.capability && capabilities.has(location.capability)) params.set('capability', location.capability);
  if (location.runId) params.set('runId', location.runId);
  const returnTo = safeReturnTo(location.returnTo);
  if (returnTo) params.set('returnTo', returnTo);
  return `/llm-config?${params.toString()}`;
}

export function modelCenterSectionHref(section: ModelCenterSection, location: Omit<ModelCenterLocation, 'section'> = {}) {
  return modelCenterHref({ ...location, section });
}

type SearchParamsLike = Pick<URLSearchParams, 'get'>;

export function legacyModelCenterHref(section: ModelCenterSection, params: SearchParamsLike) {
  const legacyCapability: Record<string, ModelCapability> = {
    text: 'text_generation', image: 'image_generation', video: 'video_generation', audio: 'speech_generation',
  };
  const rawCapability = params.get('capability') || '';
  return modelCenterHref({
    section,
    capability: legacyCapability[rawCapability] || (capabilities.has(rawCapability as ModelCapability) ? rawCapability as ModelCapability : undefined),
    runId: params.get('runId') || undefined,
    returnTo: params.get('returnTo') || undefined,
  });
}

export function readModelCenterLocation(params: SearchParamsLike): Required<Pick<ModelCenterLocation, 'section'>> & Omit<ModelCenterLocation, 'section'> {
  const section = params.get('section');
  const capability = params.get('capability');
  return {
    section: section && sections.has(section as ModelCenterSection) ? section as ModelCenterSection : 'overview',
    capability: capability && capabilities.has(capability as ModelCapability) ? capability as ModelCapability : undefined,
    runId: params.get('runId') || undefined,
    returnTo: safeReturnTo(params.get('returnTo') || undefined),
  };
}
