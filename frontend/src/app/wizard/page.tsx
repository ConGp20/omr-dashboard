"use client";
import { useWizard } from "@/lib/wizardStore";
import { Network, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { StepWelcome } from "@/components/wizard/StepWelcome";
import { StepVpsConnect } from "@/components/wizard/StepVpsConnect";
import { StepWanDetect } from "@/components/wizard/StepWanDetect";
import { StepProtocol } from "@/components/wizard/StepProtocol";
import { StepLan } from "@/components/wizard/StepLan";
import { StepApply } from "@/components/wizard/StepApply";

const STEPS = [
  "Willkommen",
  "VPS verbinden",
  "Leitungen",
  "Protokoll",
  "LAN",
  "Verbinden",
];

export default function WizardPage() {
  const step = useWizard((s) => s.step);

  return (
    <div className="min-h-screen bg-bg">
      <div className="mx-auto max-w-3xl px-4 py-8">
        {/* Header */}
        <div className="mb-6 flex items-center gap-2 text-lg font-bold">
          <Network className="text-primary" /> OMR Einrichtung
        </div>

        {/* Stepper */}
        <div className="mb-8 flex items-center">
          {STEPS.map((label, i) => (
            <div key={label} className="flex flex-1 items-center last:flex-none">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-semibold transition",
                    i < step
                      ? "border-good bg-good text-white"
                      : i === step
                        ? "border-primary bg-primary text-white"
                        : "border-border bg-surface text-muted",
                  )}
                >
                  {i < step ? <Check size={16} /> : i + 1}
                </div>
                <span
                  className={cn(
                    "hidden text-[11px] sm:block",
                    i === step ? "font-medium text-fg" : "text-muted",
                  )}
                >
                  {label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={cn(
                    "mx-1 h-0.5 flex-1 transition",
                    i < step ? "bg-good" : "bg-border",
                  )}
                />
              )}
            </div>
          ))}
        </div>

        {/* Step content */}
        <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          {step === 0 && <StepWelcome />}
          {step === 1 && <StepVpsConnect />}
          {step === 2 && <StepWanDetect />}
          {step === 3 && <StepProtocol />}
          {step === 4 && <StepLan />}
          {step === 5 && <StepApply />}
        </div>
      </div>
    </div>
  );
}
