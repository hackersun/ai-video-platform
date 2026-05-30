'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import apiClient from '@/lib/api-client';

interface Version {
  id: string;
  user_id: string;
  resource_type: string;
  resource_id: string;
  version_number: number;
  version_label: string | null;
  change_summary: string | null;
  created_at: string;
  created_by: string | null;
}

interface VersionDetail extends Version {
  snapshot: Record<string, any>;
}

interface VersionDiff {
  version_id: string;
  version_number: number;
  prev_version_id: string | null;
  prev_version_number: number | null;
  diff: {
    added?: Record<string, any>;
    removed?: Record<string, any>;
    changed?: Record<string, { old: any; new: any }>;
    message?: string;
  };
  is_first?: boolean;
}

export default function VersionsPage() {
  const router = useRouter();
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<VersionDetail | null>(null);
  const [showVersionDetail, setShowVersionDetail] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [currentDiff, setCurrentDiff] = useState<VersionDiff | null>(null);
  const [rollbackConfirm, setRollbackConfirm] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // URL params
  const [resourceType, setResourceType] = useState<string>('novel');
  const [resourceId, setResourceId] = useState<string>('');

  useEffect(() => {
    // Parse URL params
    const params = new URLSearchParams(window.location.search);
    const rt = params.get('resource_type');
    const rid = params.get('resource_id');
    if (rt) setResourceType(rt);
    if (rid) setResourceId(rid);
  }, []);

  const fetchVersions = useCallback(async () => {
    if (!resourceId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getVersions(resourceType, resourceId);
      setVersions(data);
    } catch (err: any) {
      setError(err.message || '获取版本列表失败');
    } finally {
      setLoading(false);
    }
  }, [resourceType, resourceId]);

  useEffect(() => {
    if (resourceId) {
      fetchVersions();
    }
  }, [fetchVersions, resourceId]);

  const handleViewVersion = async (versionId: string) => {
    try {
      const detail = await apiClient.getVersionDetail(versionId) as VersionDetail;
      setSelectedVersion(detail);
      setShowVersionDetail(true);
    } catch (err: any) {
      alert('获取版本详情失败: ' + err.message);
    }
  };

  const handleCompare = async (versionId: string, compareWithCurrent: boolean = false) => {
    try {
      const diff = await apiClient.getVersionDiff(versionId, compareWithCurrent) as VersionDiff;
      setCurrentDiff(diff);
      setShowDiff(true);
    } catch (err: any) {
      alert('获取版本差异失败: ' + err.message);
    }
  };

  const handleRollback = async (versionId: string) => {
    if (!rollbackConfirm) {
      setRollbackConfirm(true);
      return;
    }

    setActionLoading(true);
    try {
      await apiClient.rollbackVersion(versionId, true);
      alert('回滚成功！');
      setRollbackConfirm(false);
      fetchVersions();
    } catch (err: any) {
      alert('回滚失败: ' + err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteVersion = async (versionId: string) => {
    if (!confirm('确定要删除这个版本吗？')) return;

    setActionLoading(true);
    try {
      await apiClient.deleteVersion(versionId);
      alert('版本已删除');
      fetchVersions();
    } catch (err: any) {
      alert('删除失败: ' + err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getResourceTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      novel: '小说',
      chapter: '章节',
      script: '剧本',
      storyboard: '分镜',
      shot: '镜头',
    };
    return labels[type] || type;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <div className="flex items-center">
            <button
              onClick={() => router.back()}
              className="mr-4 text-gray-500 hover:text-gray-700"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <h1 className="text-2xl font-bold text-gray-900">版本历史</h1>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-500">
              {getResourceTypeLabel(resourceType)}: {resourceId.slice(0, 8)}...
            </span>
            <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
              {versions.length} 个版本
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        {/* Filter Bar */}
        <div className="mb-6 bg-white rounded-lg shadow p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">资源类型</label>
              <select
                value={resourceType}
                onChange={(e) => setResourceType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="novel">小说</option>
                <option value="chapter">章节</option>
                <option value="script">剧本</option>
                <option value="storyboard">分镜</option>
                <option value="shot">镜头</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">资源ID</label>
              <input
                type="text"
                value={resourceId}
                onChange={(e) => setResourceId(e.target.value)}
                placeholder="输入资源ID"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <button
              onClick={fetchVersions}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              刷新
            </button>
          </div>
        </div>

        {/* Loading/Error States */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-2 text-gray-500">加载中...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {/* Version List */}
        {!loading && !error && versions.length === 0 && (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">暂无版本记录</h3>
            <p className="mt-1 text-sm text-gray-500">该资源还没有创建过版本。</p>
          </div>
        )}

        {!loading && !error && versions.length > 0 && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    版本号
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    标签
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    变更摘要
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    创建时间
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {versions.map((version, index) => (
                  <tr key={version.id} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        v{version.version_number}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {version.version_label || '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                      {version.change_summary || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(version.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end space-x-2">
                        <button
                          onClick={() => handleViewVersion(version.id)}
                          className="text-blue-600 hover:text-blue-900"
                        >
                          查看
                        </button>
                        {index > 0 && (
                          <button
                            onClick={() => handleCompare(version.id)}
                            className="text-gray-600 hover:text-gray-900"
                          >
                            比较
                          </button>
                        )}
                        <button
                          onClick={() => handleRollback(version.id)}
                          className={`${
                            rollbackConfirm && selectedVersion?.id === version.id
                              ? 'text-red-600 hover:text-red-900'
                              : 'text-green-600 hover:text-green-900'
                          }`}
                        >
                          {rollbackConfirm && selectedVersion?.id === version.id ? '确认回滚' : '回滚'}
                        </button>
                        <button
                          onClick={() => handleDeleteVersion(version.id)}
                          className="text-red-600 hover:text-red-900"
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {/* Version Detail Modal */}
      {showVersionDetail && selectedVersion && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
            <div className="px-6 py-4 border-b flex justify-between items-center">
              <h2 className="text-xl font-semibold">
                版本 v{selectedVersion.version_number}
                {selectedVersion.version_label && (
                  <span className="ml-2 text-gray-500">({selectedVersion.version_label})</span>
                )}
              </h2>
              <button
                onClick={() => {
                  setShowVersionDetail(false);
                  setSelectedVersion(null);
                  setRollbackConfirm(false);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-500">资源类型</label>
                  <p className="mt-1">{getResourceTypeLabel(selectedVersion.resource_type)}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500">资源ID</label>
                  <p className="mt-1 font-mono text-sm">{selectedVersion.resource_id}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500">创建时间</label>
                  <p className="mt-1">{formatDate(selectedVersion.created_at)}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500">创建者</label>
                  <p className="mt-1">{selectedVersion.created_by || '-'}</p>
                </div>
                {selectedVersion.change_summary && (
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-500">变更摘要</label>
                    <p className="mt-1">{selectedVersion.change_summary}</p>
                  </div>
                )}
              </div>

              <h3 className="text-lg font-medium mb-3">快照数据</h3>
              <pre className="bg-gray-100 rounded-lg p-4 overflow-x-auto text-sm">
                {JSON.stringify(selectedVersion.snapshot, null, 2)}
              </pre>
            </div>
            <div className="px-6 py-4 border-t bg-gray-50 flex justify-end space-x-3">
              <button
                onClick={() => handleCompare(selectedVersion!.id)}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-100"
              >
                与上一个版本比较
              </button>
              <button
                onClick={() => handleCompare(selectedVersion!.id, true)}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-100"
              >
                与当前版本比较
              </button>
              <button
                onClick={() => handleRollback(selectedVersion!.id)}
                className={`px-4 py-2 rounded-md text-white ${
                  rollbackConfirm
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-green-600 hover:bg-green-700'
                }`}
                disabled={actionLoading}
              >
                {rollbackConfirm ? '确认回滚' : '回滚到此版本'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Diff Modal */}
      {showDiff && currentDiff && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
            <div className="px-6 py-4 border-b flex justify-between items-center">
              <h2 className="text-xl font-semibold">
                版本 v{currentDiff.version_number} 差异
                {currentDiff.prev_version_number && (
                  <span className="ml-2 text-gray-500">vs v{currentDiff.prev_version_number}</span>
                )}
              </h2>
              <button
                onClick={() => {
                  setShowDiff(false);
                  setCurrentDiff(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
              {currentDiff.is_first ? (
                <div className="text-center py-8 text-gray-500">
                  这是第一个版本，无更早版本可比较
                </div>
              ) : currentDiff.diff.message ? (
                <div className="text-center py-8 text-gray-500">
                  {currentDiff.diff.message}
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Added */}
                  {currentDiff.diff.added && Object.keys(currentDiff.diff.added).length > 0 && (
                    <div>
                      <h3 className="text-green-600 font-medium mb-2">新增 (+)</h3>
                      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                        <pre className="text-sm overflow-x-auto">
                          {JSON.stringify(currentDiff.diff.added, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )}

                  {/* Removed */}
                  {currentDiff.diff.removed && Object.keys(currentDiff.diff.removed).length > 0 && (
                    <div>
                      <h3 className="text-red-600 font-medium mb-2">删除 (-)</h3>
                      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <pre className="text-sm overflow-x-auto">
                          {JSON.stringify(currentDiff.diff.removed, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )}

                  {/* Changed */}
                  {currentDiff.diff.changed && Object.keys(currentDiff.diff.changed).length > 0 && (
                    <div>
                      <h3 className="text-yellow-600 font-medium mb-2">变更 (~)</h3>
                      <div className="space-y-3">
                        {Object.entries(currentDiff.diff.changed).map(([key, value]) => (
                          <div key={key} className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                            <div className="font-medium mb-2">{key}</div>
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <div className="text-xs text-red-500 mb-1">旧值</div>
                                <pre className="text-sm bg-white p-2 rounded border border-red-200">
                                  {JSON.stringify(value.old, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <div className="text-xs text-green-500 mb-1">新值</div>
                                <pre className="text-sm bg-white p-2 rounded border border-green-200">
                                  {JSON.stringify(value.new, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="px-6 py-4 border-t bg-gray-50 flex justify-end">
              <button
                onClick={() => {
                  setShowDiff(false);
                  setCurrentDiff(null);
                }}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-100"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}