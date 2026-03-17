'use client';

import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Users, Plus, Mail, Crown, UserCircle } from 'lucide-react';

const teamMembers = [
  { id: 1, name: '张三', email: 'zhangsan@example.com', role: 'owner', avatar: 'ZS' },
  { id: 2, name: '李四', email: 'lisi@example.com', role: 'admin', avatar: 'LS' },
  { id: 3, name: '王五', email: 'wangwu@example.com', role: 'member', avatar: 'WW' },
];

export default function TeamsPage() {
  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">团队管理</h1>
            <p className="text-white/60 mt-1">管理团队成员和权限</p>
          </div>
          <Button className="bg-violet-600 hover:bg-violet-700">
            <Plus className="w-4 h-4 mr-2" />
            邀请成员
          </Button>
        </div>

        {/* 团队统计 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="text-3xl font-bold text-white">3</div>
              <div className="text-white/60">团队成员</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="text-3xl font-bold text-white">1</div>
              <div className="text-white/60">管理员</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="text-3xl font-bold text-white">5</div>
              <div className="text-white/60">待处理邀请</div>
            </CardContent>
          </Card>
        </div>

        {/* 成员列表 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Users className="w-5 h-5 text-violet-400" />
              团队成员
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {teamMembers.map((member) => (
                <div key={member.id} className="flex items-center gap-4 p-4 rounded-lg bg-white/5">
                  <div className="w-10 h-10 rounded-full bg-violet-600 flex items-center justify-center text-white font-medium">
                    {member.avatar}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{member.name}</span>
                      {member.role === 'owner' && (
                        <Crown className="w-4 h-4 text-yellow-400" />
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-white/60 text-sm">
                      <Mail className="w-3 h-3" />
                      {member.email}
                    </div>
                  </div>
                  <div className="text-white/60 text-sm capitalize">
                    {member.role === 'owner' ? '所有者' : member.role === 'admin' ? '管理员' : '成员'}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}