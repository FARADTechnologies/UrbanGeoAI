import * as React from "react";

import { cn } from "@/lib/utils";

const Alert = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="alert"
      className={cn("rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm", className)}
      {...props}
    />
  )
);
Alert.displayName = "Alert";

export { Alert };
