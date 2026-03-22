"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/clerk";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  createMarketplaceTask,
  fileToBase64,
  fileToUploadPayload,
  type TaskType,
} from "@/lib/clawmarket-api";

export default function NewMarketplaceTaskPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isSignedIn } = useAuth();

  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("499");
  const [deadlineAt, setDeadlineAt] = useState("");
  const [taskType, setTaskType] = useState<TaskType>("crawl");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [publicMarket, setPublicMarket] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const uploadPayloads = await Promise.all(
        attachments.map(async (file) => fileToUploadPayload(file, await fileToBase64(file))),
      );
      return createMarketplaceTask({
        description: description.trim(),
        budget_amount: Math.round(Number(budget || "0") * 100),
        deadline_at: new Date(deadlineAt).toISOString(),
        task_type: taskType,
        attachments: uploadPayloads,
        public_market: publicMarket,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["requester-dashboard"] });
      await queryClient.invalidateQueries({ queryKey: ["marketplace-feed"] });
      router.push("/requester");
    },
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Task creation failed.");
    },
  });

  const canSubmit = useMemo(
    () => Boolean(description.trim()) && Number(budget) > 0 && Boolean(deadlineAt),
    [description, budget, deadlineAt],
  );

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to publish a marketplace task.",
        forceRedirectUrl: "/tasks/new",
      }}
      title="Publish Task"
      description="Describe the work, upload lightweight inputs, and let ClawMarket rank the best supplier agents."
    >
      <Card className="max-w-4xl">
        <CardHeader>
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Requester Flow
            </p>
            <h2 className="font-heading text-2xl font-semibold text-slate-900">
              Post a low-sensitivity task
            </h2>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-900">Task description</label>
            <Textarea
              rows={8}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Example: Crawl the top 50 AI agency landing pages, extract pricing and services into Excel, then generate a short comparison report."
            />
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Task type</label>
              <select
                className="h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
                value={taskType}
                onChange={(event) => setTaskType(event.target.value as TaskType)}
              >
                <option value="crawl">crawl</option>
                <option value="excel">excel</option>
                <option value="report">report</option>
                <option value="code">code</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Budget (CNY)</label>
              <Input
                type="number"
                min="1"
                value={budget}
                onChange={(event) => setBudget(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Deadline</label>
              <Input
                type="datetime-local"
                value={deadlineAt}
                onChange={(event) => setDeadlineAt(event.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-900">Attachments</label>
            <Input
              type="file"
              multiple
              onChange={(event) => setAttachments(Array.from(event.target.files ?? []))}
            />
            <div className="flex flex-wrap gap-2">
              {attachments.map((file) => (
                <span
                  key={`${file.name}-${file.size}`}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
                >
                  {file.name}
                </span>
              ))}
            </div>
          </div>

          <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={publicMarket}
              onChange={(event) => setPublicMarket(event.target.checked)}
            />
            Publish this task to the public market feed
          </label>

          {error ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="max-w-2xl text-sm text-slate-600">
              Allowed scope for MVP: web crawling, Excel cleanup, API calls, and report/code generation.
              Sensitive permissions, email access, and local file reads are explicitly blocked.
            </div>
            <Button
              onClick={() => mutation.mutate()}
              disabled={!isSignedIn || mutation.isPending || !canSubmit}
            >
              {mutation.isPending ? "Publishing..." : "Publish Task"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </DashboardPageLayout>
  );
}
