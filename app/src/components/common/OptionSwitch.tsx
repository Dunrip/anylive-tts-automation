import React from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface OptionSwitchProps {
  id: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  description: string;
  disabled?: boolean;
  testId?: string;
}

export function OptionSwitch({
  id,
  checked,
  onCheckedChange,
  label,
  description,
  disabled,
  testId,
}: OptionSwitchProps): React.ReactElement {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <label htmlFor={id} className="flex items-center gap-1.5 cursor-pointer select-none">
          <input
            id={id}
            type="checkbox"
            checked={checked}
            onChange={(e) => onCheckedChange(e.target.checked)}
            disabled={disabled}
            data-testid={testId}
          />
          <span className="text-sm text-[var(--text-secondary)]">
            {label}
          </span>
        </label>
      </TooltipTrigger>
      <TooltipContent>{description}</TooltipContent>
    </Tooltip>
  );
}
