"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageSkeleton } from "@/components/ui/skeletons";

export default function AdminPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/admin/users");
  }, [router]);

  return (
    <div className="container mx-auto px-4 py-8">
      <PageSkeleton />
    </div>
  );
}
