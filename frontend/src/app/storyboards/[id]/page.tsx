import { redirect } from 'next/navigation';

interface StoryboardDetailRedirectProps {
  params: {
    id: string;
  };
}

export default function StoryboardDetailRedirect({ params }: StoryboardDetailRedirectProps) {
  redirect(`/storyboards?storyboard_id=${encodeURIComponent(params.id)}`);
}
