"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
}

const Tabs = React.forwardRef<HTMLDivElement, TabsProps>(
  ({ className, defaultValue, value, onValueChange, children, ...props }, ref) => {
    const [activeTab, setActiveTab] = React.useState(defaultValue || value || "");
    
    React.useEffect(() => {
      if (value !== undefined) setActiveTab(value);
    }, [value]);

    const handleTabClick = (tabValue: string) => {
      setActiveTab(tabValue);
      onValueChange?.(tabValue);
    };

    return (
      <div ref={ref} className={className} {...props}>
        {React.Children.map(children, (child) => {
          if (React.isValidElement(child)) {
            return React.cloneElement(child as React.ReactElement<any>, {
              activeTab,
              onTabClick: handleTabClick,
            });
          }
          return child;
        })}
      </div>
    );
  }
);
Tabs.displayName = "Tabs";

const TabsList = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { activeTab?: string; onTabClick?: (value: string) => void }
>(({ className, activeTab, onTabClick, children, ...props }, ref) => {
  return (
    <div
      ref={ref}
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-md bg-slate-800 p-1 text-slate-400",
        className
      )}
      {...props}
    >
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<any>, {
            isActive: child.props.value === activeTab,
            onClick: () => child.props.value && onTabClick?.(child.props.value),
          });
        }
        return child;
      })}
    </div>
  );
});
TabsList.displayName = "TabsList";

const TabsTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { isActive?: boolean; value?: string }
>(({ className, isActive, value, ...props }, ref) => {
  return (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-slate-900 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
        isActive ? "bg-slate-900 text-white shadow-sm" : "text-slate-400 hover:text-white",
        className
      )}
      {...props}
    />
  );
});
TabsTrigger.displayName = "TabsTrigger";

const TabsContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { value?: string; activeTab?: string }
>(({ className, value, activeTab, children, ...props }, ref) => {
  if (value !== activeTab) return null;
  
  return (
    <div
      ref={ref}
      className={cn(
        "mt-2 ring-offset-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
});
TabsContent.displayName = "TabsContent";

export { Tabs, TabsList, TabsTrigger, TabsContent };