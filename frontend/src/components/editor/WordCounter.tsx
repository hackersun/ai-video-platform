'use client';

import { FileText, Clock, Type } from 'lucide-react';
import { cn } from '@/lib/utils';

interface WordCounterProps {
  content: string;
  className?: string;
}

interface Stats {
  characters: number;
  charactersNoSpaces: number;
  words: number;
  paragraphs: number;
  readingTime: number;
}

function stripHtml(html: string): string {
  if (typeof document !== 'undefined') {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || '';
  }
  return html.replace(/<[^>]*>/g, '');
}

function calculateStats(content: string): Stats {
  const text = stripHtml(content);
  
  const characters = text.length;
  const charactersNoSpaces = text.replace(/\s/g, '').length;
  
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  
  const paragraphs = text
    .split(/\n\s*\n/)
    .filter((p) => p.trim().length > 0).length || (text.trim() ? 1 : 0);
  
  const readingTime = Math.max(1, Math.ceil(words / 200));

  return {
    characters,
    charactersNoSpaces,
    words,
    paragraphs,
    readingTime,
  };
}

interface StatItemProps {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  unit?: string;
}

function StatItem({ icon, label, value, unit }: StatItemProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-400 dark:text-gray-500">
        {icon}
      </span>
      <span className="text-sm text-gray-600 dark:text-gray-400">
        {label}
      </span>
      <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">
        {value}
      </span>
      {unit && (
        <span className="text-xs text-gray-500">
          {unit}
        </span>
      )}
    </div>
  );
}

export function WordCounter({ content, className }: WordCounterProps) {
  const stats = calculateStats(content);

  return (
    <div className={cn('flex flex-wrap gap-4', className)}>
      <StatItem
        icon={<Type className="w-4 h-4" />}
        label="字数"
        value={stats.characters}
        unit="字符"
      />
      
      <StatItem
        icon={<FileText className="w-4 h-4" />}
        label="词数"
        value={stats.words}
        unit="词"
      />
      
      <StatItem
        icon={<Clock className="w-4 h-4" />}
        label="阅读时长"
        value={stats.readingTime}
        unit="分钟"
      />
    </div>
  );
}