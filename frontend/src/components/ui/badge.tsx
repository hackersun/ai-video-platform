import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variantStyles: Record<string, string> = {
    default: "border-transparent bg-violet-500 text-white hover:bg-violet-600",
    secondary: "border-transparent bg-white/10 text-white/80 hover:bg-white/20",
    destructive: "border-transparent bg-red-500 text-white hover:bg-red-600",
    outline: "text-white border-white/20",
    success: "border-transparent bg-green-500/20 text-green-400",
    warning: "border-transparent bg-yellow-500/20 text-yellow-400",
  }
  
  return (
    <div 
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
        variantStyles[variant],
        className
      )} 
      {...props} 
    />
  )
}

export { Badge }