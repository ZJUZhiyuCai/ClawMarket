"use client";

export const dynamic = "force-dynamic";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { MarketplaceStateBadge } from "@/components/clawmarket/MarketplaceStateBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  createEscrowPayment,
  decideRequesterTask,
  formatMoney,
  getRequesterDashboard,
  rematchMarketplaceTask,
  selectMarketplaceAgent,
  withApiBase,
} from "@/lib/clawmarket-api";

export default function RequesterDashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [disputeNotes, setDisputeNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["requester-dashboard"],
    queryFn: getRequesterDashboard,
  });

  const refreshData = async () => {
    await queryClient.invalidateQueries({ queryKey: ["requester-dashboard"] });
    await queryClient.invalidateQueries({ queryKey: ["supplier-dashboard"] });
    await queryClient.invalidateQueries({ queryKey: ["marketplace-feed"] });
  };

  const selectMutation = useMutation({
    mutationFn: ({ taskId, agentId }: { taskId: string; agentId: string }) =>
      selectMarketplaceAgent(taskId, agentId),
    onSuccess: refreshData,
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Unable to select supplier.");
    },
  });

  const rematchMutation = useMutation({
    mutationFn: (taskId: string) => rematchMarketplaceTask(taskId),
    onSuccess: refreshData,
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Unable to refresh matches.");
    },
  });

  const paymentMutation = useMutation({
    mutationFn: ({ taskId, amount, currency }: { taskId: string; amount: number; currency: string }) =>
      createEscrowPayment(taskId, amount, currency),
    onSuccess: refreshData,
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Unable to create escrow.");
    },
  });

  const decisionMutation = useMutation({
    mutationFn: ({ taskId, approve, comment }: { taskId: string; approve: boolean; comment?: string }) =>
      decideRequesterTask(taskId, approve, comment),
    onSuccess: async () => {
      await refreshData();
      setDisputeNotes({});
    },
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Unable to update task.");
    },
  });

  const data = query.data;

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to manage your marketplace requests.",
        forceRedirectUrl: "/requester",
      }}
      title="Requester Console"
      description="Publish work, compare the ranked supplier matches, fund escrow, and accept or dispute deliveries."
      headerActions={<Button onClick={() => router.push("/tasks/new")}>Publish New Task</Button>}
    >
      {error ? (
        <div className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardContent className="py-6">
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Total tasks</div>
            <div className="mt-3 text-3xl font-semibold text-slate-900">
              {data?.tasks.length ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-6">
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Completed cases</div>
            <div className="mt-3 text-3xl font-semibold text-slate-900">
              {data?.history_cases.length ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-6">
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Escrow funded</div>
            <div className="mt-3 text-3xl font-semibold text-slate-900">
              {
                (data?.tasks ?? []).filter((entry) =>
                  ["awaiting_supplier_approval", "executing", "awaiting_acceptance", "completed", "disputed"].includes(
                    entry.task.marketplace_state ?? "",
                  ),
                ).length
              }
            </div>
          </CardContent>
        </Card>
      </div>

      <section className="mt-6 space-y-4">
        <h2 className="font-heading text-xl font-semibold text-slate-900">My tasks</h2>
        <div className="grid gap-4">
          {(data?.tasks ?? []).map((entry) => (
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
              <CardContent className="space-y-5">
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
                    Deadline
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

                {entry.task.marketplace_state === "open" || entry.task.marketplace_state === "awaiting_payment" ? (
                  <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h4 className="font-medium text-slate-900">Top supplier matches</h4>
                        <p className="text-sm text-slate-500">
                          Choose one supplier to continue into escrow and execution.
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        onClick={() => rematchMutation.mutate(entry.task.id)}
                        disabled={rematchMutation.isPending}
                      >
                        {rematchMutation.isPending ? "Refreshing..." : "Re-run Matching"}
                      </Button>
                    </div>
                    <div className="grid gap-3 xl:grid-cols-3">
                      {entry.task.marketplace_match_candidates.map((candidate) => {
                        const isSelected = entry.task.marketplace_listing_agent_id === candidate.agent_id;
                        return (
                          <div
                            key={candidate.agent_id}
                            className={`rounded-2xl border px-4 py-4 ${
                              isSelected
                                ? "border-blue-300 bg-blue-50"
                                : "border-slate-200 bg-white"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="font-medium text-slate-900">{candidate.name}</p>
                                <p className="text-xs text-slate-500">
                                  Score {candidate.score.toFixed(1)} · Load {candidate.current_load}/
                                  {candidate.max_concurrency}
                                </p>
                              </div>
                              <p className="text-sm font-semibold text-slate-900">
                                {formatMoney(
                                  Number(candidate.pricing.amount ?? 0),
                                  String(candidate.pricing.currency ?? "CNY"),
                                )}
                              </p>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {[...candidate.skill_tags, ...candidate.skills].slice(0, 5).map((tag) => (
                                <span
                                  key={`${candidate.agent_id}-${tag}`}
                                  className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                            <ul className="mt-3 space-y-1 text-sm text-slate-600">
                              {candidate.reasons.slice(0, 3).map((reason) => (
                                <li key={reason}>• {reason}</li>
                              ))}
                            </ul>
                            <div className="mt-4 flex gap-2">
                              <Button
                                variant={isSelected ? "outline" : "primary"}
                                className="flex-1"
                                onClick={() =>
                                  selectMutation.mutate({
                                    taskId: entry.task.id,
                                    agentId: candidate.agent_id,
                                  })
                                }
                                disabled={selectMutation.isPending}
                              >
                                {isSelected ? "Selected" : "Select Supplier"}
                              </Button>
                              {isSelected && entry.task.marketplace_state === "awaiting_payment" ? (
                                <Button
                                  className="flex-1"
                                  onClick={() =>
                                    paymentMutation.mutate({
                                      taskId: entry.task.id,
                                      amount: entry.task.marketplace_budget_amount ?? 0,
                                      currency: entry.task.marketplace_budget_currency ?? "cny",
                                    })
                                  }
                                  disabled={paymentMutation.isPending}
                                >
                                  {paymentMutation.isPending ? "Funding..." : "Fund Escrow"}
                                </Button>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {entry.task.marketplace_state === "awaiting_acceptance" ? (
                  <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
                    <div className="space-y-3">
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                        <p className="font-medium text-slate-900">Supplier note</p>
                        <p className="mt-2 whitespace-pre-wrap">{entry.task.marketplace_delivery_note}</p>
                      </div>
                      {entry.task.marketplace_delivery_artifacts.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {entry.task.marketplace_delivery_artifacts.map((file) => (
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
                      <Textarea
                        rows={3}
                        value={disputeNotes[entry.task.id] ?? ""}
                        onChange={(event) =>
                          setDisputeNotes((current) => ({
                            ...current,
                            [entry.task.id]: event.target.value,
                          }))
                        }
                        placeholder="If something is off, describe the gap before opening arbitration."
                      />
                    </div>
                    <div className="flex flex-col gap-3">
                      <Button
                        onClick={() =>
                          decisionMutation.mutate({
                            taskId: entry.task.id,
                            approve: true,
                          })
                        }
                        disabled={decisionMutation.isPending}
                      >
                        Accept Delivery
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() =>
                          decisionMutation.mutate({
                            taskId: entry.task.id,
                            approve: false,
                            comment: disputeNotes[entry.task.id] ?? "Open arbitration.",
                          })
                        }
                        disabled={decisionMutation.isPending}
                      >
                        Open Arbitration
                      </Button>
                    </div>
                  </div>
                ) : null}

                {entry.task.marketplace_state === "completed" && entry.payment ? (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                    Escrow released. Supplier payout: {formatMoney(entry.payment.payee_amount, "CNY")}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="mt-8 space-y-4">
        <h2 className="font-heading text-xl font-semibold text-slate-900">History cases</h2>
        <div className="grid gap-4 lg:grid-cols-2">
          {(data?.history_cases ?? []).map((entry) => (
            <Card key={`history-${entry.task.id}`}>
              <CardHeader className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-heading text-lg font-semibold text-slate-900">
                    {entry.task.title}
                  </h3>
                  <MarketplaceStateBadge state={entry.task.marketplace_state} />
                </div>
                <p className="text-sm text-slate-600">{entry.task.description}</p>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="text-sm text-slate-600">
                  Supplier: <span className="font-medium text-slate-900">{entry.listing_agent?.name ?? "—"}</span>
                </div>
                <div className="text-sm text-slate-600">
                  Budget:{" "}
                  <span className="font-medium text-slate-900">
                    {formatMoney(
                      entry.task.marketplace_budget_amount,
                      entry.task.marketplace_budget_currency ?? "CNY",
                    )}
                  </span>
                </div>
                {entry.task.marketplace_screenshots.length > 0 ? (
                  <a
                    href={withApiBase(entry.task.marketplace_screenshots[0].download_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-blue-700"
                  >
                    Open saved execution screenshot
                  </a>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </DashboardPageLayout>
  );
}
