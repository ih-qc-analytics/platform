export const ASESOR_EXAM_CATEGORIES = [
    "Cambridge English (Main Suite)",
    "Cambridge Teaching & Skills",
    "IELTS",
    "Michigan (MET)",
    "TEA (Test of English for Aviation)",
    "Placement & Otros",
] as const

export type AsesorExamCategory = (typeof ASESOR_EXAM_CATEGORIES)[number]

export function createEmptyAsesorExamBreakdown<TValue>(valueFactory: () => TValue) {
    return Object.fromEntries(ASESOR_EXAM_CATEGORIES.map(category => [category, valueFactory()])) as Record<
        AsesorExamCategory,
        TValue
    >
}

export type TableDisplayGroup = {
    label: string
    categories: readonly AsesorExamCategory[]
}

export const TABLE_DISPLAY_GROUPS: TableDisplayGroup[] = [
    { label: "Cambridge", categories: ["Cambridge English (Main Suite)", "Cambridge Teaching & Skills"] },
    { label: "IELTS", categories: ["IELTS"] },
    { label: "MET", categories: ["Michigan (MET)"] },
    { label: "Otros", categories: ["TEA (Test of English for Aviation)", "Placement & Otros"] },
]
