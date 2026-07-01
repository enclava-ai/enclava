'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { PageSkeleton } from '@/components/ui/skeletons';

export default function ProvidersRedirect() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to the new tab location
    router.replace('/settings/llm?tab=providers');
  }, [router]);

  return (
    <div className="min-h-screen bg-background p-6">
      <PageSkeleton className="mx-auto max-w-6xl" />
    </div>
  );
}
