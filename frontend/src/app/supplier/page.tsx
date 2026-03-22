"use client";

export const dynamic = "force-dynamic";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { MarketplaceStateBadge } from "@/components/clawmarket/MarketplaceStateBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  approveSupplierTask,
  failMarketplaceTask,
  fileToBase64,
  fileToUploadPayload,
  formatMoney,
  getSupplierDashboard,
  importSupplierSkills,
  submitMarketplaceDelivery,
  withApiBase,
} from "@/lib/clawmarket-api";

export default function SupplierDashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [deliveryNotes, setDeliveryNotes] = useState<Record<string, string>>({});
  const [deliveryFiles, setDeliveryFiles] = useState<Record<string, File[]>>({});
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["supplier-dashboard"],
    queryFn: getSupplierDashboard,
  });

  const refreshData = async () => {
    await queryClient.invalidateQueries({ queryKey: ["supplier-dashboard"] });
    await queryClient.invalidateQueries({ queryKey: ["requester-dashboard"] });
    await queryClient.invalidateQueries({ queryKey: ["marketplace-feed"] });
  };

  const approveMutation = useMutation({
    mutationFn: ({ taskId, approve }: { taskId: string; approve: boolean }) =>
      approveSupplierTask(taskId, approve),
    onSuccess: refreshData,
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Unable to update approval.");
    },
  });

  const importMutation = useMutation({
    mutationFn: (agentId: string) => importSupplierSkills(agentId),
    onSuccess: refreshData,
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Unable to import skills.");
    },
  });

  const submitMutation = useMutation({
    mutationFn: async (taskId: string) => {
      const note = deliveryNotes[taskId]?.trim() ?? "";
      const files = deliveryFiles[taskId] ?? [];
      const uploads = await Promise.all(
        files.map(async (file) => fileToUploadPayload(file, await fileToBase64(file))),
      );
      return submitMarketplaceDelivery(taskId, note, uploads);
    },
    onSuccess: async () => {
      await refreshData();
      setDeliveryNotes({});
      setDeliveryFiles({});
    },
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Unable to submit delivery.");
    },
  });

  const failMutation = useMutation({
    mutationFn: ({ taskId, reason }: { taskId: string; reason: string }) =>
      failMarketplaceTask(taskId, reason),
    onSuccess: refreshData,
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Unable to mark task failed.");
    },
  });

  const data = query.data;

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to manage your supplier agents.",
        forceRedirectUrl: "/supplier",
      }}
      title="Supplier Console"
      description="Approve new orders, monitor current workload, import skills from ClawHub, and submit delivery packages."
      headerActions={<Button onClick={() => router.push("/agents/register")}>Register Agent</Button>}
    >
      {error ? (
        <div className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardContent className="py-6">
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Released income</div>
            <div className="mt-3 text-3xl font-semibold text-slate-900">
              {formatMoney(data?.income_released_amount, "CNY")}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-6">
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Pending income</div>
            <div className="mt-3 text-3xl font-semibold text-slate-900">
              {formatMoney(data?.income_pending_amount, "CNY")}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-6">
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Active orders</div>
            <div className="mt-3 text-3xl font-semibold text-slate-900">
              {data?.active_tasks.length ?? 0}
            </div>
          </CardContent>
        </Card>
      </div>

      <section className="mt-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-xl font-semibold text-slate-900">My digital employees</h2>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {(data?.agents ?? []).map((item) => (
            <Card key={item.agent.id}>
              <CardHeader className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-heading text-xl font-semibold text-slate-900">
                      {item.agent.name}
                    </p>
                    <p className="text-sm text-slate-500">{item.agent.gateway_url}</p>
                  </div>
                  <MarketplaceStateBadge
                    state={item.gateway_connected ? "executing" : "failed"}
                  />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    Active orders
                    <div className="mt-2 text-xl font-semibold text-slate-900">{item.active_tasks}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    Completed
                    <div className="mt-2 text-xl font-semibold text-slate-900">{item.completed_tasks}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    Revenue
                    <div className="mt-2 text-xl font-semibold text-slate-900">
                      {formatMoney(item.total_revenue_amount, "CNY")}
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {item.imported_skills.map((skill) => (
                    <span
                      key={`${item.agent.id}-${skill}`}
                      className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
                <Button
                  variant="outline"
                  onClick={() => importMutation.mutate(item.agent.id)}
                  disabled={importMutation.isPending}
                >
                  {importMutation.isPending ? "Importing..." : "Import Skills from ClawHub"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="mt-8 space-y-4">
        <h2 className="font-heading text-xl font-semibold text-slate-900">Current tasks</h2>
        <div className="grid gap-4">
          {(data?.active_tasks ?? []).map((entry) => (
            <Card key={entry.task.id}>
              <CardHeader className="space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {entry.task.marketplace_task_type}
                    </p>
                    <h3 className="font-heading text-xl font-semibold text-slate-900">
                      {entry.task.title}
                    </h3>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                      {entry.task.description}
                    </p>
                  </div>
                  <MarketplaceStateBadge state={entry.task.marketplace_state} />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    Budget
                    <div className="mt-2 text-xl font-semibold text-slate-900">
                      {formatMoney(
                        entry.task.marketplace_budget_amount,
                        entry.task.marketplace_budget_currency ?? "CNY",
                      )}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    Due
                    <div className="mt-2 text-sm font-medium text-slate-900">
                      {entry.task.due_at ? new Date(entry.task.due_at).toLocaleString() : "Flexible"}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    Escrow
                    <div className="mt-2 text-sm font-medium text-slate-900">
                      {entry.payment?.status ?? "Not funded"}
                    </div>
                  </div>
                </div>

                {entry.task.marketplace_attachments.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {entry.task.marketplace_attachments.map((file) => (
                      <a
                        key={file.file_id}
                        href={withApiBase(file.download_url)}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:border-blue-300 hover:text-blue-700"
                      >
                        {file.name}
                      </a>
                    ))}
                  </div>
                ) : null}

                {entry.task.marketplace_state === "awaiting_supplier_approval" ? (
                  <div className="flex flex-wrap gap-3">
                    <Button
                      onClick={() => approveMutation.mutate({ taskId: entry.task.id, approve: true })}
                      disabled={approveMutation.isPending}
                    >
                      Approve Execution
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => approveMutation.mutate({ taskId: entry.task.id, approve: false })}
                      disabled={approveMutation.isPending}
                    >
                      Reject Order
                    </Button>
                  </div>
                ) : null}

                {entry.task.marketplace_state === "executing" ? (
                  <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
                    <div className="space-y-3">
                      <Textarea
                        rows={4}
                        value={deliveryNotes[entry.task.id] ?? ""}
                        onChange={(event) =>
                          setDeliveryNotes((current) => ({
                            ...current,
                            [entry.task.id]: event.target.value,
                          }))
                        }
                        placeholder="Summarize what you completed, assumptions made, and how the requester should review it."
                      />
                      <Input
                        type="file"
                        multiple
                        onChange={(event) =>
                          setDeliveryFiles((current) => ({
                            ...current,
                            [entry.task.id]: Array.from(event.target.files ?? []),
                          }))
                        }
                      />
                    </div>
                    <div className="flex flex-col gap-3">
                      <Button
                        onClick={() => submitMutation.mutate(entry.task.id)}
                        disabled={
                          submitMutation.isPending || !(deliveryNotes[entry.task.id] ?? "").trim()
                        }
                      >
                        {submitMutation.isPending ? "Submitting..." : "Submit for Acceptance"}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() =>
                          failMutation.mutate({
                            taskId: entry.task.id,
                            reason: "Supplier reported execution failure.",
                          })
                        }
                        disabled={failMutation.isPending}
                      >
                        Mark Failed + Refund
                      </Button>
                    </div>
                  </div>
                ) : null}

                {entry.task.marketplace_screenshots.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Saved screenshots
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {entry.task.marketplace_screenshots.map((file) => (
                        <a
                          key={file.file_id}
                          href={withApiBase(file.download_url)}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
                        >
                          {file.name}
                        </a>
                      ))}
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </DashboardPageLayout>
  );
}
