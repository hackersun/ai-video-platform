import * as React from "react"
import { cn } from "@/lib/utils"

type SkeletonVariant = "text" | "card" | "avatar" | "table-row"

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: SkeletonVariant
  className?: string
}

const variantStyles: Record<SkeletonVariant, string> = {
  text: "h-4 w-full",
  card: "h-32 w-full rounded-lg",
  avatar: "h-10 w-10 rounded-full",
  "table-row": "h-10 w-full",
}

const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, variant = "text", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "animate-pulse rounded-md bg-muted",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  )
)
Skeleton.displayName = "Skeleton"

export { Skeleton, type SkeletonVariant }

export function DashboardSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      {/* Welcome area */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-9 w-64 bg-muted rounded" />
          <div className="h-5 w-48 bg-muted rounded" />
        </div>
        <div className="h-10 w-32 bg-muted rounded" />
      </div>

      {/* Workflow guide */}
      <div className="h-40 bg-muted/50 rounded-xl" />

      {/* My works */}
      <div className="space-y-4">
        <div className="h-6 w-24 bg-muted rounded" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 bg-muted/50 rounded-lg" />
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 bg-muted/50 rounded-lg" />
        ))}
      </div>

      {/* Recent items */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-64 bg-muted/50 rounded-lg" />
        <div className="h-64 bg-muted/50 rounded-lg" />
      </div>

      {/* Quick actions */}
      <div className="space-y-4">
        <div className="h-6 w-24 bg-muted rounded" />
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-24 bg-muted/50 rounded-xl" />
          ))}
        </div>
      </div>
    </div>
  );
}
