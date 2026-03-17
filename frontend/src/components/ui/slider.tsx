import * as React from "react"
import { cn } from "@/lib/utils"

export interface SliderProps {
  className?: string
  value?: number[]
  defaultValue?: number[]
  onValueChange?: (value: number[]) => void
  max?: number
  min?: number
  step?: number
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, value, defaultValue, onValueChange, max = 100, min = 0, step = 1, ...props }, ref) => {
    const currentValue = value?.[0] ?? defaultValue?.[0] ?? min;
    
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = parseFloat(e.target.value);
      if (onValueChange) {
        onValueChange([newValue]);
      }
    };

    return (
      <input
        type="range"
        value={currentValue}
        max={max}
        min={min}
        step={step}
        onChange={handleChange}
        className={cn(
          "flex h-2 w-full touch-none select-none items-center rounded-full bg-white/20 cursor-pointer",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Slider.displayName = "Slider"

export { Slider }
