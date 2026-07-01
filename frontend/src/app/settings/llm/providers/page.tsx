'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function ProvidersRedirect() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to the new tab location
    router.replace('/settings/llm?tab=providers');
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-empire-gold"></div>
    </div>
  );
}
