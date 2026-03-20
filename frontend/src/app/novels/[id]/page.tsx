// 动态路由修复 - 重定向到列表页
import { redirect } from 'next/navigation';

export default function NovelDetailPage({ params }: { params: { id: string } }) {
  redirect(`/novels?highlight=${params.id}`);
}