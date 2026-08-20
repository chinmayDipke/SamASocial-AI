import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

/*
  Three variants and no more, because the design allows exactly one primary on
  screen at a time (the composer's Send). Everything else is a bordered secondary
  or a chrome-free quiet button -- no icon-only primary, no full-width button, no
  gradient, nothing rounder than 5px.
*/
const buttonVariants = cva(
  "control inline-flex items-center justify-center whitespace-nowrap transition-colors duration-100 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        primary:
          "h-9 rounded-[5px] bg-accent px-4 text-paper hover:bg-accent-deep active:translate-y-[0.5px] disabled:bg-rule disabled:text-ink-faint",
        secondary:
          "h-9 rounded-[5px] border border-rule-firm bg-transparent px-4 text-ink hover:border-ink-quiet hover:bg-paper-warm disabled:border-rule disabled:text-ink-faint",
        quiet:
          "h-8 rounded-[4px] px-2 text-ink-quiet hover:bg-paper-warm hover:text-ink disabled:text-ink-faint",
      },
    },
    defaultVariants: {
      variant: "secondary",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render the caller's own element instead -- used to style a file `<label>`. */
  asChild?: boolean;
}

export function Button({ className, variant, asChild = false, ...props }: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return <Component className={cn(buttonVariants({ variant }), className)} {...props} />;
}
