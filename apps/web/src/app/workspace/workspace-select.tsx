"use client";

/* Use case: Offers one clearly labelled choice inside the workspace.
What it does: Themes Radix Select while preserving managed focus, keyboard navigation,
typeahead and viewport-aware positioning; it does not change application state itself. */

import { useId } from "react";
import * as Select from "@radix-ui/react-select";
import styles from "./workspace-select.module.css";

export type WorkspaceSelectOption = {
  value: string;
  label: string;
  description?: string;
};

export type WorkspaceSelectProps = {
  id?: string;
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  options: readonly WorkspaceSelectOption[];
  disabled?: boolean;
};

function Chevron({ up = false }: { up?: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path d={up ? "m6 15 6-6 6 6" : "m6 9 6 6 6-6"} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function WorkspaceSelect({ id, label, value, onValueChange, options, disabled = false }: WorkspaceSelectProps) {
  const generatedId = useId();
  const triggerId = id ?? `workspace-select-${generatedId}`;
  const labelId = `${triggerId}-label`;

  return (
    <div className={styles.field}>
      <label className={styles.label} id={labelId} htmlFor={triggerId}>{label}</label>
      <Select.Root value={value} onValueChange={onValueChange} disabled={disabled}>
        <Select.Trigger id={triggerId} className={styles.trigger} aria-labelledby={labelId}>
          <span className={styles.value}><Select.Value placeholder="Choose an option" /></span>
          <Select.Icon className={styles.chevron}><Chevron /></Select.Icon>
        </Select.Trigger>
        <Select.Portal>
          <Select.Content className={styles.content} position="popper" side="bottom" align="start" sideOffset={8} collisionPadding={12} aria-labelledby={labelId}>
            <Select.ScrollUpButton className={styles.scrollButton} aria-label="Scroll choices up"><Chevron up /></Select.ScrollUpButton>
            <Select.Viewport className={styles.viewport}>
              {options.map((option, index) => {
                const descriptionId = `${triggerId}-description-${index}`;
                return (
                  <Select.Item key={option.value} className={styles.item} value={option.value} textValue={option.label} aria-describedby={option.description ? descriptionId : undefined}>
                    <span className={styles.optionCopy}>
                      <span className={styles.optionLabel}><Select.ItemText>{option.label}</Select.ItemText></span>
                      {option.description && <span className={styles.description} id={descriptionId}>{option.description}</span>}
                    </span>
                    <Select.ItemIndicator className={styles.indicator}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
                        <path d="m5 12 4 4L19 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </Select.ItemIndicator>
                  </Select.Item>
                );
              })}
            </Select.Viewport>
            <Select.ScrollDownButton className={styles.scrollButton} aria-label="Scroll choices down"><Chevron /></Select.ScrollDownButton>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </div>
  );
}
