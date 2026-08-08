import { redirect } from 'next/navigation';

export default async function StoryboardDetailRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/storyboards?storyboard_id=${encodeURIComponent(id)}`);
}
