import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface CharacterHighlightOptions {
  highlightColor?: string;
  highlightBgColor?: string;
  highlightClass?: string;
  caseSensitive?: boolean;
}

interface HighlightMatch {
  name: string;
  characterId: string;
  start: number;
  end: number;
}

export function findCharacterMentions(
  text: string,
  characters: { id: string; name: string }[],
  options: CharacterHighlightOptions = {}
): HighlightMatch[] {
  const { caseSensitive = false } = options;
  const matches: HighlightMatch[] = [];
  const searchText = caseSensitive ? text : text.toLowerCase();

  for (const char of characters) {
    if (!char.name) continue;
    
    const searchName = caseSensitive ? char.name : char.name.toLowerCase();
    let start = 0;
    
    while ((start = searchText.indexOf(searchName, start)) !== -1) {
      matches.push({
        name: char.name,
        characterId: char.id,
        start,
        end: start + char.name.length,
      });
      start += char.name.length;
    }
  }

  return matches.sort((a, b) => a.start - b.start);
}

export function highlightCharacters(
  text: string,
  characters: { id: string; name: string }[],
  options: CharacterHighlightOptions = {}
): { before: string; characterId: string; name: string; after: string }[] {
  const matches = findCharacterMentions(text, characters, options);
  const result: { before: string; characterId: string; name: string; after: string }[] = [];
  
  let lastEnd = 0;
  
  for (const match of matches) {
    if (match.start > lastEnd) {
      result.push({
        before: text.slice(lastEnd, match.start),
        characterId: match.characterId,
        name: match.name,
        after: "",
      });
    } else if (result.length > 0) {
      const last = result[result.length - 1];
      last.after = text.slice(lastEnd, match.end);
      continue;
    }
    
    result.push({
      before: text.slice(lastEnd, match.start),
      characterId: match.characterId,
      name: match.name,
      after: "",
    });
    
    lastEnd = match.end;
  }
  
  if (lastEnd < text.length) {
    if (result.length > 0) {
      result[result.length - 1].after = text.slice(lastEnd);
    } else {
      result.push({
        before: text,
        characterId: "",
        name: "",
        after: "",
      });
    }
  }
  
  return result;
}

export function renderHighlightedText(
  text: string,
  characters: { id: string; name: string }[],
  options: CharacterHighlightOptions = {}
): ReactNode {
  const { highlightBgColor = "#8b5cf6", highlightClass } = options;
  const parts = highlightCharacters(text, characters, options);
  
  return (
    <>
      {parts.map((part, index) => {
        if (!part.characterId) {
          return <span key={index}>{part.before}{part.after}</span>;
        }
        
        return (
          <span key={index}>
            {part.before}
            <span
              className={cn(
                "px-1.5 py-0.5 rounded font-medium cursor-pointer transition-colors",
                highlightClass
              )}
              style={{ 
                backgroundColor: `${highlightBgColor}30`,
                color: highlightBgColor,
              }}
              data-character-id={part.characterId}
            >
              {part.name}
            </span>
            {part.after}
          </span>
        );
      })}
    </>
  );
}

export function getCharacterPresence(
  text: string,
  characters: { id: string; name: string }[]
): { characterId: string; name: string; count: number }[] {
  const matches = findCharacterMentions(text, characters);
  const counts = new Map<string, { name: string; count: number }>();
  
  for (const match of matches) {
    const existing = counts.get(match.characterId);
    if (existing) {
      existing.count++;
    } else {
      counts.set(match.characterId, { name: match.name, count: 1 });
    }
  }
  
  return Array.from(counts.entries()).map(([id, data]) => ({
    characterId: id,
    name: data.name,
    count: data.count,
  })).sort((a, b) => b.count - a.count);
}

export function createCharacterNameMap(
  characters: { id: string; name: string; aliases?: string[] }[]
): Map<string, string> {
  const map = new Map<string, string>();
  
  for (const char of characters) {
    if (char.name) {
      map.set(char.name.toLowerCase(), char.id);
    }
    if (char.aliases) {
      for (const alias of char.aliases) {
        map.set(alias.toLowerCase(), char.id);
      }
    }
  }
  
  return map;
}