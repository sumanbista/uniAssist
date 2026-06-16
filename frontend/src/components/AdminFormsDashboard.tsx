"use client";

import { useState } from "react";

import { PdfFormUpload } from "@/components/PdfFormUpload";
import { ReviewQueue } from "@/components/ReviewQueue";
import { RoleSwitcher } from "@/components/RoleSwitcher";
import { UserRole } from "@/lib/api";

export function AdminFormsDashboard() {
  const [role, setRole] = useState<UserRole>("admin");
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium text-zinc-950">Forms admin mode</p>
          <p className="text-sm text-zinc-500">
            Use Admin mode to upload PDFs and review pending forms.
          </p>
        </div>
        <RoleSwitcher value={role} onChange={setRole} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <PdfFormUpload
          onUploaded={() => setRefreshKey((current) => current + 1)}
          role={role}
        />
        <ReviewQueue refreshKey={refreshKey} role={role} />
      </div>
    </div>
  );
}
