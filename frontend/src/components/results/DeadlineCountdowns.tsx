"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Clock, AlertTriangle, CheckCircle2, Timer } from "lucide-react";
import type { Deadline } from "@/lib/types";

interface DeadlineCountdownsProps {
  deadlines: Deadline[];
}

function deadlineBadge(dl: Deadline) {
  if (dl.is_expired) {
    return { variant: "danger" as const, label: "Expired", Icon: AlertTriangle };
  }
  if (dl.days_remaining <= 7) {
    return { variant: "danger" as const, label: `${dl.days_remaining}d left`, Icon: AlertTriangle };
  }
  if (dl.days_remaining <= 30) {
    return { variant: "warning" as const, label: `${dl.days_remaining}d left`, Icon: Timer };
  }
  return { variant: "success" as const, label: `${dl.days_remaining}d left`, Icon: CheckCircle2 };
}

export function DeadlineCountdowns({ deadlines }: DeadlineCountdownsProps) {
  if (!deadlines || deadlines.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4, duration: 0.5 }}
    >
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-info" />
          <h2 className="text-lg font-bold text-foreground tracking-tight">
            Filing Deadlines
          </h2>
        </div>
        <p className="text-xs text-muted-foreground mt-1 ml-7">
          Time-sensitive windows for disaster relief programs. Missing a deadline can mean losing access to that funding entirely.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {deadlines.map((dl, i) => {
          const { variant, label, Icon } = deadlineBadge(dl);
          const borderColor =
            dl.is_expired || dl.days_remaining <= 7
              ? "border-l-danger"
              : dl.days_remaining <= 30
                ? "border-l-amber"
                : "border-l-success";

          return (
            <motion.div
              key={dl.program}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.45 + i * 0.07, duration: 0.35 }}
            >
              <Card
                padding="sm"
                className={`border-l-4 ${borderColor} h-full`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-foreground leading-snug">
                      {dl.program}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Due: {new Date(dl.due_date).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </p>
                  </div>
                  <Badge variant={variant} size="md">
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </Badge>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
