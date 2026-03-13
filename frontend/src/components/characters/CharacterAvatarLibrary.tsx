"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
import { cn } from "@/lib/utils";
import {
  Upload,
  Image as ImageIcon,
  Trash2,
  Loader2,
  Check,
  Wand2,
  X
} from "lucide-react";

interface Avatar {
  id: string;
  url: string;
  isPrimary?: boolean;
}

interface CharacterAvatarLibraryProps {
  characterId: string;
  avatars?: Avatar[];
  currentAvatar?: string;
  onUpload?: (file: File) => Promise<string>;
  onDelete?: (avatarId: string) => Promise<void>;
  onSetPrimary?: (avatarId: string) => Promise<void>;
  onGenerateAI?: () => Promise<string>;
}

export function CharacterAvatarLibrary({
  characterId,
  avatars = [],
  currentAvatar,
  onUpload,
  onDelete,
  onSetPrimary,
  onGenerateAI,
}: CharacterAvatarLibraryProps) {
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [selectedAvatar, setSelectedAvatar] = useState<string | null>(currentAvatar || null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith("image/")) {
      toast({
        title: "无效文件类型",
        description: "请上传图片文件",
        variant: "error",
      });
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast({
        title: "文件过大",
        description: "图片大小不能超过5MB",
        variant: "error",
      });
      return;
    }

    setUploading(true);
    try {
      if (onUpload) {
        const url = await onUpload(file);
        toast({
          title: "上传成功",
          description: "头像已上传",
          variant: "success",
        });
      } else {
        // Default: convert to data URL
        const reader = new FileReader();
        reader.onload = () => {
          toast({
            title: "上传成功",
            description: "头像已上传",
            variant: "success",
          });
        };
        reader.readAsDataURL(file);
      }
    } catch (error) {
      toast({
        title: "上传失败",
        description: "请稍后重试",
        variant: "error",
      });
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleGenerateAI = async () => {
    if (!onGenerateAI) return;
    
    setGenerating(true);
    try {
      await onGenerateAI();
      toast({
        title: "生成成功",
        description: "AI头像已生成",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "生成失败",
        description: "请稍后重试",
        variant: "error",
      });
    } finally {
      setGenerating(false);
    }
  };

  const handleDelete = async (avatarId: string) => {
    if (!onDelete) return;
    
    try {
      await onDelete(avatarId);
      toast({
        title: "删除成功",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "删除失败",
        variant: "error",
      });
    }
  };

  const handleSetPrimary = async (avatarId: string) => {
    if (!onSetPrimary) return;
    
    try {
      await onSetPrimary(avatarId);
      setSelectedAvatar(avatarId);
      toast({
        title: "设置成功",
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "设置失败",
        variant: "error",
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <div className="flex gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleUpload}
          className="hidden"
        />
        <Button
          variant="outline"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Upload className="w-4 h-4 mr-2" />
          )}
          上传头像
        </Button>
        
        {onGenerateAI && (
          <Button
            variant="secondary"
            onClick={handleGenerateAI}
            disabled={generating}
          >
            {generating ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Wand2 className="w-4 h-4 mr-2" />
            )}
            AI生成
          </Button>
        )}
      </div>

      {/* Avatar Grid */}
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-4">
        {/* Current/Main Avatar */}
        {currentAvatar && (
          <div
            className={cn(
              "relative aspect-square rounded-lg overflow-hidden border-2 cursor-pointer transition-all",
              selectedAvatar === currentAvatar
                ? "border-violet-500 ring-2 ring-violet-500/20"
                : "border-white/10 hover:border-violet-500/30"
            )}
            onClick={() => setSelectedAvatar(currentAvatar)}
          >
            <img
              src={currentAvatar}
              alt="当前头像"
              className="w-full h-full object-cover"
            />
            {selectedAvatar === currentAvatar && (
              <div className="absolute top-2 right-2 w-6 h-6 bg-violet-500 rounded-full flex items-center justify-center">
                <Check className="w-4 h-4 text-white" />
              </div>
            )}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
              <span className="text-xs text-white/80">当前头像</span>
            </div>
          </div>
        )}

        {/* Avatar Library */}
        {avatars.map((avatar) => (
          <div
            key={avatar.id}
            className={cn(
              "relative aspect-square rounded-lg overflow-hidden border-2 cursor-pointer transition-all group",
              selectedAvatar === avatar.id
                ? "border-violet-500 ring-2 ring-violet-500/20"
                : "border-white/10 hover:border-violet-500/30"
            )}
            onClick={() => setSelectedAvatar(avatar.id)}
          >
            <img
              src={avatar.url}
              alt={`头像 ${avatar.id}`}
              className="w-full h-full object-cover"
            />
            
            {/* Hover Overlay */}
            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
              {onSetPrimary && !avatar.isPrimary && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSetPrimary(avatar.id);
                  }}
                >
                  <Check className="w-3 h-3 mr-1" />
                  设为主图
                </Button>
              )}
              {onDelete && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(avatar.id);
                  }}
                  className="text-red-400 hover:text-red-300 hover:bg-red-500/20"
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              )}
            </div>

            {/* Primary Badge */}
            {avatar.isPrimary && (
              <div className="absolute top-2 right-2 w-6 h-6 bg-violet-500 rounded-full flex items-center justify-center">
                <Check className="w-4 h-4 text-white" />
              </div>
            )}
          </div>
        ))}

        {/* Empty State */}
        {avatars.length === 0 && !currentAvatar && (
          <div className="col-span-full aspect-video rounded-lg bg-white/5 border-2 border-dashed border-white/10 flex items-center justify-center">
            <div className="text-center">
              <ImageIcon className="w-12 h-12 text-white/20 mx-auto mb-3" />
              <p className="text-white/40 text-sm">暂无头像</p>
              <p className="text-white/20 text-xs mt-1">上传或生成头像</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default CharacterAvatarLibrary;