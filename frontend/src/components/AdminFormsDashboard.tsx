"use client";

import { useState } from "react";

import { PdfFormUpload } from "@/components/PdfFormUpload";
import { ReviewQueue } from "@/components/ReviewQueue";

export function AdminFormsDashboard() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-zinc-200 bg-white p-4">
        <div>
          <p className="font-medium text-zinc-950">Forms admin access</p>
          <p className="text-sm text-zinc-500">
            Upload and review actions require an admin JWT.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <PdfFormUpload
          onUploaded={() => setRefreshKey((current) => current + 1)}
        />
        <ReviewQueue refreshKey={refreshKey} />
      </div>
    </div>
  );
}
