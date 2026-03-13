import { CharacterAttributes } from "@/components/characters/CharacterAttributesPanel";

export interface HighlightConfig {
  characterId: string;
  name: string;
  aliases?: string[];
  color: string;
  textColor?: string;
}

export interface HighlightedSegment {
  text: string;
  isHighlighted: boolean;
  characterId?: string;
  characterName?: string;
}

export function createHighlightConfig(
  attributes: Partial<CharacterAttributes>,
  characterId: string
): HighlightConfig {
  const config: HighlightConfig = {
    characterId,
    name: attributes.name || "",
    color: attributes.theme_color || "#8b5cf6",
  };

  if (attributes.personality) {
    const nicknameMatch = attributes.personality.match(/(?:外号|绰号|昵称)[是为：:]\s*["']?([^"'，,\n]+)/);
    if (nicknameMatch) {
      config.aliases = [nicknameMatch[1].trim()];
    }
  }

  return config;
}

function buildCharacterPattern(config: HighlightConfig): RegExp {
  const names = [config.name, ...(config.aliases || [])]
    .filter(Boolean)
    .map((name) => escapeRegex(name))
    .join("|");

  return new RegExp(`([，。、！？：；""''【】《》（）]*)(${names})([，。、！？：；""''【】《》（）]*)`, "gi");
}

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function highlightCharacter(
  text: string,
  config: HighlightConfig
): HighlightedSegment[] {
  if (!config.name) return [{ text, isHighlighted: false }];

  const pattern = buildCharacterPattern(config);
  const segments: HighlightedSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({
        text: text.slice(lastIndex, match.index),
        isHighlighted: false,
      });
    }

    const prefix = match[1];
    const charName = match[2];
    const suffix = match[3];

    if (prefix) {
      segments.push({ text: prefix, isHighlighted: false });
    }

    segments.push({
      text: charName,
      isHighlighted: true,
      characterId: config.characterId,
      characterName: config.name,
    });

    if (suffix) {
      segments.push({ text: suffix, isHighlighted: false });
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    segments.push({
      text: text.slice(lastIndex),
      isHighlighted: false,
    });
  }

  return segments.length > 0 ? segments : [{ text, isHighlighted: false }];
}

export function highlightCharacters(
  text: string,
  configs: HighlightConfig[]
): HighlightedSegment[] {
  if (configs.length === 0 || !text) {
    return [{ text, isHighlighted: false }];
  }

  const patterns = configs
    .filter((c) => c.name)
    .map((c) => {
      const names = [c.name, ...(c.aliases || [])]
        .filter(Boolean)
        .map((name) => escapeRegex(name))
        .join("|");
      return { pattern: new RegExp(`(${names})`, "gi"), config: c };
    });

  if (patterns.length === 0) {
    return [{ text, isHighlighted: false }];
  }

  type Match = {
    start: number;
    end: number;
    text: string;
    config: HighlightConfig;
  };

  const allMatches: Match[] = [];

  for (const { pattern, config } of patterns) {
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(text)) !== null) {
      allMatches.push({
        start: match.index,
        end: match.index + match[0].length,
        text: match[0],
        config,
      });
    }
  }

  allMatches.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return b.end - a.end;
  });

  const uniqueMatches: Match[] = [];
  for (const match of allMatches) {
    const hasOverlap = uniqueMatches.some(
      (existing) =>
        (match.start >= existing.start && match.start < existing.end) ||
        (match.end > existing.start && match.end <= existing.end)
    );
    if (!hasOverlap) {
      uniqueMatches.push(match);
    }
  }

  const segments: HighlightedSegment[] = [];
  let lastIndex = 0;

  for (const match of uniqueMatches) {
    if (match.start > lastIndex) {
      segments.push({
        text: text.slice(lastIndex, match.start),
        isHighlighted: false,
      });
    }

    segments.push({
      text: match.text,
      isHighlighted: true,
      characterId: match.config.characterId,
      characterName: match.config.name,
    });

    lastIndex = match.end;
  }

  if (lastIndex < text.length) {
    segments.push({
      text: text.slice(lastIndex),
      isHighlighted: false,
    });
  }

  return segments.length > 0 ? segments : [{ text, isHighlighted: false }];
}

export function highlightToHTML(
  text: string,
  configs: HighlightConfig[],
  options: {
    tagName?: string;
    className?: string;
  } = {}
): string {
  const { tagName = "span", className = "character-highlight" } = options;
  const segments = highlightCharacters(text, configs);

  return segments
    .map((segment) => {
      if (!segment.isHighlighted) {
        return segment.text;
      }
      const config = configs.find((c) => c.characterId === segment.characterId);
      const bgColor = config?.color || "#8b5cf6";
      const txtColor = config?.textColor || "#ffffff";
      return `<${tagName} class="${className}" data-character-id="${segment.characterId}" style="background-color: ${bgColor}; color: ${txtColor}; padding: 1px 4px; border-radius: 3px;">${segment.text}</${tagName}>`;
    })
    .join("");
}

export function countMentions(
  text: string,
  configs: HighlightConfig[]
): Record<string, number> {
  const counts: Record<string, number> = {};

  for (const config of configs) {
    if (!config.name) continue;
    const pattern = buildCharacterPattern(config);
    const matches = text.match(pattern);
    counts[config.characterId] = matches ? matches.length : 0;
  }

  return counts;
}

export interface MentionWithContext {
  characterId: string;
  characterName: string;
  position: number;
  text: string;
  contextBefore: string;
  contextAfter: string;
}

export function findMentionsWithContext(
  text: string,
  configs: HighlightConfig[],
  contextLength = 30
): MentionWithContext[] {
  const mentions: MentionWithContext[] = [];

  for (const config of configs) {
    if (!config.name) continue;
    const pattern = buildCharacterPattern(config);
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(text)) !== null) {
      const start = Math.max(0, match.index - contextLength);
      const end = Math.min(text.length, match.index + match[0].length + contextLength);

      mentions.push({
        characterId: config.characterId,
        characterName: config.name,
        position: match.index,
        text: match[0],
        contextBefore: text.slice(start, match.index),
        contextAfter: text.slice(match.index + match[0].length, end),
      });
    }
  }

  return mentions.sort((a, b) => a.position - b.position);
}

export interface LegendItem {
  characterId: string;
  name: string;
  color: string;
  mentionCount: number;
}

export function generateLegend(
  text: string,
  configs: HighlightConfig[]
): LegendItem[] {
  const counts = countMentions(text, configs);

  return configs
    .filter((config) => config.name && counts[config.characterId] > 0)
    .map((config) => ({
      characterId: config.characterId,
      name: config.name,
      color: config.color,
      mentionCount: counts[config.characterId],
    }))
    .sort((a, b) => b.mentionCount - a.mentionCount);
}