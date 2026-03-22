"use client";

export const dynamic = "force-dynamic";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { MarketplaceStateBadge } from "@/components/clawmarket/MarketplaceStateBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  formatMoney,
  getArbitrationCases,
  resolveArbitrationCase,
  withApiBase,
} from "@/lib/clawmarket-api";

export default function ArbitrationPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["arbitration-cases"],
    queryFn: getArbitrationCases,
  });

  const mutation = useMutation({
    mutationFn: ({
      taskId,
      decision,
    }: {
      taskId: string;
      decision: "refund" | "release_supplier";
    }) => resolveArbitrationCase(taskId, decision),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["arbitration-cases"] });
      await queryClient.invalidateQueries({ queryKey: ["requester-dashboard"] });
      await queryClient.invalidateQueries({ queryKey: ["supplier-dashboard"] });
    },
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Unable to resolve case.");
    },
  });

  const cases = query.data ?? [];

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to review arbitration cases.",
        forceRedirectUrl: "/admin/arbitration",
      }}
      title="Arbitration"
      description="Review marketplace logs, saved screenshots, and payment state before deciding refund or supplier release."
    >
      {error ? (
        <div className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="grid gap-5">
        {cases.map((entry) => (
          <Card key={entry.task.task.id}>
            <CardHeader className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {entry.task.task.marketplace_task_type}
                  </p>
                  <h2 className="font-heading text-xl font-semibold text-slate-900">
                    {entry.task.task.title}
                  </h2>
                  <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
                    {entry.task.task.description}
                  </p>
                </div>
                <MarketplaceStateBadge state={entry.task.task.marketplace_state} />
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-3 lg:grid-cols-4">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  Request budget
                  <div className="mt-2 text-lg font-semibold text-slate-900">
                    {formatMoney(
                      entry.task.task.marketplace_budget_amount,
                      entry.task.task.marketplace_budget_currency ?? "CNY",
                    )}
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  Supplier
                  <div className="mt-2 text-sm font-semibold text-slate-900">
                    {entry.task.listing_agent?.name ?? "Unassigned"}
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  Escrow
                  <div className="mt-2 text-sm font-semibold text-slate-900">
                    {entry.task.payment?.status ?? "No payment"}
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  Supplier payout
                  <div className="mt-2 text-lg font-semibold text-slate-900">
                    {formatMoney(entry.task.payment?.payee_amount, "CNY")}
                  </div>
                </div>
              </div>

              <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
                <div className="space-y-3">
                  <h3 className="font-medium text-slate-900">Timeline</h3>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="space-y-3">
                      {entry.timeline.map((event) => (
                        <div key={`${event.kind}-${event.created_at}-${event.message}`} className="border-b border-slate-200 pb-3 last:border-b-0 last:pb-0">
                          <div className="flex items-center justify-between gap-3 text-xs uppercase tracking-[0.16em] text-slate-500">
                            <span>{event.event_type}</span>
                            <span>{new Date(event.created_at).toLocaleString()}</span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-700">{event.message}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <h3 className="font-medium text-slate-900">Evidence</h3>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="space-y-2">
                      {entry.task.task.marketplace_screenshots.map((file) => (
                        <a
                          key={file.file_id}
                          href={withApiBase(file.download_url)}
                          target="_blank"
                          rel="noreferrer"
                          className="block rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:border-blue-300 hover:text-blue-700"
                        >
                          Screenshot: {file.name}
                        </a>
                      ))}
                      {entry.task.task.marketplace_delivery_artifacts.map((file) => (
                        <a
                          key={file.file_id}
                          href={withApiBase(file.download_url)}
                          target="_blank"
                          rel="noreferrer"
                          className="block rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:border-blue-300 hover:text-blue-700"
                        >
                          Artifact: {file.name}
                        </a>
                      ))}
                    </div>
                  </div>

                  <div className="flex flex-col gap-3">
                    <Button
                      onClick={() =>
                        mutation.mutate({
                          taskId: entry.task.task.id,
                          decision: "release_supplier",
                        })
                      }
                      disabled={mutation.isPending}
                    >
                      Release Supplier Payment
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() =>
                        mutation.mutate({
                          taskId: entry.task.task.id,
                          decision: "refund",
                        })
                      }
                      disabled={mutation.isPending}
                    >
                      Refund Requester
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {!query.isLoading && cases.length === 0 ? (
        <Card className="mt-5">
          <CardContent className="py-10 text-center text-slate-500">
            No disputed or failed cases are waiting for arbitration.
          </CardContent>
        </Card>
      ) : null}
    </DashboardPageLayout>
  );
}
