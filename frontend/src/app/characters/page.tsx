"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
import { 
  Plus, 
  Search, 
  Edit, 
  Trash2, 
  Users,
  ChevronLeft,
  Sparkles,
  Wand2,
  Image as ImageIcon,
  Save,
  RefreshCw,
  CheckCircle
} from "lucide-react";
import { cn } from "@/lib/utils";

// Mock data
const characters = [
  {
    id: 1,
    name: "李明",
    novel: "星际穿越",
    role: "主角",
    description: "年轻的物理学家，对宇宙充满好奇",
    personality: "聪明、勇敢、有点固执",
    appearance: "短发，戴眼镜，常穿实验室白大褂",
    age: 28,
    gender: "男",
    avatar: null,
  },
  {
    id: 2,
    name: "Sarah Chen",
    novel: "星际穿越",
    role: "配角",
    description: "李明的助手，计算机专家",
    personality: "细心、理性、善于分析",
    appearance: "长发，干练的穿着",
    age: 26,
    gender: "女",
    avatar: null,
  },
  {
    id: 3,
    name: "AI-7",
    novel: "未来世界",
    role: "主角",
    description: "觉醒的人工智能",
    personality: "好奇、渴望理解人类情感",
    appearance: "全息投影，可变换形态",
    age: null,
    gender: "无",
    avatar: null,
  },
  {
    id: 4,
    name: "王小明",
    novel: "魔法学院",
    role: "主角",
    description: "普通少年，意外获得魔法天赋",
    personality: "善良、有点胆小但勇敢",
    appearance: "瘦高，常穿学院制服",
    age: 16,
    gender: "男",
    avatar: null,
  },
];

const roleColors = {
  "主角": "bg-violet-500/20 text-violet-300",
  "配角": "bg-blue-500/20 text-blue-300",
  "反派": "bg-red-500/20 text-red-300",
};

export default function CharactersPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDetail, setShowDetail] = useState(false);
  const [selectedCharacter, setSelectedCharacter] = useState<typeof characters[0] | null>(null);

  const filteredCharacters = characters.filter(
    (char) =>
      char.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      char.novel.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleViewCharacter = (char: typeof characters[0]) => {
    setSelectedCharacter(char);
    setShowDetail(true);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      {/* Header */}
      <header className="h-16 border-b border-white/10 flex items-center px-8">
        <button 
          onClick={() => router.push("/dashboard")}
          className="flex items-center gap-2 text-white/60 hover:text-white transition-colors"
        >
          <ChevronLeft className="w-5 h-5" />
          返回
        </button>
        <h1 className="text-xl font-semibold ml-4">角色管理</h1>
      </header>

      {/* Content */}
      <div className="p-8">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
              <Input
                placeholder="搜索角色..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-64 pl-10"
              />
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary">
              <Sparkles className="w-4 h-4 mr-2" />
              AI生成角色
            </Button>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="w-4 h-4 mr-2" />
              新建角色
            </Button>
          </div>
        </div>

        {/* Characters Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredCharacters.map((char) => (
            <Card 
              key={char.id} 
              className="group hover:border-violet-500/30 transition-all cursor-pointer"
              onClick={() => handleViewCharacter(char)}
            >
              <CardContent className="p-6">
                {/* Avatar */}
                <div className="flex justify-center mb-4">
                  <div className="w-24 h-24 rounded-full bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center border-2 border-white/10 group-hover:border-violet-500/30 transition-all">
                    <span className="text-3xl font-bold text-violet-400">
                      {char.name.charAt(0)}
                    </span>
                  </div>
                </div>

                {/* Info */}
                <div className="text-center mb-4">
                  <h3 className="font-semibold text-lg">{char.name}</h3>
                  <p className="text-sm text-white/40">{char.novel}</p>
                </div>

                {/* Tags */}
                <div className="flex flex-wrap justify-center gap-2 mb-4">
                  <span className={cn(
                    "px-2 py-1 rounded-full text-xs",
                    roleColors[char.role as keyof typeof roleColors] || "bg-white/10 text-white/60"
                  )}>
                    {char.role}
                  </span>
                  {char.age && (
                    <span className="px-2 py-1 rounded-full text-xs bg-white/10 text-white/60">
                      {char.age}岁
                    </span>
                  )}
                  <span className="px-2 py-1 rounded-full text-xs bg-white/10 text-white/60">
                    {char.gender}
                  </span>
                </div>

                <p className="text-sm text-white/60 text-center line-clamp-2">
                  {char.description}
                </p>

                {/* Actions */}
                <div className="flex gap-2 mt-4">
                  <Button variant="outline" size="sm" className="flex-1">
                    <Edit className="w-4 h-4 mr-1" />
                    编辑
                  </Button>
                  <Button variant="secondary" size="sm" className="flex-1">
                    <Wand2 className="w-4 h-4 mr-1" />
                    生成形象
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Empty state */}
        {filteredCharacters.length === 0 && (
          <div className="text-center py-20">
            <Users className="w-16 h-16 text-white/20 mx-auto mb-4" />
            <p className="text-white/60">暂无角色</p>
            <Button variant="outline" className="mt-4" onClick={() => setShowCreateModal(true)}>
              创建第一个角色
            </Button>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <Card className="w-full max-w-lg max-h-[90vh] overflow-auto">
            <CardHeader>
              <CardTitle>新建角色</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Input label="角色名称" placeholder="输入角色名称" />
                <Input label="年龄" placeholder="输入年龄" type="number" />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-1.5">
                    性别
                  </label>
                  <select className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white">
                    <option>男</option>
                    <option>女</option>
                    <option>无</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-1.5">
                    角色类型
                  </label>
                  <select className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white">
                    <option>主角</option>
                    <option>配角</option>
                    <option>反派</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  关联小说
                </label>
                <select className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white">
                  <option>星际穿越</option>
                  <option>未来世界</option>
                  <option>魔法学院</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  角色简介
                </label>
                <textarea
                  className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 min-h-[80px]"
                  placeholder="描述角色的背景和定位"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  性格特点
                </label>
                <textarea
                  className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 min-h-[80px]"
                  placeholder="描述角色的性格特征"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-white/80 mb-1.5">
                  外貌描述
                </label>
                <textarea
                  className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 min-h-[80px]"
                  placeholder="描述角色的外貌特征"
                />
              </div>

              <div className="flex gap-3 pt-4">
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={() => setShowCreateModal(false)}
                >
                  取消
                </Button>
                <Button className="flex-1" onClick={() => {
                  setShowCreateModal(false);
                  toast({
                    title: "创建成功",
                    description: "角色已创建",
                    variant: "success",
                  });
                }}>
                  创建
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Character Detail Modal */}
      {showDetail && selectedCharacter && (
        <CharacterDetail 
          character={selectedCharacter} 
          onClose={() => setShowDetail(false)} 
        />
      )}
    </div>
  );
}

// Character Detail Component
function CharacterDetail({ character, onClose }: { character: typeof characters[0]; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState("info");
  const [isGenerating, setIsGenerating] = useState(false);

  const tabs = [
    { id: "info", label: "角色信息" },
    { id: "appearance", label: "形象预览" },
    { id: "consistency", label: "一致性" },
  ];

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-auto">
        {/* Header */}
        <div className="p-6 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center">
              <span className="text-2xl font-bold text-violet-400">
                {character.name.charAt(0)}
              </span>
            </div>
            <div>
              <h2 className="text-xl font-bold">{character.name}</h2>
              <p className="text-sm text-white/40">{character.novel} · {character.role}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white">
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-white/10">
          <div className="flex">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "px-6 py-3 text-sm font-medium transition-colors border-b-2",
                  activeTab === tab.id
                    ? "text-violet-400 border-violet-400"
                    : "text-white/60 border-transparent hover:text-white"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {activeTab === "info" && (
            <div className="space-y-6">
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-white/5">
                  <p className="text-sm text-white/40">年龄</p>
                  <p className="text-lg font-medium">{character.age || "未知"}</p>
                </div>
                <div className="p-4 rounded-lg bg-white/5">
                  <p className="text-sm text-white/40">性别</p>
                  <p className="text-lg font-medium">{character.gender}</p>
                </div>
                <div className="p-4 rounded-lg bg-white/5">
                  <p className="text-sm text-white/40">角色定位</p>
                  <p className="text-lg font-medium">{character.role}</p>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-medium text-white/60 mb-2">简介</h3>
                <p className="text-white/80">{character.description}</p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-white/60 mb-2">性格</h3>
                <p className="text-white/80">{character.personality}</p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-white/60 mb-2">外貌</h3>
                <p className="text-white/80">{character.appearance}</p>
              </div>

              <div className="flex gap-3 pt-4">
                <Button>
                  <Edit className="w-4 h-4 mr-2" />
                  编辑信息
                </Button>
                <Button variant="secondary">
                  <RefreshCw className="w-4 h-4 mr-2" />
                  AI完善
                </Button>
              </div>
            </div>
          )}

          {activeTab === "appearance" && (
            <div className="space-y-6">
              <div className="aspect-video rounded-lg bg-white/5 flex items-center justify-center border-2 border-dashed border-white/10">
                <div className="text-center">
                  <ImageIcon className="w-16 h-16 text-white/20 mx-auto mb-4" />
                  <p className="text-white/40 mb-4">暂无角色形象</p>
                  <Button 
                    variant="secondary" 
                    isLoading={isGenerating}
                    onClick={() => {
                      setIsGenerating(true);
                      setTimeout(() => {
                        setIsGenerating(false);
                        toast({
                          title: "生成完成",
                          description: "角色形象已生成",
                          variant: "success",
                        });
                      }, 2000);
                    }}
                  >
                    <Sparkles className="w-4 h-4 mr-2" />
                    AI生成形象
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <div 
                    key={i}
                    className="aspect-square rounded-lg bg-white/5 flex items-center justify-center border border-white/10 hover:border-violet-500/30 transition-colors cursor-pointer"
                  >
                    <span className="text-white/20">变体 {i}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "consistency" && (
            <div className="space-y-6">
              <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                <div className="flex items-center gap-2 text-green-400 mb-2">
                  <CheckCircle className="w-5 h-5" />
                  <span className="font-medium">一致性检查通过</span>
                </div>
                <p className="text-sm text-white/60">
                  该角色在所有场景中的描述保持一致
                </p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-white/60 mb-3">关键特征</h3>
                <div className="space-y-2">
                  {[
                    { feature: "短发", confirmed: true },
                    { feature: "戴眼镜", confirmed: true },
                    { feature: "白大褂", confirmed: true },
                    { feature: "身高180cm", confirmed: false },
                  ].map((item, i) => (
                    <div 
                      key={i}
                      className="flex items-center justify-between p-3 rounded-lg bg-white/5"
                    >
                      <span>{item.feature}</span>
                      <span className={cn(
                        "text-sm",
                        item.confirmed ? "text-green-400" : "text-yellow-400"
                      )}>
                        {item.confirmed ? "已确认" : "待确认"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
