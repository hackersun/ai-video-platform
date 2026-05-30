'use client';

import { useEffect, useState } from 'react';
import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/toast';
import { apiClient } from '@/lib/api-client';
import { AlertCircle, Crown, Loader2, Mail, Plus, RefreshCw, Trash2, Users } from 'lucide-react';

interface Project {
  id: string;
  name: string;
  status: string;
}

interface ProjectMember {
  id: string;
  project_id: string;
  user_id: string;
  role: string;
  is_active: boolean;
  joined_at?: string;
}

const roleLabel = (role: string) => {
  if (role === 'owner') return '所有者';
  if (role === 'editor') return '编辑';
  return '查看者';
};

export default function TeamsPage() {
  const { toast } = useToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [memberUserId, setMemberUserId] = useState('');
  const [role, setRole] = useState('editor');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<ProjectMember | null>(null);
  const [removingMemberId, setRemovingMemberId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const selectedProject = projects.find((project) => project.id === selectedProjectId);

  const loadProjects = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const data = await apiClient.getProjects();
      setProjects(Array.isArray(data) ? data : []);
      const nextProjectId = selectedProjectId || data?.[0]?.id || '';
      setSelectedProjectId(nextProjectId);
      if (nextProjectId) {
        const memberData = await apiClient.getProjectMembers(nextProjectId);
        setMembers(Array.isArray(memberData) ? memberData : []);
      } else {
        setMembers([]);
      }
    } catch (err: any) {
      setMessage(err?.message || '项目成员加载失败');
      setMembers([]);
    } finally {
      setLoading(false);
    }
  };

  const loadMembers = async (projectId: string) => {
    setSelectedProjectId(projectId);
    setMessage(null);
    try {
      const memberData = await apiClient.getProjectMembers(projectId);
      setMembers(Array.isArray(memberData) ? memberData : []);
    } catch (err: any) {
      setMessage(err?.message || '成员加载失败');
      setMembers([]);
    }
  };

  const inviteMember = async () => {
    if (!selectedProjectId || !memberUserId.trim()) return;

    setSaving(true);
    setMessage(null);
    try {
      await apiClient.createProjectMember(selectedProjectId, { user_id: memberUserId.trim(), role });
      setMemberUserId('');
      await loadMembers(selectedProjectId);
      setMessage('成员已添加');
      toast({ title: '成员已添加', type: 'success' });
    } catch (err: any) {
      setMessage(err?.message || '成员添加失败');
      toast({ title: '成员添加失败', description: err?.message || '请检查用户 ID 和项目权限。', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const updateRole = async (member: ProjectMember, nextRole: string) => {
    setMessage(null);
    try {
      await apiClient.updateProjectMember(selectedProjectId, member.user_id, { role: nextRole });
      await loadMembers(selectedProjectId);
      toast({ title: '成员角色已更新', type: 'success' });
    } catch (err: any) {
      setMessage(err?.message || '角色更新失败');
      toast({ title: '角色更新失败', description: err?.message || '请稍后重试。', type: 'error' });
    }
  };

  const removeMember = async (member: ProjectMember) => {
    setRemovingMemberId(member.user_id);
    setMessage(null);
    try {
      await apiClient.deleteProjectMember(selectedProjectId, member.user_id);
      await loadMembers(selectedProjectId);
      toast({ title: '成员已移除', type: 'success' });
    } catch (err: any) {
      setMessage(err?.message || '成员移除失败');
      toast({ title: '成员移除失败', description: err?.message || '请稍后重试。', type: 'error' });
    } finally {
      setRemovingMemberId(null);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">团队管理</h1>
            <p className="text-white/60 mt-1">按项目管理成员和权限</p>
          </div>
          <Button variant="outline" onClick={loadProjects} className="border-white/20">
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新
          </Button>
        </div>

        {message && (
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 flex items-center gap-3 text-white/70">
              <AlertCircle className="w-5 h-5 text-yellow-400" />
              {message}
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="text-3xl font-bold text-white">{projects.length}</div>
              <div className="text-white/60">可管理项目</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="text-3xl font-bold text-white">{members.length}</div>
              <div className="text-white/60">当前项目成员</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="text-3xl font-bold text-white">{members.filter((member) => member.role === 'editor').length}</div>
              <div className="text-white/60">编辑</div>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Users className="w-5 h-5 text-violet-400" />
              项目成员
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-[240px_1fr_140px_auto] gap-3">
              <select
                value={selectedProjectId}
                onChange={(event) => loadMembers(event.target.value)}
                className="px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white"
              >
                <option value="">选择项目</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
              <Input
                value={memberUserId}
                onChange={(event) => setMemberUserId(event.target.value)}
                placeholder="成员用户ID"
                className="bg-white/10 border-white/20 text-white"
              />
              <select
                value={role}
                onChange={(event) => setRole(event.target.value)}
                className="px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white"
              >
                <option value="editor">编辑</option>
                <option value="viewer">查看者</option>
              </select>
              <Button
                onClick={inviteMember}
                disabled={saving || !selectedProjectId || !memberUserId.trim()}
                className="bg-violet-600 hover:bg-violet-700"
              >
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
                添加成员
              </Button>
            </div>

            {loading ? (
              <div className="py-10 text-center text-white/50">
                <Loader2 className="w-8 h-8 mx-auto mb-2 animate-spin" />
                加载中…
              </div>
            ) : !selectedProject ? (
              <div className="py-10 text-center text-white/40">暂无项目</div>
            ) : members.length === 0 ? (
              <div className="py-10 text-center text-white/40">当前项目暂无成员</div>
            ) : (
              <div className="space-y-3">
                {members.map((member) => (
                  <div key={member.id} className="flex items-center gap-4 p-4 rounded-lg bg-white/5">
                    <div className="w-10 h-10 rounded-full bg-violet-600 flex items-center justify-center text-white font-medium">
                      {member.user_id.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium truncate">{member.user_id}</span>
                        {member.role === 'owner' && <Crown className="w-4 h-4 text-yellow-400" />}
                      </div>
                      <div className="flex items-center gap-2 text-white/60 text-sm">
                        <Mail className="w-3 h-3" />
                        加入时间：{member.joined_at ? new Date(member.joined_at).toLocaleDateString() : '未知'}
                      </div>
                    </div>
                    <select
                      value={member.role}
                      disabled={member.role === 'owner'}
                      onChange={(event) => updateRole(member, event.target.value)}
                      className="px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white disabled:opacity-60"
                    >
                      <option value="owner">{roleLabel('owner')}</option>
                      <option value="editor">{roleLabel('editor')}</option>
                      <option value="viewer">{roleLabel('viewer')}</option>
                    </select>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`移除成员 ${member.user_id}`}
                      title="移除成员"
                      disabled={member.role === 'owner' || removingMemberId === member.user_id}
                      onClick={() => setRemoveTarget(member)}
                      className="text-white/60 hover:text-red-400"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      <ConfirmDialog
        open={Boolean(removeTarget)}
        title="移除项目成员"
        description={`确定移除${removeTarget ? `「${removeTarget.user_id}」` : '该成员'}？移除后该用户将失去当前项目访问权限。`}
        confirmText="移除成员"
        destructive
        loading={Boolean(removeTarget && removingMemberId === removeTarget.user_id)}
        onOpenChange={(open) => {
          if (!open) setRemoveTarget(null);
        }}
        onConfirm={async () => {
          if (!removeTarget) return;
          await removeMember(removeTarget);
          setRemoveTarget(null);
        }}
      />
    </MainLayout>
  );
}
