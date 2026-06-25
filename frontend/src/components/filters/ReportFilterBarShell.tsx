import type { ReactNode } from "react"

import AdvancedOptionsPopover from "@/components/filters/AdvancedOptionsPopover"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import type { ComparisonFields } from "@/types"

type ReportFilterBarShellProps = {
    children: ReactNode
    onClear?: () => void
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

export default function ReportFilterBarShell({
    children,
    onClear,
    comparison,
    onApplyComparison,
    hideComparison,
    onExportPdf,
    onExportExcelWithFilters,
    onExportExcelWithoutFilters,
    isExportingPdf,
    isExportingExcel,
    exportingExcelVariant,
    exportError,
}: ReportFilterBarShellProps) {
    return (
        <Card className="rounded-[2rem] shadow-sm">
            <CardContent className="grid gap-5 p-6 2xl:grid-cols-[minmax(0,1fr)_auto] 2xl:items-end">
                <div className="flex min-w-0 flex-wrap items-end gap-4">
                    {children}
                </div>
                <div className="flex shrink-0 flex-col gap-3 2xl:items-end">
                    {onClear ? (
                        <Button
                            variant="ghost"
                            className="self-start rounded-2xl px-2 text-sm font-semibold text-slate-700 underline-offset-4 hover:text-slate-950 hover:underline 2xl:self-end"
                            onClick={onClear}
                        >
                            Limpiar filtros
                        </Button>
                    ) : null}
                    <AdvancedOptionsPopover
                        comparison={comparison}
                        onApplyComparison={onApplyComparison}
                        hideComparison={hideComparison}
                        onExportPdf={onExportPdf}
                        onExportExcelWithFilters={onExportExcelWithFilters}
                        onExportExcelWithoutFilters={onExportExcelWithoutFilters}
                        isExportingPdf={isExportingPdf}
                        isExportingExcel={isExportingExcel}
                        exportingExcelVariant={exportingExcelVariant}
                        exportError={exportError}
                    />
                </div>
            </CardContent>
        </Card>
    )
}
