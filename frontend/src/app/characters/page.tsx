'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MainLayout } from '@/components/layout/main-layout';
import { 
  Users, 
  Plus, 
  Edit2, 
  Trash2,
  Search,
  User,
  Palette,
  Mic,
  Sparkles,
  Save,
  X,
  ChevronRight,
  Image as ImageIcon
} from 'lucide-react';

// 角色数据类型
interface Character {
  id: string;
  name: string;
  description: string;
  appearance: string;
  personality: string;
  voice: string;
  avatar?: string;
  tags: string[];
  createdAt: string;
}

// 模拟角色数据
const MOCK_CHARACTERS: Character[] = [
  {
    id: '1',
    name: '李逍遥',
    description: '主角，性格豪爽，武功高强',
    appearance: '白衣少年，手持长剑，眼神坚定',
    personality: '正直善良，重情重义，偶尔有些冲动',
    voice: '男声，清亮有力，语速适中',
    tags: ['主角', '武侠', '正派'],
    createdAt: '2024-03-15'
  },
  {
    id: '2',
    name: '林月如',
    description: '女主角，温柔聪慧',
    appearance: '青衣少女，手持折扇，气质优雅',
    personality: '温柔体贴，聪明机智，善解人意',
    voice: '女声，柔美动听，语调轻柔',
    tags: ['女主', '武侠', '正派'],
    createdAt: '2024-03-15'
  }
];

export default function CharactersPage() {
  const [characters, setCharacters] = useState<Character[]>(MOCK_CHARACTERS);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  // 表单状态
  const [formData, setFormData] = useState<Partial<Character>>({
    name: '',
    description: '',
    appearance: '',
    personality: '',
    voice: '',
    tags: []
  });

  // 过滤角色
  const filteredCharacters = characters.filter(char => 
    char.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    char.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    char.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // 选择角色
  const handleSelectCharacter = (char: Character) => {
    setSelectedCharacter(char);
    setFormData(char);
    setIsEditing(false);
    setIsCreating(false);
  };

  // 创建新角色
  const handleCreate = () => {
    setIsCreating(true);
    setIsEditing(true);
    setSelectedCharacter(null);
    setFormData({
      name: '',
      description: '',
      appearance: '',
      personality: '',
      voice: '',
      tags: []
    });
  };

  // 编辑角色
  const handleEdit = () => {
    if (selectedCharacter) {
      setIsEditing(true);
      setFormData(selectedCharacter);
    }
  };

  // 保存角色
  const handleSave = () => {
    if (isCreating) {
      // 创建新角色
      const newCharacter: Character = {
        id: Date.now().toString(),
        name: formData.name || '',
        description: formData.description || '',
        appearance: formData.appearance || '',
        personality: formData.personality || '',
        voice: formData.voice || '',
        tags: formData.tags || [],
        createdAt: new Date().toISOString().split('T')[0]
      };
      setCharacters([...characters, newCharacter]);
      setSelectedCharacter(newCharacter);
    } else if (selectedCharacter) {
      // 更新现有角色
      const updatedCharacters = characters.map(char => 
        char.id === selectedCharacter.id 
          ? { ...char, ...formData } as Character
          : char
      );
      setCharacters(updatedCharacters);
      setSelectedCharacter({ ...selectedCharacter, ...formData } as Character);
    }
    
    setIsEditing(false);
    setIsCreating(false);
  };

  // 删除角色
  const handleDelete = (id: string) => {
    setCharacters(characters.filter(char => char.id !== id));
    if (selectedCharacter?.id === id) {
      setSelectedCharacter(null);
    }
  };

  // 取消编辑
  const handleCancel = () => {
    setIsEditing(false);
    setIsCreating(false);
    if (selectedCharacter) {
      setFormData(selectedCharacter);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Users className="w-6 h-6" />
              角色管理
            </h1>
            <p className="text-white/60 mt-1">创建和管理您的角色库</p>
          </div>
          <Button 
            onClick={handleCreate}
            className="bg-violet-600 hover:bg-violet-700"
          >
            <Plus className="w-4 h-4 mr-2" />
            新建角色
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：角色列表 */}
          <div className="lg:col-span-1 space-y-4">
            {/* 搜索框 */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
              <Input
                placeholder="搜索角色..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 bg-white/5 border-white/10"
              />
            </div>

            {/* 角色列表 */}
            <div className="space-y-2">
              {filteredCharacters.map((char) => (
                <div
                  key={char.id}
                  onClick={() => handleSelectCharacter(char)}
                  className={`p-4 rounded-lg border cursor-pointer transition-all ${
                    selectedCharacter?.id === char.id
                      ? 'border-violet-500 bg-violet-500/10'
                      : 'border-white/10 hover:border-white/20 bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                      <User className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-white font-medium truncate">
                        {char.name}
                      </div>
                      <div className="text-white/60 text-sm truncate">
                        {char.description}
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-white/40" />
                  </div>
                  
                  {/* 标签 */}
                  <div className="flex gap-1 mt-2">
                    {char.tags.slice(0, 3).map((tag, idx) => (
                      <span 
                        key={idx}
                        className="px-2 py-0.5 text-xs bg-white/10 text-white/70 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
              
              {filteredCharacters.length === 0 && (
                <div className="text-center py-8 text-white/40">
                  <Users className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>暂无角色</p>
                  <p className="text-sm">点击上方按钮创建</p>
                </div>
              )}
            </div>
          </div>

          {/* 右侧：角色详情/编辑 */}
          <div className="lg:col-span-2">
            {(selectedCharacter || isCreating) ? (
              <Card className="bg-white/5 border-white/10">
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-white flex items-center gap-2">
                    {isCreating ? (
                      <>
                        <Plus className="w-5 h-5" />
                        新建角色
                      </>
                    ) : (
                      <>
                        <User className="w-5 h-5" />
                        {isEditing ? '编辑角色' : '角色详情'}
                      </>
                    )}
                  </CardTitle>
                  
                  <div className="flex gap-2">
                    {!isEditing && selectedCharacter && (
                      <>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={handleEdit}
                        >
                          <Edit2 className="w-4 h-4 mr-1" />
                          编辑
                        </Button>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleDelete(selectedCharacter.id)}
                          className="text-red-400 hover:text-red-300"
                        >
                          <Trash2 className="w-4 h-4 mr-1" />
                          删除
                        </Button>
                      </>
                    )}
                    
                    {isEditing && (
                      <>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={handleCancel}
                        >
                          <X className="w-4 h-4 mr-1" />
                          取消
                        </Button>
                        <Button 
                          size="sm"
                          onClick={handleSave}
                          className="bg-violet-600 hover:bg-violet-700"
                        >
                          <Save className="w-4 h-4 mr-1" />
                          保存
                        </Button>
                      </>
                    )}
                  </div>
                </CardHeader>
                
                <CardContent className="space-y-6">
                  {/* 基本信息 */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-white/80 mb-2">
                      <User className="w-4 h-4" />
                      <span className="font-medium">基本信息</span>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm text-white/60 mb-1">
                          角色名称 *
                        </label>
                        {isEditing ? (
                          <Input
                            value={formData.name}
                            onChange={(e) => setFormData({...formData, name: e.target.value})}
                            placeholder="输入角色名称"
                            className="bg-white/5 border-white/10"
                          />
                        ) : (
                          <div className="text-white p-2 bg-white/5 rounded">
                            {selectedCharacter?.name}
                          </div>
                        )}
                      </div>
                      
                      <div>
                        <label className="block text-sm text-white/60 mb-1">
                          标签
                        </label>
                        {isEditing ? (
                          <Input
                            value={formData.tags?.join(', ')}
                            onChange={(e) => setFormData({...formData, tags: e.target.value.split(',').map(t => t.trim())})}
                            placeholder="用逗号分隔，如：主角,武侠,正派"
                            className="bg-white/5 border-white/10"
                          />
                        ) : (
                          <div className="flex gap-1">
                            {selectedCharacter?.tags.map((tag, idx) => (
                              <span 
                                key={idx}
                                className="px-2 py-1 text-sm bg-violet-500/20 text-violet-300 rounded"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div>
                      <label className="block text-sm text-white/60 mb-1">
                        角色简介
                      </label>
                      {isEditing ? (
                        <textarea
                          value={formData.description}
                          onChange={(e) => setFormData({...formData, description: e.target.value})}
                          placeholder="简要描述角色的定位和特点"
                          rows={2}
                          className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40"
                        />
                      ) : (
                        <div className="text-white p-3 bg-white/5 rounded min-h-[60px]">
                          {selectedCharacter?.description}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 外观特征 */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-white/80 mb-2">
                      <Palette className="w-4 h-4" />
                      <span className="font-medium">外观特征</span>
                    </div>
                    
                    {isEditing ? (
                      <textarea
                        value={formData.appearance}
                        onChange={(e) => setFormData({...formData, appearance: e.target.value})}
                        placeholder="描述角色的外貌特征：身高、体型、发型、服装、配饰等"
                        rows={3}
                        className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40"
                      />
                    ) : (
                      <div className="text-white p-3 bg-white/5 rounded min-h-[80px]">
                        {selectedCharacter?.appearance || '未设置'}
                      </div>
                    )}
                  </div>

                  {/* 性格特征 */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-white/80 mb-2">
                      <Sparkles className="w-4 h-4" />
                      <span className="font-medium">性格特征</span>
                    </div>
                    
                    {isEditing ? (
                      <textarea
                        value={formData.personality}
                        onChange={(e) => setFormData({...formData, personality: e.target.value})}
                        placeholder="描述角色的性格特点：内向/外向、勇敢/谨慎、善良/冷酷等"
                        rows={3}
                        className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40"
                      />
                    ) : (
                      <div className="text-white p-3 bg-white/5 rounded min-h-[80px]">
                        {selectedCharacter?.personality || '未设置'}
                      </div>
                    )}
                  </div>

                  {/* 声音特征 */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-white/80 mb-2">
                      <Mic className="w-4 h-4" />
                      <span className="font-medium">声音特征</span>
                    </div>
                    
                    {isEditing ? (
                      <textarea
                        value={formData.voice}
                        onChange={(e) => setFormData({...formData, voice: e.target.value})}
                        placeholder="描述角色的声音特点：男/女、年龄、音色、语速、口音等"
                        rows={2}
                        className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/40"
                      />
                    ) : (
                      <div className="text-white p-3 bg-white/5 rounded min-h-[60px]">
                        {selectedCharacter?.voice || '未设置'}
                      </div>
                    )}
                  </div>

                  {/* 角色头像 */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-white/80 mb-2">
                      <ImageIcon className="w-4 h-4" />
                      <span className="font-medium">角色头像</span>
                    </div>
                    
                    <div className="flex items-center gap-4">
                      <div className="w-20 h-20 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                        <User className="w-10 h-10 text-white" />
                      </div>
                      
                      {isEditing && (
                        <div className="space-y-2">
                          <Button variant="outline" size="sm">
                            上传图片
                          </Button>
                          <Button variant="outline" size="sm">
                            <Sparkles className="w-4 h-4 mr-1" />
                            AI生成
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-white/40">
                <Users className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg">选择一个角色查看详情</p>
                <p className="text-sm mt-2">或点击"新建角色"创建新角色</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
