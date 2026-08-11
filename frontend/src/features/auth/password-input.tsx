'use client';

import { useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';
import { Input } from '@/components/ui/input';

interface PasswordInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function PasswordInput({ value, onChange }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div>
      <label htmlFor="password" className="mb-2 block text-sm font-medium text-foreground">密码</label>
      <div className="relative">
        <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <Input
          id="password"
          type={visible ? 'text' : 'password'}
          placeholder="请输入密码"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete="current-password"
          className="h-12 border-input bg-background pl-10 pr-11 text-foreground placeholder:text-muted-foreground focus-visible:ring-cyan-300"
        />
        <button
          type="button"
          aria-label={visible ? '隐藏输入内容' : '显示输入内容'}
          aria-pressed={visible}
          onClick={() => setVisible((current) => !current)}
          className="absolute right-1.5 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
        >
          {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>
    </div>
  );
}
