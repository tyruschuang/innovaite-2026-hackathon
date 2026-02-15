"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { BarChart3, Users, DollarSign, ExternalLink } from "lucide-react";
import type { DisasterBenchmark } from "@/lib/types";

interface BenchmarkCardProps {
  benchmark: DisasterBenchmark;
}

function formatDollars(val: number | null): string {
  if (val == null) return "N/A";
  if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(1)}B`;
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`;
  return `$${val.toLocaleString()}`;
}

function formatNumber(val: number | null): string {
  if (val == null) return "N/A";
  return val.toLocaleString();
}

export function BenchmarkCard({ benchmark }: BenchmarkCardProps) {
  if (!benchmark.available) return null;

  const stats = [
    {
      label: "Housing Assistance",
      value: formatDollars(benchmark.total_amount_ha_approved),
      icon: DollarSign,
      show: benchmark.total_amount_ha_approved != null,
    },
    {
      label: "Individual & Households",
      value: formatDollars(benchmark.total_amount_ihp_approved),
      icon: DollarSign,
      show: benchmark.total_amount_ihp_approved != null,
    },
    {
      label: "Other Needs Assistance",
      value: formatDollars(benchmark.total_amount_ona_approved),
      icon: DollarSign,
      show: benchmark.total_amount_ona_approved != null,
    },
    {
      label: "Approved Applicants",
      value: formatNumber(benchmark.total_applicants),
      icon: Users,
      show: benchmark.total_applicants != null,
    },
  ].filter((s) => s.show);

  if (stats.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.5, duration: 0.5 }}
    >
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-bold text-foreground tracking-tight">
            How Others Fared
          </h2>
          {benchmark.incident_type && (
            <Badge variant="info" size="sm">
              {benchmark.incident_type}
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1 ml-7">
          Real FEMA aggregate data for this disaster. See what relief others received to set realistic expectations for your own applications.
        </p>
      </div>

      <Card padding="md">
        {benchmark.disaster_title && (
          <p className="text-sm text-muted-foreground mb-4">
            Real FEMA data for <span className="font-semibold text-foreground">{benchmark.disaster_title}</span>
            {benchmark.state && ` (${benchmark.state})`}
          </p>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {stats.map((stat, i) => {
            const Icon = stat.icon;
            return (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.55 + i * 0.08, duration: 0.35 }}
                className="text-center"
              >
                <div className="inline-flex items-center justify-center h-8 w-8 rounded-lg bg-primary/10 mb-2">
                  <Icon className="h-4 w-4 text-primary" />
                </div>
                <p className="text-lg font-bold text-foreground font-mono">
                  {stat.value}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {stat.label}
                </p>
              </motion.div>
            );
          })}
        </div>

        <p className="text-[10px] text-muted-foreground mt-4 flex items-center gap-1">
          <ExternalLink className="h-3 w-3" />
          Source: OpenFEMA FemaWebDisasterSummaries — live aggregate data
        </p>
      </Card>
    </motion.div>
  );
}
