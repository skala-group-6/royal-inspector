import type { ComponentProps, ReactNode } from "react"
import { Slot } from "radix-ui"
import { cn } from "@/lib/utils"

/**
 * Line-free list primitives (docs/DESIGN.md). Separation comes from spacing and the surface-* tones;
 * never add border-b / dividers between items.
 */

/** Section title at the top of a panel. */
export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 pt-4 pb-1">
      <span className="type-title">{children}</span>
      {right}
    </div>
  )
}

/** Small summary line under a title (counts, period). */
export function ListMeta({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("flex items-center justify-between px-4 pb-2 type-meta", className)} {...props} />
}

/** Vertical stack of items with a small gap, inset from the panel edge so rounded backgrounds read as items. */
export function ListGroup({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("flex flex-col gap-0.5 px-2 pb-2", className)} {...props} />
}

/** One item: rounded, hover and selected shown by background only. Use `asChild` to render a router Link. */
export function ListItem({ asChild, active, className, ...props }: ComponentProps<"div"> & { asChild?: boolean; active?: boolean }) {
  const Comp = asChild ? Slot.Root : "div"
  return (
    <Comp
      data-active={active || undefined}
      className={cn("rounded-lg px-2.5 py-2 hover:bg-surface-hover data-active:bg-surface-selected", className)}
      {...props}
    />
  )
}
