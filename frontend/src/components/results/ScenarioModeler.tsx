"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Sliders, Plus, TrendingUp } from "lucide-react";
import type { DeferrableEstimate } from "@/lib/types";

interface ScenarioModelerProps {
  baselineRunwayDays: number;
  dailyBurn: number;
  cashOnHand: number;
  deferrableEstimates: DeferrableEstimate[];
}

export function ScenarioModeler({
  baselineRunwayDays,
  dailyBurn,
  deferrableEstimates,
}: ScenarioModelerProps) {
  // Toggle state for each deferrable action
  const [toggles, setToggles] = useState<Record<string, boolean>>({});

  const toggle = (category: string) => {
    setToggles((prev) => ({ ...prev, [category]: !prev[category] }));
  };

  // Calculate extended runway
  const { totalGain, extendedRunway, segments } = useMemo(() => {
    let gain = 0;
    const segs: { category: string; days: number; active: boolean }[] = [];

    for (const d of deferrableEstimates) {
      const active = toggles[d.category] ?? false;
      if (active) gain += d.estimated_savings_days;
      segs.push({
        category: d.category,
        days: d.estimated_savings_days,
        active,
      });
    }

    return {
      totalGain: gain,
      extendedRunway: baselineRunwayDays + gain,
      segments: segs,
    };
  }, [toggles, deferrableEstimates, baselineRunwayDays]);

  // Bar chart scaling
  const maxDays = Math.max(
    extendedRunway,
    baselineRunwayDays +
      deferrableEstimates.reduce((s, d) => s + d.estimated_savings_days, 0),
    60
  );

  const baselinePercent = Math.min(100, (baselineRunwayDays / maxDays) * 100);
  const gainPercent = Math.min(
    100 - baselinePercent,
    (totalGain / maxDays) * 100
  );

  const baseColor =
    baselineRunwayDays < 14
      ? "bg-danger"
      : baselineRunwayDays < 30
        ? "bg-amber"
        : "bg-success/60";

  if (!deferrableEstimates || deferrableEstimates.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.6, duration: 0.5 }}
    >
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <Sliders className="h-5 w-5 text-amber" />
          <h2 className="text-lg font-bold text-foreground tracking-tight">
            What-If Scenario Modeler
          </h2>
        </div>
        <p className="text-xs text-muted-foreground mt-1 ml-7">
          Toggle actions below to see how many extra days of financial runway each one could buy you. Stack them to maximize breathing room.
        </p>
      </div>

      <Card padding="md">
        {/* Runway bar */}
        <div className="mb-6">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
            <span>0 days</span>
            <span className="font-semibold text-foreground">
              {Math.round(extendedRunway)} days total
            </span>
            <span>{Math.round(maxDays)} days</span>
          </div>
          <div className="h-8 bg-muted/50 rounded-full overflow-hidden flex relative">
            <motion.div
              className={`${baseColor} rounded-l-full`}
              initial={{ width: 0 }}
              animate={{ width: `${baselinePercent}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
            <motion.div
              className="bg-success rounded-r-full"
              initial={{ width: 0 }}
              animate={{ width: `${gainPercent}%` }}
              transition={{ duration: 0.6, ease: "easeOut", delay: 0.3 }}
            />
          </div>
          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className={`h-2.5 w-2.5 rounded-full ${baseColor}`} />
              Baseline: {Math.round(baselineRunwayDays)}d
            </span>
            {totalGain > 0 && (
              <span className="flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-full bg-success" />
                Deferred: +{Math.round(totalGain)}d
              </span>
            )}
          </div>
        </div>

        {/* Toggle switches */}
        <div className="space-y-2.5">
          {deferrableEstimates.map((d, i) => {
            const active = toggles[d.category] ?? false;
            return (
              <motion.button
                key={d.category}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.65 + i * 0.06, duration: 0.3 }}
                onClick={() => toggle(d.category)}
                className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all text-left ${
                  active
                    ? "border-success/40 bg-success-light/30"
                    : "border-border bg-card hover:border-muted-foreground/30"
                }`}
              >
                {/* Custom toggle switch */}
                <div
                  className={`relative h-5 w-9 rounded-full transition-colors shrink-0 ${
                    active ? "bg-success" : "bg-muted"
                  }`}
                >
                  <motion.div
                    className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm"
                    animate={{ left: active ? 18 : 2 }}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Plus className="h-3.5 w-3.5 text-success shrink-0" />
                    <span className="text-sm font-medium text-foreground truncate">
                      {d.category}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 pl-5.5 line-clamp-1">
                    {d.description}
                  </p>
                </div>

                <Badge
                  variant={active ? "success" : "outline"}
                  size="sm"
                  className="shrink-0"
                >
                  +{Math.round(d.estimated_savings_days)}d
                </Badge>
              </motion.button>
            );
          })}
        </div>

        {/* Summary line */}
        {totalGain > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-4 pt-3 border-t border-border flex items-center justify-between"
          >
            <span className="text-sm text-muted-foreground flex items-center gap-1.5">
              <TrendingUp className="h-4 w-4 text-success" />
              With selected actions:
            </span>
            <span className="text-sm font-bold text-success font-mono">
              {Math.round(extendedRunway)} days runway (+{Math.round(totalGain)})
            </span>
          </motion.div>
        )}
      </Card>
    </motion.div>
  );
}
