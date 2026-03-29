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
