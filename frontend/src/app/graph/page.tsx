'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { MainLayout } from '@/components/layout/main-layout';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Users,
  Box,
  MapPin,
  RefreshCw,
  GitGraph,
  Plus,
  Eye,
  Move,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Link2,
} from 'lucide-react';
import * as d3 from 'd3';
import { apiClient } from '@/lib/api-client';

interface Novel {
  id: string;
  title: string;
  description?: string;
}

interface EntityNode {
  id: string;
  entity_type: string;
  name: string;
  description?: string;
  appearance?: string;
  avatar_url?: string;
  tags: string[];
  // D3 布局属性
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface RelationEdge {
  id: string;
  from_entity_id: string;
  to_entity_id: string;
  relation_type: string;
  description?: string;
}

interface GraphData {
  nodes: EntityNode[];
  edges: RelationEdge[];
  total_nodes: number;
  total_edges: number;
}

interface CharacterDetail {
  id: string;
  name: string;
  description?: string;
  appearance?: string;
  avatar_url?: string;
  relations: any[];
  scenes: any[];
  is_connected: boolean;
}

const ENTITY_COLORS: Record<string, string> = {
  character: '#10b981', // green
  scene: '#3b82f6', // blue
  prop: '#f59e0b', // amber
  event: '#a855f7', // purple
};

const RELATION_COLORS: Record<string, string> = {
  friend: '#10b981',
  enemy: '#ef4444',
  family: '#3b82f6',
  love: '#ec4899',
  rival: '#f97316',
  mentor: '#8b5cf6',
  possession: '#f59e0b',
  located: '#06b6d4',
};

const RELATION_LABELS: Record<string, string> = {
  FRIEND: '朋友',
  ENEMY: '敌人',
  FAMILY: '家人',
  LOVE: '恋人',
  RIVAL: '对手',
  MENTOR: '导师',
  POSSESSION: '拥有',
  LOCATED: '位于',
  RELATES_TO: '关联',
  APPEARS_WITH: '同现',
  APPEARS_IN: '出现于',
};

const NOVEL_OPTIONS = [
  { value: '', label: '选择小说' },
];

export default function GraphPage() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [selectedNovelId, setSelectedNovelId] = useState<string>('');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [activeTab, setActiveTab] = useState('graph');
  const [selectedNode, setSelectedNode] = useState<EntityNode | null>(null);
  const [nodeDetail, setNodeDetail] = useState<CharacterDetail | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);

  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<d3.Simulation<EntityNode, RelationEdge> | null>(null);

  // 加载小说列表
  useEffect(() => {
    loadNovels();
  }, []);

  // 当选择小说变化时加载图谱
  useEffect(() => {
    if (selectedNovelId) {
      loadGraph();
    }
  }, [selectedNovelId]);

  const loadNovels = async () => {
    try {
      const data = await apiClient.getNovels();
      setNovels(data);
      if (data.length > 0) {
        setSelectedNovelId(data[0].id);
      }
    } catch (error) {
      console.error('加载小说失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadGraph = async () => {
    if (!selectedNovelId) return;
    setLoadingGraph(true);
    try {
      const data = await apiClient.getNovelGraph(selectedNovelId);
      setGraphData(data);
    } catch (error) {
      console.error('加载图谱失败:', error);
    } finally {
      setLoadingGraph(false);
    }
  };

  const handleNodeClick = async (node: EntityNode) => {
    setSelectedNode(node);
    if (node.entity_type === 'character') {
      try {
        const data = await apiClient.getCharacterRelations(node.id);
        setNodeDetail(data);
        setDetailDialogOpen(true);
      } catch (error) {
        console.error('加载角色详情失败:', error);
      }
    }
  };

  const getRelationLabel = (type: string): string => {
    return RELATION_LABELS[type] || type;
  };

  // D3 图谱渲染
  const renderGraph = useCallback(() => {
    if (!svgRef.current || !graphData || graphData.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // 创建缩放行为
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        setZoomLevel(event.transform.k);
      });

    svg.call(zoom);

    const g = svg.append('g');

    // 创建箭头标记
    const defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('path')
      .attr('d', 'M 0,-5 L 10,0 L 0,5')
      .attr('fill', '#666');

    // 创建力模拟
    const simulation = d3.forceSimulation<EntityNode, RelationEdge>(graphData.nodes)
      .force('link', d3.forceLink<EntityNode, RelationEdge>(graphData.edges)
        .id(d => d.id)
        .distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40));

    simulationRef.current = simulation;

    // 绘制边
    const link = g.append('g')
      .selectAll('line')
      .data(graphData.edges)
      .join('line')
      .attr('stroke', d => RELATION_COLORS[d.relation_type] || '#666')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 2)
      .attr('marker-end', 'url(#arrowhead)');

    // 绘制边标签
    const linkLabel = g.append('g')
      .selectAll('text')
      .data(graphData.edges)
      .join('text')
      .attr('font-size', 10)
      .attr('fill', '#999')
      .text(d => getRelationLabel(d.relation_type));

    // 绘制节点
    const node = g.append('g')
      .selectAll('g')
      .data(graphData.nodes)
      .join('g')
      .call(d3.drag<SVGGElement, EntityNode>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended) as any)
      .on('click', (event, d) => {
        event.stopPropagation();
        handleNodeClick(d);
      });

    // 节点圆形
    node.append('circle')
      .attr('r', 24)
      .attr('fill', d => ENTITY_COLORS[d.entity_type] || '#666')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer');

    // 节点图标
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', 16)
      .attr('fill', '#fff')
      .text(d => {
        switch (d.entity_type) {
          case 'character': return '👤';
          case 'scene': return '📍';
          case 'prop': return '📦';
          case 'event': return '⚡';
          default: return '●';
        }
      });

    // 节点标签
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 40)
      .attr('fill', '#fff')
      .attr('font-size', 12)
      .text(d => d.name.length > 10 ? d.name.slice(0, 10) + '...' : d.name);

    // 更新位置
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as EntityNode).x!)
        .attr('y1', d => (d.source as EntityNode).y!)
        .attr('x2', d => (d.target as EntityNode).x!)
        .attr('y2', d => (d.target as EntityNode).y!);

      linkLabel
        .attr('x', d => ((d.source as EntityNode).x! + (d.target as EntityNode).x!) / 2)
        .attr('y', d => ((d.source as EntityNode).y! + (d.target as EntityNode).y!) / 2);

      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    function dragstarted(event: d3.D3DragEvent<SVGGElement, EntityNode, EntityNode>) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: d3.D3DragEvent<SVGGElement, EntityNode, EntityNode>) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: d3.D3DragEvent<SVGGElement, EntityNode, EntityNode>) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }
  }, [graphData]);

  useEffect(() => {
    if (graphData && activeTab === 'graph') {
      renderGraph();
    }
  }, [graphData, activeTab, renderGraph]);

  const handleZoomIn = () => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().call(
        d3.zoom<SVGSVGElement, unknown>().scaleBy as any,
        1.3
      );
    }
  };

  const handleZoomOut = () => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().call(
        d3.zoom<SVGSVGElement, unknown>().scaleBy as any,
        0.7
      );
    }
  };

  const handleResetView = () => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().call(
        d3.zoom<SVGSVGElement, unknown>().transform as any,
        d3.zoomIdentity
      );
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="space-y-6 p-6">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6 p-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <GitGraph className="w-7 h-7" />
              角色关系图
            </h1>
            <p className="text-white/60 mt-1">可视化展示角色、场景、道具及其关系网络</p>
          </div>
          <div className="flex items-center gap-3">
            <Select
              value={selectedNovelId}
              onValueChange={setSelectedNovelId}
              options={novels.map(n => ({ value: n.id, label: n.title }))}
              placeholder="选择小说"
            />
            <Button
              variant="outline"
              size="sm"
              className="border-white/20 text-white hover:bg-white/10"
              onClick={loadGraph}
              disabled={!selectedNovelId || loadingGraph}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loadingGraph ? 'animate-spin' : ''}`} />
              刷新
            </Button>
          </div>
        </div>

        {/* Stats */}
        {graphData && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <Users className="w-5 h-5 text-green-400" />
                  <span className="text-2xl font-bold text-white">
                    {graphData.nodes.filter(n => n.entity_type === 'character').length}
                  </span>
                </div>
                <div className="text-white/60 text-sm mt-1">角色</div>
              </CardContent>
            </Card>
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <MapPin className="w-5 h-5 text-blue-400" />
                  <span className="text-2xl font-bold text-white">
                    {graphData.nodes.filter(n => n.entity_type === 'scene').length}
                  </span>
                </div>
                <div className="text-white/60 text-sm mt-1">场景</div>
              </CardContent>
            </Card>
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <Box className="w-5 h-5 text-amber-400" />
                  <span className="text-2xl font-bold text-white">
                    {graphData.nodes.filter(n => n.entity_type === 'prop').length}
                  </span>
                </div>
                <div className="text-white/60 text-sm mt-1">道具</div>
              </CardContent>
            </Card>
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <Link2 className="w-5 h-5 text-purple-400" />
                  <span className="text-2xl font-bold text-white">
                    {graphData.total_edges}
                  </span>
                </div>
                <div className="text-white/60 text-sm mt-1">关系</div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white/5 border border-white/10">
            <TabsTrigger value="graph" className="data-[state=active]:bg-white/10">
              <GitGraph className="w-4 h-4 mr-2" />
              关系图
            </TabsTrigger>
            <TabsTrigger value="nodes" className="data-[state=active]:bg-white/10">
              <Users className="w-4 h-4 mr-2" />
              节点列表
            </TabsTrigger>
            <TabsTrigger value="legend" className="data-[state=active]:bg-white/10">
              图例
            </TabsTrigger>
          </TabsList>

          {/* Graph Tab */}
          <TabsContent value="graph" className="mt-6">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-white text-lg">关系网络图</CardTitle>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-white/60 hover:text-white"
                      onClick={handleZoomOut}
                    >
                      <ZoomOut className="w-4 h-4" />
                    </Button>
                    <span className="text-white/60 text-sm w-16 text-center">
                      {Math.round(zoomLevel * 100)}%
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-white/60 hover:text-white"
                      onClick={handleZoomIn}
                    >
                      <ZoomIn className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-white/60 hover:text-white"
                      onClick={handleResetView}
                    >
                      <Maximize2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {loadingGraph ? (
                  <div className="h-[500px] flex items-center justify-center">
                    <div className="flex flex-col items-center gap-3">
                      <RefreshCw className="w-8 h-8 text-white/40 animate-spin" />
                      <span className="text-white/60">加载图谱中...</span>
                    </div>
                  </div>
                ) : graphData && graphData.nodes.length > 0 ? (
                  <svg
                    ref={svgRef}
                    className="w-full h-[500px] bg-gradient-to-br from-gray-900 to-gray-800 rounded-lg"
                    style={{ cursor: 'grab' }}
                  />
                ) : (
                  <div className="h-[500px] flex items-center justify-center">
                    <div className="text-center">
                      <GitGraph className="w-16 h-16 text-white/20 mx-auto mb-4" />
                      <h3 className="text-lg font-medium text-white/80 mb-2">暂无关系图数据</h3>
                      <p className="text-white/60 mb-4">
                        {selectedNovelId
                          ? '该小说还没有角色或关系数据'
                          : '请先选择一个小说'}
                      </p>
                      {selectedNovelId && (
                        <Button
                          variant="outline"
                          className="border-violet-500/50 text-violet-400 hover:bg-violet-500/10"
                        >
                          <Plus className="w-4 h-4 mr-2" />
                          添加角色
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Nodes List Tab */}
          <TabsContent value="nodes" className="mt-6">
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-6">
                {graphData && graphData.nodes.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {graphData.nodes.map(node => (
                      <div
                        key={node.id}
                        className="bg-white/5 border border-white/10 rounded-lg p-4 hover:border-white/20 cursor-pointer transition-colors"
                        onClick={() => handleNodeClick(node)}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className="w-10 h-10 rounded-full flex items-center justify-center text-lg"
                            style={{ backgroundColor: ENTITY_COLORS[node.entity_type] }}
                          >
                            {node.entity_type === 'character' && '👤'}
                            {node.entity_type === 'scene' && '📍'}
                            {node.entity_type === 'prop' && '📦'}
                            {node.entity_type === 'event' && '⚡'}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h3 className="text-white font-medium truncate">{node.name}</h3>
                            <Badge
                              variant="outline"
                              className="mt-1 text-xs border-white/20"
                            >
                              {node.entity_type === 'character' && '角色'}
                              {node.entity_type === 'scene' && '场景'}
                              {node.entity_type === 'prop' && '道具'}
                              {node.entity_type === 'event' && '事件'}
                            </Badge>
                            {node.description && (
                              <p className="text-white/60 text-sm mt-2 line-clamp-2">
                                {node.description}
                              </p>
                            )}
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-white/60 hover:text-white"
                          >
                            <Eye className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="w-12 h-12 text-white/20 mx-auto mb-4" />
                    <p className="text-white/60">暂无节点数据</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Legend Tab */}
          <TabsContent value="legend" className="mt-6">
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  {/* Entity Types */}
                  <div>
                    <h3 className="text-white font-medium mb-4">实体类型</h3>
                    <div className="space-y-3">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center text-sm"
                          style={{ backgroundColor: ENTITY_COLORS.character }}
                        >
                          👤
                        </div>
                        <div>
                          <div className="text-white">角色 (Character)</div>
                          <div className="text-white/60 text-sm">故事中的主要人物</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center text-sm"
                          style={{ backgroundColor: ENTITY_COLORS.scene }}
                        >
                          📍
                        </div>
                        <div>
                          <div className="text-white">场景 (Scene)</div>
                          <div className="text-white/60 text-sm">故事发生的地点</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center text-sm"
                          style={{ backgroundColor: ENTITY_COLORS.prop }}
                        >
                          📦
                        </div>
                        <div>
                          <div className="text-white">道具 (Prop)</div>
                          <div className="text-white/60 text-sm">物品或装备</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center text-sm"
                          style={{ backgroundColor: ENTITY_COLORS.event }}
                        >
                          ⚡
                        </div>
                        <div>
                          <div className="text-white">事件 (Event)</div>
                          <div className="text-white/60 text-sm">故事情节中的关键事件</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Relation Types */}
                  <div>
                    <h3 className="text-white font-medium mb-4">关系类型</h3>
                    <div className="space-y-3">
                      {Object.entries(RELATION_LABELS).filter(([key]) => key !== 'RELATES_TO' && key !== 'APPEARS_WITH' && key !== 'APPEARS_IN').map(([key, label]) => (
                        <div key={key} className="flex items-center gap-3">
                          <div className="w-4 h-0.5" style={{ backgroundColor: RELATION_COLORS[key] || '#666' }} />
                          <div className="flex-1">
                            <div className="text-white">{label}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Usage Tips */}
                <div className="mt-8 pt-6 border-t border-white/10">
                  <h3 className="text-white font-medium mb-4">操作提示</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-white/60">
                    <div className="flex items-start gap-2">
                      <Move className="w-4 h-4 mt-0.5" />
                      <span>拖拽节点可调整位置</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <ZoomIn className="w-4 h-4 mt-0.5" />
                      <span>滚轮可缩放视图</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <Eye className="w-4 h-4 mt-0.5" />
                      <span>点击节点查看详情</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Detail Dialog */}
        <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
          <DialogContent className="bg-gray-900 border-white/10 text-white max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
                  👤
                </div>
                <div>
                  <div className="text-lg font-medium">
                    {nodeDetail?.name || selectedNode?.name}
                  </div>
                  <Badge variant="outline" className="border-white/20 text-white/80 mt-1">
                    角色
                  </Badge>
                </div>
              </DialogTitle>
            </DialogHeader>
            {nodeDetail && (
              <div className="space-y-6 py-4 max-h-[60vh] overflow-y-auto">
                {/* Avatar */}
                {nodeDetail.avatar_url && (
                  <div className="flex justify-center">
                    <img
                      src={nodeDetail.avatar_url}
                      alt={nodeDetail.name}
                      className="w-32 h-32 rounded-full object-cover border-2 border-white/20"
                    />
                  </div>
                )}

                {/* Description */}
                {nodeDetail.description && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">描述</h4>
                    <p className="text-white leading-relaxed">{nodeDetail.description}</p>
                  </div>
                )}

                {/* Appearance */}
                {nodeDetail.appearance && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">外貌特征</h4>
                    <p className="text-white leading-relaxed">{nodeDetail.appearance}</p>
                  </div>
                )}

                {/* Relations */}
                {nodeDetail.relations && nodeDetail.relations.length > 0 && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">关系</h4>
                    <div className="space-y-2">
                      {nodeDetail.relations.map((rel: any, idx: number) => (
                        <div
                          key={idx}
                          className="flex items-center gap-3 bg-white/5 p-3 rounded-lg"
                        >
                          <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center text-sm">
                            👤
                          </div>
                          <div className="flex-1">
                            <div className="text-white font-medium">{rel.name}</div>
                            <Badge
                              variant="outline"
                              className="text-xs border-white/20 mt-1"
                              style={{
                                borderColor: RELATION_COLORS[rel.relationship] || '#666',
                                color: RELATION_COLORS[rel.relationship] || '#666',
                              }}
                            >
                              {getRelationLabel(rel.relationship)}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Scenes */}
                {nodeDetail.scenes && nodeDetail.scenes.length > 0 && (
                  <div>
                    <h4 className="text-sm text-white/60 mb-2">出现场景</h4>
                    <div className="space-y-2">
                      {nodeDetail.scenes.map((scene: any, idx: number) => (
                        <div key={idx} className="flex items-center gap-3 bg-white/5 p-3 rounded-lg">
                          <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-sm">
                            📍
                          </div>
                          <div className="flex-1">
                            <div className="text-white">
                              {scene.storyboard_id || '未知场景'}
                            </div>
                            {scene.description && (
                              <p className="text-white/60 text-sm">{scene.description}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Connection Status */}
                <div className="text-xs text-white/40 pt-4 border-t border-white/10">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        nodeDetail.is_connected ? 'bg-green-500' : 'bg-red-500'
                      }`}
                    />
                    {nodeDetail.is_connected ? '已同步到图数据库' : '未连接到图数据库'}
                  </div>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </MainLayout>
  );
}
