import { FileDown, Loader2, Settings2, Sheet } from "lucide-react"
import { useState } from "react"

import DateRangePicker from "@/components/filters/DateRangePicker"
import { FILTER_BUTTON_CLASS, FILTER_CONTROL_CLASS, FILTER_FIELD_WIDTH_CLASS } from "@/components/filters/controlStyles"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import type { ComparisonFields } from "@/types"
import { cn } from "@/lib/utils"

type AdvancedOptionsPopoverProps = {
    comparison: ComparisonFields
    onApplyComparison: (next: ComparisonFields) => void
    hideComparison?: boolean
    onExportPdf?: () => void
    onExportExcelWithFilters?: () => void
    onExportExcelWithoutFilters?: () => void
    isExportingPdf?: boolean
    isExportingExcel?: boolean
    exportingExcelVariant?: "filtered" | "all" | null
    exportError?: string | null
}

export default function AdvancedOptionsPopover({
    comparison,
    onApplyComparison,
    hideComparison = false,
    onExportPdf,
    onExportExcelWithFilters,
    onExportExcelWithoutFilters,
    isExportingPdf = false,
    isExportingExcel = false,
    exportingExcelVariant = null,
    exportError,
}: AdvancedOptionsPopoverProps) {
    const [open, setOpen] = useState(false)
    const [draft, setDraft] = useState<ComparisonFields>(comparison)

    const normalizedDraft: ComparisonFields = {
        show_comparison: draft.show_comparison ?? false,
        comparison_mode: draft.comparison_mode ?? "PREVIOUS_YEAR",
        comparison_date_from: draft.comparison_mode === "CUSTOM" ? draft.comparison_date_from : undefined,
        comparison_date_to: draft.comparison_mode === "CUSTOM" ? draft.comparison_date_to : undefined,
    }

    const applyComparison = () => {
        onApplyComparison(normalizedDraft)
        setOpen(false)
    }

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen) {
            if (comparison.show_comparison && !normalizedDraft.show_comparison) {
                onApplyComparison(normalizedDraft)
            }
            setDraft(comparison)
        }
        setOpen(nextOpen)
    }

    const handleExportClick = (mode: "filtered" | "all") => {
        if (mode === "filtered") {
            onExportExcelWithFilters?.()
            return
        }
        onExportExcelWithoutFilters?.()
    }

    return (
        <DropdownMenu open={open} onOpenChange={handleOpenChange}>
            <DropdownMenuTrigger asChild>
                <Button
                    variant="outline"
                    className={cn(FILTER_BUTTON_CLASS, FILTER_CONTROL_CLASS, FILTER_FIELD_WIDTH_CLASS, "justify-start")}
                >
                    <Settings2 className="size-4" />
                    Opciones avanzadas
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
                align="end"
                sideOffset={10}
                className="w-[30rem] rounded-3xl border border-border bg-card p-4 shadow-xl"
                onCloseAutoFocus={(event) => event.preventDefault()}
            >
                <div className="flex flex-col gap-5">
                    {!hideComparison ? (
                        <section className="flex flex-col gap-4">
                            <div className="space-y-1">
                                <p className="text-sm font-semibold text-slate-900">Comparación</p>
                                <p className="text-xs text-muted-foreground">Compara exactamente dos períodos.</p>
                            </div>

                            <label className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-muted/30 px-4 py-3 text-sm text-slate-700">
                                <span>{draft.show_comparison ? "Comparación activa" : "Comparación inactiva"}</span>
                                <input
                                    type="checkbox"
                                    checked={draft.show_comparison ?? false}
                                    onChange={(event) =>
                                        setDraft((prev) => ({ ...prev, show_comparison: event.target.checked }))
                                    }
                                />
                            </label>

                            {draft.show_comparison ? (
                                <>
                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
                                            Modo
                                        </label>
                                        <select
                                            value={draft.comparison_mode ?? "PREVIOUS_YEAR"}
                                            onChange={(event) =>
                                                setDraft((prev) => ({
                                                    ...prev,
                                                    comparison_mode: event.target
                                                        .value as ComparisonFields["comparison_mode"],
                                                }))
                                            }
                                            className="h-11 rounded-2xl border border-border bg-background px-3 text-sm"
                                        >
                                            <option value="PREVIOUS_YEAR">Mismo período año anterior</option>
                                            <option value="PREVIOUS_PERIOD">Período anterior</option>
                                            <option value="CUSTOM">Rango personalizado</option>
                                        </select>
                                    </div>

                                    {draft.comparison_mode === "CUSTOM" ? (
                                        <div className="rounded-2xl border border-border/70 bg-muted/30 p-3">
                                            <DateRangePicker
                                                dateFrom={draft.comparison_date_from}
                                                dateTo={draft.comparison_date_to}
                                                onDateFromChange={(value) =>
                                                    setDraft((prev) => ({
                                                        ...prev,
                                                        comparison_date_from: value || undefined,
                                                    }))
                                                }
                                                onDateToChange={(value) =>
                                                    setDraft((prev) => ({
                                                        ...prev,
                                                        comparison_date_to: value || undefined,
                                                    }))
                                                }
                                            />
                                        </div>
                                    ) : null}

                                    <div className="flex justify-end gap-2">
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            className="rounded-2xl"
                                            onClick={() => setDraft(comparison)}
                                        >
                                            Cancelar
                                        </Button>
                                        <Button
                                            type="button"
                                            className="rounded-2xl"
                                            onClick={applyComparison}
                                            disabled={Boolean(
                                                draft.show_comparison &&
                                                draft.comparison_mode === "CUSTOM" &&
                                                (!draft.comparison_date_from || !draft.comparison_date_to),
                                            )}
                                        >
                                            Confirmar
                                        </Button>
                                    </div>
                                </>
                            ) : null}
                        </section>
                    ) : null}

                    <section className={`flex flex-col gap-3 pt-4 ${!hideComparison ? "border-t border-border" : ""}`}>
                        <div className="space-y-1">
                            <p className="text-sm font-semibold text-slate-900">Exportación</p>
                            <p className="text-xs text-muted-foreground">Genera PDF o Excel desde este reporte.</p>
                        </div>

                        <Button
                            onClick={onExportPdf}
                            variant="outline"
                            className="justify-start rounded-2xl"
                            disabled={isExportingPdf}
                        >
                            {isExportingPdf ? (
                                <Loader2 className="size-4 animate-spin" />
                            ) : (
                                <FileDown className="size-4" />
                            )}
                            {isExportingPdf ? "Generando PDF..." : "Exportar PDF"}
                        </Button>

                        <div className="rounded-2xl border border-border bg-background p-2">
                            <DropdownMenuItem
                                className="rounded-xl px-3 py-3"
                                disabled={isExportingExcel}
                                onClick={() => handleExportClick("filtered")}
                            >
                                <Sheet className="size-4" />
                                <span>Exportar Excel con filtros</span>
                                {exportingExcelVariant === "filtered" ? (
                                    <Loader2 className="ml-auto size-4 animate-spin" />
                                ) : null}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                className="rounded-xl px-3 py-3"
                                disabled={isExportingExcel}
                                onClick={() => handleExportClick("all")}
                            >
                                <Sheet className="size-4" />
                                <span>Exportar Excel sin filtros</span>
                                {exportingExcelVariant === "all" ? (
                                    <Loader2 className="ml-auto size-4 animate-spin" />
                                ) : null}
                            </DropdownMenuItem>
                        </div>

                        {exportError ? <p className="text-sm text-destructive">{exportError}</p> : null}
                    </section>
                </div>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
