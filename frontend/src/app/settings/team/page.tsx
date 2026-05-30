'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import apiClient from '@/lib/api-client';
import {
  Users,
  Crown,
  Eye,
  Edit3,
  Plus,
  Trash2,
  Loader2,
  AlertCircle,
  CheckCircle,
  Mail,
} from 'lucide-react';

type ProjectMember = {
  id: string;
  project_id: string;
  user_id: string;
  role: 'owner' | 'editor' | 'viewer';
  is_active: boolean;
  joined_at?: string;
};

type Project = {
  id: string;
  name: string;
  description?: string;
  user_id: string;
};

const ROLE_CONFIG = {
  owner: { label: '所有者', icon: Crown, color: 'text-amber-400', badge: 'bg-amber-500/20 border-amber-500/30' },
  editor: { label: '编辑', icon: Edit3, color: 'text-cyan-400', badge: 'bg-cyan-500/20 border-cyan-500/30' },
  viewer: { label: '查看', icon: Eye, color: 'text-gray-400', badge: 'bg-gray-500/20 border-gray-500/30' },
};

const ROLE_OPTIONS = [
  { value: 'owner', label: '所有者 (owner)' },
  { value: 'editor', label: '编辑 (editor)' },
  { value: 'viewer', label: '查看 (viewer)' },
];

export default function TeamSettingsPage() {
  const params = useParams();
  const projectId = params.projectId as string || '';

  const [project, setProject] = useState<Project | null>(null);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string>('');

  // Invite dialog
  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [inviteUserId, setInviteUserId] = useState('');
  const [inviteRole, setInviteRole] = useState('editor');
  const [inviting, setInviting] = useState(false);

  // Remove dialog
  const [showRemoveDialog, setShowRemoveDialog] = useState(false);
  const [memberToRemove, setMemberToRemove] = useState<ProjectMember | null>(null);
  const [removing, setRemoving] = useState(false);

  // Role change
  const [updatingRole, setUpdatingRole] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [projectId]);

  async function loadData() {
    if (!projectId) {
      setError('缺少项目ID');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get current user
      const user = await apiClient.getCurrentUser();
      setCurrentUserId(user.id);

      // Get project
      const projectData = await apiClient.getProject(projectId);
      setProject(projectData);

      // Get members
      const membersData = await apiClient.getProjectMembers(projectId);
      setMembers(membersData);
    } catch (err: any) {
      setError(err.message || '加载数据失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleInvite() {
    if (!inviteUserId.trim()) return;

    try {
      setInviting(true);
      await apiClient.createProjectMember(projectId, {
        user_id: inviteUserId.trim(),
        role: inviteRole,
      });
      setShowInviteDialog(false);
      setInviteUserId('');
      setInviteRole('editor');
      await loadData();
    } catch (err: any) {
      alert(err.message || '邀请成员失败');
    } finally {
      setInviting(false);
    }
  }

  async function handleRemoveMember(member: ProjectMember) {
    setMemberToRemove(member);
    setShowRemoveDialog(true);
  }

  async function confirmRemoveMember() {
    if (!memberToRemove) return;

    try {
      setRemoving(true);
      await apiClient.deleteProjectMember(projectId, memberToRemove.user_id);
      setShowRemoveDialog(false);
      setMemberToRemove(null);
      await loadData();
    } catch (err: any) {
      alert(err.message || '移除成员失败');
    } finally {
      setRemoving(false);
    }
  }

  async function handleRoleChange(memberUserId: string, newRole: string) {
    try {
      setUpdatingRole(memberUserId);
      await apiClient.updateProjectMember(projectId, memberUserId, { role: newRole });
      await loadData();
    } catch (err: any) {
      alert(err.message || '更新角色失败');
    } finally {
      setUpdatingRole(null);
    }
  }

  const isOwner = project?.user_id === currentUserId;
  const currentMember = members.find(m => m.user_id === currentUserId);
  const effectiveRole = currentMember?.role || (isOwner ? 'owner' : null);

  if (loading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-cyan-400" />
        </div>
      </MainLayout>
    );
  }

  if (error) {
    return (
      <MainLayout>
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <AlertCircle className="h-12 w-12 text-red-400" />
          <p className="text-white/70">{error}</p>
          <Button variant="outline" onClick={loadData}>重试</Button>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-white/70">
            <Users className="h-4 w-4" />
            团队管理
          </div>
          <h1 className="mt-3 text-3xl font-bold text-white">
            {project?.name || '项目'} - 团队设置
          </h1>
          <p className="mt-1 text-white/60">管理项目成员和访问权限。</p>
        </div>

        {/* Permission Matrix */}
        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <CheckCircle className="h-5 w-5 text-emerald-400" />
              权限说明
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4">
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <div className="flex items-center gap-2 text-amber-400 mb-2">
                  <Crown className="h-4 w-4" />
                  <span className="font-medium">所有者 (owner)</span>
                </div>
                <p className="text-xs text-white/50">完整控制权，可管理成员和项目设置</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <div className="flex items-center gap-2 text-cyan-400 mb-2">
                  <Edit3 className="h-4 w-4" />
                  <span className="font-medium">编辑 (editor)</span>
                </div>
                <p className="text-xs text-white/50">可查看、编辑和生成，但不能管理成员</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <div className="flex items-center gap-2 text-gray-400 mb-2">
                  <Eye className="h-4 w-4" />
                  <span className="font-medium">查看 (viewer)</span>
                </div>
                <p className="text-xs text-white/50">仅可查看，不能编辑或生成内容</p>
              </div>
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3">
                <div className="text-emerald-400 font-medium text-sm mb-1">当前角色</div>
                <p className="text-white text-lg font-bold capitalize">{effectiveRole || '无访问'}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Members List */}
        <Card className="border-white/10 bg-white/5">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-white">
              <Users className="h-5 w-5 text-cyan-300" />
              项目成员 ({members.length})
            </CardTitle>
            {effectiveRole === 'owner' && (
              <Button
                size="sm"
                className="bg-cyan-500 hover:bg-cyan-600"
                onClick={() => setShowInviteDialog(true)}
              >
                <Plus className="h-4 w-4 mr-1" />
                邀请成员
              </Button>
            )}
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {members.map((member) => {
                const roleConfig = ROLE_CONFIG[member.role];
                const RoleIcon = roleConfig.icon;
                const isSelf = member.user_id === currentUserId;
                const isProjectOwner = project?.user_id === member.user_id;

                return (
                  <div
                    key={member.id}
                    className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 p-4"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-full bg-white/10 ${roleConfig.color}`}>
                        <RoleIcon className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-white">
                            {member.user_id.slice(0, 8)}...{member.user_id.slice(-4)}
                          </span>
                          {isSelf && (
                            <Badge variant="outline" className="border-cyan-500/30 text-cyan-300 text-xs">
                              你
                            </Badge>
                          )}
                          {isProjectOwner && (
                            <Badge variant="outline" className="border-amber-500/30 text-amber-300 text-xs">
                              项目创建者
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-white/50">
                          {member.joined_at ? `加入于 ${new Date(member.joined_at).toLocaleDateString()}` : '尚未加入'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {effectiveRole === 'owner' && !isProjectOwner ? (
                        <>
                          <Select
                            options={ROLE_OPTIONS}
                            value={member.role}
                            onChange={(e) => handleRoleChange(member.user_id, e.target.value)}
                            placeholder="选择角色"
                          />
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                            onClick={() => handleRemoveMember(member)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      ) : (
                        <Badge className={roleConfig.badge}>
                          <RoleIcon className={`h-3 w-3 mr-1 ${roleConfig.color}`} />
                          {roleConfig.label}
                        </Badge>
                      )}
                    </div>
                  </div>
                );
              })}

              {members.length === 0 && (
                <div className="flex flex-col items-center justify-center py-8 text-white/50">
                  <Users className="h-12 w-12 mb-2" />
                  <p>暂无成员</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Invite Dialog */}
      <Dialog open={showInviteDialog} onOpenChange={setShowInviteDialog}>
        <DialogContent className="bg-slate-900 border-white/20">
          <DialogHeader>
            <DialogTitle className="text-white">邀请新成员</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="block text-sm text-white/70 mb-2">用户ID</label>
              <Input
                value={inviteUserId}
                onChange={(e) => setInviteUserId(e.target.value)}
                placeholder="输入用户ID"
                className="bg-white/5 border-white/20 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-white/70 mb-2">角色</label>
              <Select
                options={[
                  { value: 'editor', label: '编辑 (editor)' },
                  { value: 'viewer', label: '查看 (viewer)' },
                ]}
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                placeholder="选择角色"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowInviteDialog(false)}>
              取消
            </Button>
            <Button
              className="bg-cyan-500 hover:bg-cyan-600"
              onClick={handleInvite}
              disabled={inviting || !inviteUserId.trim()}
            >
              {inviting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Mail className="h-4 w-4 mr-1" />}
              发送邀请
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Dialog */}
      <Dialog open={showRemoveDialog} onOpenChange={setShowRemoveDialog}>
        <DialogContent className="bg-slate-900 border-white/20">
          <DialogHeader>
            <DialogTitle className="text-white">移除成员</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p className="text-white/70">
              确定要移除成员 <span className="text-white font-medium">{memberToRemove?.user_id.slice(0, 8)}...</span> 吗？
              此操作不会删除该用户的任何数据，但该用户将失去对此项目的访问权限。
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRemoveDialog(false)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={confirmRemoveMember}
              disabled={removing}
            >
              {removing ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Trash2 className="h-4 w-4 mr-1" />}
              确认移除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}