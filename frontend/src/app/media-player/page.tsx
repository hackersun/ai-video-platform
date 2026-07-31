'use client';

import { ArrowLeft, Download, Loader2, RefreshCw } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useRef, useState } from 'react';

import { apiClient } from '@/lib/api-client';

type RefreshReason = 'initial' | 'manual' | 'auto';

function MediaPlayerContent() {
  const searchParams = useSearchParams();
  const jobId = searchParams.get('job_id') || '';
  const [playbackUrl, setPlaybackUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const autoRefreshAttempted = useRef(false);

  const refreshPlayback = useCallback(async (reason: RefreshReason = 'manual') => {
    if (!jobId) {
      setError('缺少成片任务编号，请返回工作台重新打开。');
      setLoading(false);
      return;
    }
    if (reason !== 'auto') {
      autoRefreshAttempted.current = false;
    }
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const result = await apiClient.getMediaPlaybackUrl(jobId);
      setPlaybackUrl(result.url);
      setNotice(reason === 'auto' ? '播放地址已自动刷新' : '播放地址已刷新');
    } catch (reason: any) {
      setPlaybackUrl('');
      setError(reason?.message || '播放地址刷新失败，请重试。');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    void refreshPlayback('initial');
  }, [refreshPlayback]);

  const handlePlaybackError = () => {
    if (autoRefreshAttempted.current) {
      setError('视频仍无法加载，请点击“刷新地址”重试；如仍失败，请检查存储配置。');
      return;
    }
    autoRefreshAttempted.current = true;
    void refreshPlayback('auto');
  };

  const handleDownload = async (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    if (!jobId || downloading) {
      return;
    }
    setDownloading(true);
    setError('');
    setNotice('正在准备下载…');
    try {
      const result = await apiClient.getMediaPlaybackUrl(jobId);
      const separator = result.url.includes('?') ? '&' : '?';
      const downloadUrl = result.delivery_method === 'local_static'
        ? `${result.url}${separator}_download=${Date.now()}`
        : result.url;
      const response = await fetch(downloadUrl, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`视频文件下载失败（HTTP ${response.status}）`);
      }
      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = `成片-${jobId}.mp4`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
      setPlaybackUrl(result.url);
      setNotice('下载已开始');
    } catch (reason: any) {
      setError(reason?.message || '下载失败，请刷新地址后重试。');
      setNotice('');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#05091a] px-4 py-6 text-white sm:px-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="mb-1 text-xs tracking-[0.2em] text-violet-300">AI 视频平台 · 成片交付</p>
            <h1 className="text-2xl font-semibold">成片播放</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => window.close()}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
            >
              <ArrowLeft className="h-4 w-4" /> 返回工作台
            </button>
            <button
              type="button"
              onClick={() => void refreshPlayback('manual')}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium hover:bg-violet-500 disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> 刷新地址
            </button>
          </div>
        </header>

        <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl">
          <div className="flex min-h-[60vh] items-center justify-center bg-black">
            {loading && (
              <div className="flex items-center gap-3 text-slate-300">
                <Loader2 className="h-5 w-5 animate-spin" /> 正在获取最新播放地址…
              </div>
            )}
            {!loading && error && (
              <div className="max-w-md px-6 text-center">
                <p className="mb-4 text-rose-300">{error}</p>
                <button
                  type="button"
                  onClick={() => void refreshPlayback('manual')}
                  className="rounded-lg border border-rose-400/50 px-4 py-2 text-sm text-rose-200 hover:bg-rose-500/10"
                >
                  修改配置后重试
                </button>
              </div>
            )}
            {!loading && playbackUrl && (
              <video
                data-testid="delivery-video"
                key={playbackUrl}
                src={playbackUrl}
                controls
                preload="none"
                playsInline
                className="max-h-[75vh] w-full bg-black object-contain"
                onError={handlePlaybackError}
              />
            )}
          </div>
          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 px-5 py-4 text-sm">
            <span className={error ? 'text-rose-300' : 'text-emerald-300'}>
              {error || notice || (playbackUrl ? '播放地址已刷新' : '等待播放地址')}
            </span>
            {playbackUrl && (
              <a
                href={playbackUrl}
                download
                onClick={handleDownload}
                aria-disabled={downloading}
                className="inline-flex items-center gap-2 text-violet-300 hover:text-violet-200"
              >
                {downloading
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : <Download className="h-4 w-4" />}
                下载成片
              </a>
            )}
          </footer>
        </section>
      </div>
    </main>
  );
}

export default function MediaPlayerPage() {
  return <Suspense fallback={<main className="min-h-screen bg-[#05091a] p-8 text-white">正在加载成片…</main>}>
    <MediaPlayerContent />
  </Suspense>;
}
