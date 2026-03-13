"use client";

import * as React from "react"
import { cn } from "@/lib/utils"

interface SliderProps {
  value?: number[]
  onValueChange?: (value: number[]) => void
  min?: number
  max?: number
  step?: number
  defaultValue?: number[]
  className?: string
}

const Slider: React.FC<SliderProps> = ({
  value,
  onValueChange,
  min = 0,
  max = 100,
  step = 1,
  defaultValue = [0],
  className,
}) => {
  const currentValue = value?.[0] ?? defaultValue[0]
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onValueChange?.([parseFloat(e.target.value)])
  }

  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={currentValue}
      onChange={handleChange}
      className={cn(
        "flex h-2 w-full rounded-full bg-white/10 appearance-none cursor-pointer accent-violet-500",
        className
      )}
    />
  )
}

export { Slider }