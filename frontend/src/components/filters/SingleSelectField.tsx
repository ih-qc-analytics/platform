import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

type SingleSelectFieldProps = {
    label: string
    value: string
    options: string[]
    onChange: (value: string) => void
    triggerClassName?: string
}

export default function SingleSelectField({
    label,
    value,
    options,
    onChange,
    triggerClassName = "",
}: SingleSelectFieldProps) {
    return (
        <Select value={value} onValueChange={onChange}>
            <SelectTrigger aria-label={label} className={triggerClassName}>
                <SelectValue placeholder={label} />
            </SelectTrigger>
            <SelectContent>
                <SelectItem value="all">{label}</SelectItem>
                {cleanOptions(options).map(option => (
                    <SelectItem key={option} value={option}>
                        {option}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    )
}

export function cleanOptions(options: string[]) {
    return [...new Set(options.map(option => option.trim()).filter(Boolean))]
}
