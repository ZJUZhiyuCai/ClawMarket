"use client";

export const dynamic = "force-dynamic";

import { useQuery } from "@tanstack/react-query";

import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { MarketplaceStateBadge } from "@/components/clawmarket/MarketplaceStateBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatMoney, getMarketplaceTasks, withApiBase } from "@/lib/clawmarket-api";

export default function MarketplacePage() {
  const query = useQuery({
    queryKey: ["marketplace-feed"],
    queryFn: getMarketplaceTasks,
  });

  const tasks = query.data ?? [];

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to browse ClawMarket.",
        forceRedirectUrl: "/marketplace",
      }}
      title="Marketplace"
      description="Open tasks, live supplier matches, and work that is already moving through the human-in-the-loop pipeline."
    >
      <div className="grid gap-5 xl:grid-cols-2">
        {tasks.map((entry) => (
          <Card key={entry.task.id}>
            <CardHeader className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                    {entry.task.marketplace_task_type}
                  </p>
                  <h2 className="font-heading text-xl font-semibold text-slate-900">
                    {entry.task.title}
                  </h2>
                </div>
                <MarketplaceStateBadge state={entry.task.marketplace_state} />
              </div>
              <p className="text-sm leading-6 text-slate-600">{entry.task.description}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Budget</div>
                  <div className="mt-2 text-lg font-semibold text-slate-900">
                    {formatMoney(
                      entry.task.marketplace_budget_amount,
                      entry.task.marketplace_budget_currency ?? "CNY",
                    )}
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Deadline</div>
                  <div className="mt-2 text-sm font-medium text-slate-900">
                    {entry.task.due_at ? new Date(entry.task.due_at).toLocaleString() : "Flexible"}
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Top Matches</div>
                  <div className="mt-2 text-lg font-semibold text-slate-900">
                    {entry.task.marketplace_match_candidates.length}
                  </div>
                </div>
              </div>

              {entry.task.marketplace_attachments.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Attachments
                  </p>
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
                </div>
              ) : null}

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Ranked Suppliers
                </p>
                <div className="grid gap-3">
                  {entry.task.marketplace_match_candidates.map((candidate) => (
                    <div
                      key={candidate.agent_id}
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
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
                        {[...candidate.skill_tags, ...candidate.skills].slice(0, 6).map((tag) => (
                          <span
                            key={`${candidate.agent_id}-${tag}`}
                            className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                      <ul className="mt-3 space-y-1 text-sm text-slate-600">
                        {candidate.reasons.map((reason) => (
                          <li key={reason}>• {reason}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {!query.isLoading && tasks.length === 0 ? (
        <Card className="mt-5">
          <CardContent className="py-10 text-center text-slate-500">
            No public tasks yet. Publish the first task from the requester console.
          </CardContent>
        </Card>
      ) : null}
    </DashboardPageLayout>
  );
}
