"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { CheckCircle2, XCircle, ShieldCheck } from "lucide-react";
import type { CompletenessScore } from "@/lib/types";

interface CompletenessRingProps {
  completeness: CompletenessScore;
}

export function CompletenessRing({ completeness }: CompletenessRingProps) {
  const { score, items, present_count, missing_count, summary } = completeness;

  const variant =
    score >= 80 ? "success" : score >= 50 ? "amber" : "danger";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.55, duration: 0.5 }}
    >
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-success" />
          <h2 className="text-lg font-bold text-foreground tracking-tight">
            Packet Completeness
          </h2>
        </div>
        <p className="text-xs text-muted-foreground mt-1 ml-7">
          Tracks which supporting documents are ready vs. still needed. A more complete packet means faster processing and fewer back-and-forth requests.
        </p>
      </div>

      <Card padding="md">
        <div className="flex flex-col sm:flex-row items-center gap-6">
          {/* Ring */}
          <div className="shrink-0">
            <ProgressRing
              value={score}
              size={140}
              strokeWidth={10}
              variant={variant}
              label={`${score}%`}
              sublabel="complete"
            />
          </div>

          {/* Checklist */}
          <div className="flex-1 w-full">
            <p className="text-sm text-muted-foreground mb-3">{summary}</p>
            <div className="grid grid-cols-1 gap-1.5 max-h-[240px] overflow-y-auto pr-1">
              {items.map((ci, i) => (
                <motion.div
                  key={ci.item}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.6 + i * 0.04, duration: 0.25 }}
                  className="flex items-start gap-2"
                >
                  {ci.present ? (
                    <CheckCircle2 className="h-4 w-4 text-success shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="h-4 w-4 text-danger shrink-0 mt-0.5" />
                  )}
                  <div className="min-w-0">
                    <span
                      className={`text-xs font-medium ${
                        ci.present
                          ? "text-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      {ci.item}
                      {ci.weight === 3 && !ci.present && (
                        <span className="text-danger ml-1 text-[10px]">
                          (critical)
                        </span>
                      )}
                    </span>
                    {!ci.present && ci.reason && (
                      <p className="text-[10px] text-muted-foreground leading-tight">
                        {ci.reason}
                      </p>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
            <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground border-t border-border pt-2">
              <span className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3 text-success" />
                {present_count} present
              </span>
              <span className="flex items-center gap-1">
                <XCircle className="h-3 w-3 text-danger" />
                {missing_count} missing
              </span>
            </div>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
