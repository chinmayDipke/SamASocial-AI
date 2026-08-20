"use client";

import * as SelectPrimitive from "@radix-ui/react-select";
import * as React from "react";

import { cn } from "@/lib/utils";

/*
  A trimmed Radix Select: root, trigger, content, item. No value mirroring and
  no scroll buttons, because the only select in this app is a three-item
  difficulty menu whose trigger is the chip itself.

  The popover is the one place besides nothing else allowed to use
  `--shadow-pop`: a menu genuinely leaves the plane of the sheet.
*/

export const Select = SelectPrimitive.Root;

export function SelectTrigger({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger className={cn("cursor-pointer", className)} {...props}>
      {children}
    </SelectPrimitive.Trigger>
  );
}

export function SelectContent({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        position="popper"
        sideOffset={4}
        className={cn(
          "z-50 min-w-[9rem] overflow-hidden rounded-[4px] border border-rule-firm bg-popover shadow-pop",
          className,
        )}
        {...props}
      >
        <SelectPrimitive.Viewport className="p-1">{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

export function SelectItem({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-[3px] px-2 py-1.5 outline-none select-none",
        "data-[highlighted]:bg-paper-warm data-[state=checked]:bg-accent-tint",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  );
}
