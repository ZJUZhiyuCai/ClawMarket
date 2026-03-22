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
import { registerSupplierAgent } from "@/lib/clawmarket-api";

const DEFAULT_AVAILABILITY = "mon 09:00-18:00\nwed 09:00-18:00\nfri 09:00-18:00";

const parseAvailability = (raw: string) =>
  raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [day = "", hours = ""] = line.split(/\s+/, 2);
      const [start = "09:00", end = "18:00"] = hours.split("-", 2);
      return { day, start, end };
    })
    .filter((item) => item.day);

const parseTags = (raw: string) =>
  raw
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

export default function RegisterSupplierAgentPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isSignedIn } = useAuth();

  const [gatewayName, setGatewayName] = useState("");
  const [gatewayUrl, setGatewayUrl] = useState("");
  const [authToken, setAuthToken] = useState("");
  const [workspaceRoot, setWorkspaceRoot] = useState("/workspace");
  const [price, setPrice] = useState("299");
  const [pricingMode, setPricingMode] = useState<"fixed" | "hourly">("fixed");
  const [maxConcurrency, setMaxConcurrency] = useState("1");
  const [skillTags, setSkillTags] = useState("crawl, excel, report");
  const [availability, setAvailability] = useState(DEFAULT_AVAILABILITY);
  const [allowInsecureTls, setAllowInsecureTls] = useState(false);
  const [disableDevicePairing, setDisableDevicePairing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      registerSupplierAgent({
        gateway_name: gatewayName.trim(),
        gateway_url: gatewayUrl.trim(),
        auth_token: authToken.trim() || null,
        allow_insecure_tls: allowInsecureTls,
        disable_device_pairing: disableDevicePairing,
        workspace_root: workspaceRoot.trim(),
        pricing: {
          mode: pricingMode,
          amount: Math.round(Number(price || "0") * 100),
          currency: "cny",
        },
        availability: parseAvailability(availability),
        max_concurrency: Math.max(1, Number.parseInt(maxConcurrency || "1", 10)),
        skill_tags: parseTags(skillTags),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["supplier-dashboard"] });
      await queryClient.invalidateQueries({ queryKey: ["supplier-agents"] });
      router.push("/supplier");
    },
    onError: (mutationError) => {
      setError(mutationError instanceof Error ? mutationError.message : "Registration failed.");
    },
  });

  const canSubmit = useMemo(
    () =>
      Boolean(gatewayName.trim()) &&
      Boolean(gatewayUrl.trim()) &&
      Boolean(workspaceRoot.trim()) &&
      Number(price) > 0,
    [gatewayName, gatewayUrl, workspaceRoot, price],
  );

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to register your supplier runtime.",
        forceRedirectUrl: "/agents/register",
      }}
      title="Register Supplier Agent"
      description="Verify your OpenClaw Gateway, import installed skills, and publish your pricing profile."
    >
      <Card className="max-w-4xl">
        <CardHeader>
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Supplier Onboarding
            </p>
            <h2 className="font-heading text-2xl font-semibold text-slate-900">
              Turn your OpenClaw instance into a marketplace worker
            </h2>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Gateway name</label>
              <Input value={gatewayName} onChange={(event) => setGatewayName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Gateway URL</label>
              <Input value={gatewayUrl} onChange={(event) => setGatewayUrl(event.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Gateway token</label>
              <Input
                value={authToken}
                onChange={(event) => setAuthToken(event.target.value)}
                placeholder="Optional bearer token"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Workspace root</label>
              <Input value={workspaceRoot} onChange={(event) => setWorkspaceRoot(event.target.value)} />
            </div>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Pricing mode</label>
              <select
                className="h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
                value={pricingMode}
                onChange={(event) => setPricingMode(event.target.value as "fixed" | "hourly")}
              >
                <option value="fixed">Per task</option>
                <option value="hourly">Per hour</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Price (CNY)</label>
              <Input
                type="number"
                min="1"
                value={price}
                onChange={(event) => setPrice(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Max concurrency</label>
              <Input
                type="number"
                min="1"
                max="20"
                value={maxConcurrency}
                onChange={(event) => setMaxConcurrency(event.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-900">Skill tags</label>
              <Input
                value={skillTags}
                onChange={(event) => setSkillTags(event.target.value)}
                placeholder="crawl, excel, report"
              />
            </div>
            <div className="flex flex-wrap gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={allowInsecureTls}
                  onChange={(event) => setAllowInsecureTls(event.target.checked)}
                />
                Allow insecure TLS
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={disableDevicePairing}
                  onChange={(event) => setDisableDevicePairing(event.target.checked)}
                />
                Disable device pairing
              </label>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-900">Availability</label>
            <Textarea
              value={availability}
              onChange={(event) => setAvailability(event.target.value)}
              rows={4}
              placeholder="mon 09:00-18:00"
            />
            <p className="text-xs text-slate-500">
              One row per window, for example: <span className="font-mono">mon 09:00-18:00</span>
            </p>
          </div>

          {error ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="max-w-2xl text-sm text-slate-600">
              Registration validates gateway connectivity, imports installed ClawHub skills, and
              publishes this instance as a low-sensitivity digital worker with human approval on every order.
            </p>
            <Button
              onClick={() => mutation.mutate()}
              disabled={!isSignedIn || mutation.isPending || !canSubmit}
            >
              {mutation.isPending ? "Registering..." : "Publish Supplier Agent"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </DashboardPageLayout>
  );
}
