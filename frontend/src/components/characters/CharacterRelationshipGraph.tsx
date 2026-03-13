"use client";

import { useMemo, useState } from "react";
import { ReactFlow, Controls, Background, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toaster";
import { Plus, Save, X } from "lucide-react";

export interface CharacterNode {
  id: string;
  name: string;
  avatar?: string;
  role?: string;
}

export interface CharacterRelationship {
  id: string;
  sourceId: string;
  targetId: string;
  type: "friend" | "enemy" | "family" | "lover" | "colleague" | "rival" | "custom";
  label?: string;
}

interface CharacterRelationshipGraphProps {
  characters: CharacterNode[];
  relationships: CharacterRelationship[];
  onRelationshipAdd?: (relationship: Omit<CharacterRelationship, "id">) => Promise<void>;
  onRelationshipDelete?: (id: string) => Promise<void>;
}

const relationshipStyles: Record<string, { color: string; label: string }> = {
  friend: { color: "#22c55e", label: "朋友" },
  enemy: { color: "#ef4444", label: "敌人" },
  family: { color: "#f59e0b", label: "家人" },
  lover: { color: "#ec4899", label: "恋人" },
  colleague: { color: "#3b82f6", label: "同事" },
  rival: { color: "#f97316", label: "对手" },
  custom: { color: "#8b5cf6", label: "自定义" },
};

const roleColors: Record<string, string> = {
  "主角": "#8b5cf6",
  "配角": "#3b82f6",
  "反派": "#ef4444",
  "客串": "#6b7280",
};

export function CharacterRelationshipGraph({
  characters,
  relationships,
  onRelationshipAdd,
}: CharacterRelationshipGraphProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newRel, setNewRel] = useState({
    sourceId: "",
    targetId: "",
    type: "friend" as CharacterRelationship["type"],
    label: "",
  });

  const nodes = useMemo(() => {
    return characters.map((char, idx) => ({
      id: char.id,
      position: { x: 100 + (idx % 3) * 280, y: 100 + Math.floor(idx / 3) * 180 },
      data: { label: char.name },
      style: {
        background: "#1a1a2e",
        border: `2px solid ${roleColors[char.role || "配角"] || "#8b5cf6"}`,
        borderRadius: "12px",
        padding: "12px 16px",
        minWidth: "140px",
        color: "white",
      },
    }));
  }, [characters]);

  const edges = useMemo(() => {
    return relationships.map((rel) => {
      const style = relationshipStyles[rel.type] || relationshipStyles.custom;
      return {
        id: rel.id,
        source: rel.sourceId,
        target: rel.targetId,
        label: rel.label,
        type: "smoothstep",
        animated: rel.type === "enemy" || rel.type === "rival",
        style: { stroke: style.color, strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: style.color },
        labelStyle: { fill: style.color },
      };
    });
  }, [relationships]);

  const handleAdd = async () => {
    if (!newRel.sourceId || !newRel.targetId) {
      toast({ title: "请选择关系双方", variant: "error" });
      return;
    }
    try {
      await onRelationshipAdd?.({
        sourceId: newRel.sourceId,
        targetId: newRel.targetId,
        type: newRel.type,
        label: newRel.label,
      });
      setShowAddForm(false);
      setNewRel({ sourceId: "", targetId: "", type: "friend", label: "" });
      toast({ title: "添加成功", variant: "success" });
    } catch {
      toast({ title: "添加失败", variant: "error" });
    }
  };

  return (
    <div className="relative w-full h-[500px] bg-[#0f0f1a] rounded-xl overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        className="bg-[#0f0f1a]"
      >
        <Background color="#333" gap={20} />
        <Controls className="bg-[#1a1a2e] border border-white/10" />
      </ReactFlow>

      <div className="absolute top-4 left-4 bg-[#1a1a2e]/90 p-3 rounded-lg border border-white/10">
        <p className="text-xs text-white/60 mb-2">关系类型</p>
        <div className="flex flex-wrap gap-2">
          {Object.entries(relationshipStyles).map(([type, style]) => (
            <div key={type} className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: style.color }} />
              <span className="text-xs text-white/80">{style.label}</span>
            </div>
          ))}
        </div>
      </div>

      {onRelationshipAdd && (
        <div className="absolute top-4 right-4">
          {!showAddForm ? (
            <Button onClick={() => setShowAddForm(true)}>
              <Plus className="w-4 h-4 mr-2" />添加关系
            </Button>
          ) : (
            <Card className="w-72">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">添加角色关系</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <select
                  className="w-full px-3 py-2 rounded bg-white/5 border border-white/10 text-white text-sm"
                  value={newRel.sourceId}
                  onChange={(e) => setNewRel({ ...newRel, sourceId: e.target.value })}
                >
                  <option value="">源角色</option>
                  {characters.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <select
                  className="w-full px-3 py-2 rounded bg-white/5 border border-white/10 text-white text-sm"
                  value={newRel.targetId}
                  onChange={(e) => setNewRel({ ...newRel, targetId: e.target.value })}
                >
                  <option value="">目标角色</option>
                  {characters.filter(c => c.id !== newRel.sourceId).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <select
                  className="w-full px-3 py-2 rounded bg-white/5 border border-white/10 text-white text-sm"
                  value={newRel.type}
                  onChange={(e) => setNewRel({ ...newRel, type: e.target.value as CharacterRelationship["type"] })}
                >
                  <option value="friend">朋友</option>
                  <option value="enemy">敌人</option>
                  <option value="family">家人</option>
                  <option value="lover">恋人</option>
                  <option value="colleague">同事</option>
                  <option value="rival">对手</option>
                </select>
                <Input
                  placeholder="关系标签"
                  value={newRel.label}
                  onChange={(e) => setNewRel({ ...newRel, label: e.target.value })}
                  className="h-8"
                />
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="flex-1" onClick={() => setShowAddForm(false)}>
                    <X className="w-3 h-3" />
                  </Button>
                  <Button size="sm" className="flex-1" onClick={handleAdd}>
                    <Save className="w-3 h-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

export default CharacterRelationshipGraph;