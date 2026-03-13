"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { 
  Users, 
  Plus, 
  Settings, 
  Mail, 
  MoreVertical,
  Crown,
  Shield,
  Edit3,
  Eye,
  Trash2,
  UserPlus,
  Activity,
  Folder
} from "lucide-react";
import { api } from "@/lib/api";

interface Team {
  id: string;
  name: string;
  description: string;
  member_count: number;
  project_count: number;
  logo_url: string;
  theme_color: string;
}

interface Member {
  id: string;
  user_id: string;
  username: string;
  nickname: string;
  avatar: string;
  role: string;
  joined_at: string;
}

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamDesc, setNewTeamDesc] = useState("");

  useEffect(() => {
    loadTeams();
  }, []);

  const loadTeams = async () => {
    setLoading(true);
    try {
      const response = await api.get("/api/v1/teams");
      setTeams(response.data.items || []);
      
      // 如果没有团队，显示示例
      if (response.data.items?.length === 0) {
        setTeams([
          {
            id: "1",
            name: "我的工作室",
            description: "个人创作团队",
            member_count: 1,
            project_count: 5,
            logo_url: "",
            theme_color: "#6366f1",
          },
        ]);
      }
    } catch (error) {
      console.error("加载团队失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadMembers = async (teamId: string) => {
    try {
      const response = await api.get(`/api/v1/teams/${teamId}/members`);
      setMembers(response.data.items || []);
    } catch (error) {
      console.error("加载成员失败:", error);
    }
  };

  const handleCreateTeam = async () => {
    if (!newTeamName.trim()) return;
    
    try {
      await api.post("/api/v1/teams", {
        name: newTeamName,
        description: newTeamDesc,
      });
      setCreateDialogOpen(false);
      setNewTeamName("");
      setNewTeamDesc("");
      loadTeams();
    } catch (error) {
      console.error("创建团队失败:", error);
    }
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case "owner": return <Crown className="h-4 w-4 text-yellow-400" />;
      case "admin": return <Shield className="h-4 w-4 text-red-400" />;
      case "editor": return <Edit3 className="h-4 w-4 text-blue-400" />;
      default: return <Eye className="h-4 w-4 text-gray-400" />;
    }
  };

  const getRoleName = (role: string) => {
    switch (role) {
      case "owner": return "所有者";
      case "admin": return "管理员";
      case "editor": return "编辑者";
      default: return "查看者";
    }
  };

  return (
    <div className="min-h-screen bg-slate-900">
      {/* 头部 */}
      <header className="glass border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-xl font-bold text-white">团队管理</h1>
            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-violet-600">
                  <Plus className="h-4 w-4 mr-2" />
                  创建团队
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-slate-800 border-white/10">
                <DialogHeader>
                  <DialogTitle className="text-white">创建新团队</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-4">
                  <div>
                    <label className="text-white/80 text-sm">团队名称</label>
                    <Input
                      value={newTeamName}
                      onChange={(e) => setNewTeamName(e.target.value)}
                      placeholder="输入团队名称"
                      className="bg-white/5 border-white/10 mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-white/80 text-sm">团队描述</label>
                    <Input
                      value={newTeamDesc}
                      onChange={(e) => setNewTeamDesc(e.target.value)}
                      placeholder="输入团队描述"
                      className="bg-white/5 border-white/10 mt-1"
                    />
                  </div>
                  <Button onClick={handleCreateTeam} className="w-full bg-violet-600">
                    创建团队
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 团队列表 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {teams.map((team) => (
            <Card 
              key={team.id} 
              className="bg-white/5 border-white/10 hover:border-violet-500/50 transition-all cursor-pointer"
              onClick={() => {
                setSelectedTeam(team);
                loadMembers(team.id);
              }}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center gap-3">
                  <div 
                    className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold"
                    style={{ backgroundColor: team.theme_color || '#6366f1' }}
                  >
                    {team.name.charAt(0)}
                  </div>
                  <div className="flex-1">
                    <CardTitle className="text-white text-lg">{team.name}</CardTitle>
                    <p className="text-white/40 text-sm">{team.description || '暂无描述'}</p>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-1 text-white/60">
                    <Users className="h-4 w-4" />
                    {team.member_count} 成员
                  </div>
                  <div className="flex items-center gap-1 text-white/60">
                    <Folder className="h-4 w-4" />
                    {team.project_count} 项目
                  </div>
                  <Button variant="ghost" size="sm" className="h-8">
                    <Settings className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* 成员列表（选中团队时显示） */}
        {selectedTeam && (
          <Card className="mt-8 bg-white/5 border-white/10">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-white flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  {selectedTeam.name} - 成员管理
                </CardTitle>
                <Button variant="outline" size="sm" className="bg-white/5 border-white/10">
                  <UserPlus className="h-4 w-4 mr-2" />
                  邀请成员
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {members.length > 0 ? members.map((member) => (
                  <div 
                    key={member.id}
                    className="flex items-center justify-between p-3 rounded-lg bg-white/5"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center">
                        <span className="text-white text-sm">{member.nickname?.charAt(0) || member.username.charAt(0)}</span>
                      </div>
                      <div>
                        <p className="text-white font-medium">{member.nickname || member.username}</p>
                        <p className="text-white/40 text-sm">@{member.username}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className="bg-white/10 flex items-center gap-1">
                        {getRoleIcon(member.role)}
                        {getRoleName(member.role)}
                      </Badge>
                      {member.role !== 'owner' && (
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                )) : (
                  <div className="text-center py-8 text-white/40">
                    <Users className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p>暂无成员</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 活动日志 */}
        <Card className="mt-8 bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Activity className="h-5 w-5" />
              团队活动
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-white/5">
                <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
                  <Plus className="h-4 w-4 text-green-400" />
                </div>
                <div className="flex-1">
                  <p className="text-white text-sm">创建了新项目 <span className="text-violet-400">纳米漫剧第一集</span></p>
                  <p className="text-white/40 text-xs">2小时前</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-white/5">
                <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                  <UserPlus className="h-4 w-4 text-blue-400" />
                </div>
                <div className="flex-1">
                  <p className="text-white text-sm">邀请 <span className="text-violet-400">zhangsan@email.com</span> 加入团队</p>
                  <p className="text-white/40 text-xs">昨天</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}