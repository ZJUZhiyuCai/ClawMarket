import { cn } from "@/lib/utils";

const LABELS: Record<string, string> = {
  open: "Open",
  awaiting_payment: "Awaiting Escrow",
  awaiting_supplier_approval: "Awaiting Supplier Approval",
  executing: "Executing",
  awaiting_acceptance: "Awaiting Acceptance",
  completed: "Completed",
  failed: "Failed",
  disputed: "Disputed",
  refunded: "Refunded",
};

const STYLES: Record<string, string> = {
  open: "border-sky-200 bg-sky-50 text-sky-700",
  awaiting_payment: "border-amber-200 bg-amber-50 text-amber-700",
  awaiting_supplier_approval: "border-orange-200 bg-orange-50 text-orange-700",
  executing: "border-blue-200 bg-blue-50 text-blue-700",
  awaiting_acceptance: "border-violet-200 bg-violet-50 text-violet-700",
  completed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  failed: "border-rose-200 bg-rose-50 text-rose-700",
  disputed: "border-red-200 bg-red-50 text-red-700",
  refunded: "border-slate-200 bg-slate-100 text-slate-700",
};

export function MarketplaceStateBadge({ state }: { state?: string | null }) {
  const resolvedState = state ?? "open";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold tracking-wide",
        STYLES[resolvedState] ?? "border-slate-200 bg-slate-100 text-slate-700",
      )}
    >
      {LABELS[resolvedState] ?? resolvedState}
    </span>
  );
}
