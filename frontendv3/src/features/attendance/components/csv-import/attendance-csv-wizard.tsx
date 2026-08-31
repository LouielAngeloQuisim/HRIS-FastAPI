import { useCallback, useMemo, useState } from 'react'
// @ts-expect-error - papaparse has no type declarations
import Papa from 'papaparse'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api/client'
import { toast } from 'sonner'
import { CheckCircle2, Upload, XCircle } from 'lucide-react'

type CsvRow = Record<string, string>
type ImportStatus = 'pending' | 'success' | 'error'

interface RowResult {
  row: number
  data: CsvRow
  status: ImportStatus
  error?: string
}

const DTR_REQUIRED_FIELDS = ['employee_code', 'login_date', 'logout_date']

export function AttendanceCsvImportWizard({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [csvText, setCsvText] = useState('')
  const [parsedRows, setParsedRows] = useState<CsvRow[]>([])
  const [headers, setHeaders] = useState<string[]>([])
  const [results, setResults] = useState<RowResult[]>([])
  const [isImporting, setIsImporting] = useState(false)
  const [progress, setProgress] = useState(0)

  const requiredFields = useMemo(() => DTR_REQUIRED_FIELDS, [])

  const parseCsv = useCallback((text: string) => {
    const parsed = Papa.parse<CsvRow>(text, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: false,
    })

    if (parsed.errors.length > 0) {
      toast.error(`CSV parse error: ${parsed.errors[0].message}`)
      return
    }

    const rows = parsed.data
    const cols = parsed.meta.fields ?? []

    setParsedRows(rows)
    setHeaders(cols)
    setResults([])
    setProgress(0)
  }, [])

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return

    if (selectedFile.type && !selectedFile.type.includes('csv') && !selectedFile.name.endsWith('.csv')) {
      toast.error('Please select a CSV file')
      return
    }

    setFile(selectedFile)
    const reader = new FileReader()
    reader.onload = (evt) => {
      const text = evt.target?.result as string
      setCsvText(text)
      parseCsv(text)
    }
    reader.readAsText(selectedFile)
  }, [])

  const handleTextareaChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setCsvText(e.target.value)
    setFile(null)
    if (e.target.value.trim()) {
      parseCsv(e.target.value)
    } else {
      setParsedRows([])
      setHeaders([])
      setResults([])
    }
  }, [parseCsv])

  const mapColumns = (row: CsvRow) => ({
    employee_code: row.employee_code,
    login_date: row.login_date,
    logout_date: row.logout_date,
    shift_code: row.shift_code || undefined,
  })

  const validateRow = useCallback((row: CsvRow): string | null => {
    const missing = requiredFields.filter(f => !row[f] || row[f].trim() === '')
    if (missing.length > 0) {
      return `Missing required fields: ${missing.join(', ')}`
    }
    return null
  }, [requiredFields])

  const handleImport = useCallback(async () => {
    if (parsedRows.length === 0) {
      toast.error('No data to import')
      return
    }

    setIsImporting(true)
    setResults([])
    setProgress(0)

    const newResults: RowResult[] = []
    const total = parsedRows.length

    for (let i = 0; i < parsedRows.length; i++) {
      const row = parsedRows[i]
      const error = validateRow(row)

      if (error) {
        newResults.push({ row: i + 2, data: row, status: 'error', error })
      } else {
        try {
          const mapped = mapColumns(row)
          await api.post('/daily-time-records', mapped)
          newResults.push({ row: i + 2, data: row, status: 'success' })
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Unknown error'
          newResults.push({ row: i + 2, data: row, status: 'error', error: message })
        }
      }

      setProgress(Math.round(((i + 1) / total) * 100))
    }

    setResults(newResults)
    setIsImporting(false)

    const successCount = newResults.filter(r => r.status === 'success').length
    const errorCount = newResults.filter(r => r.status === 'error').length

    if (errorCount === 0) {
      toast.success(`Successfully imported ${successCount} time records`)
    } else {
      toast.error(`Imported ${successCount} time records, ${errorCount} failed`)
    }
  }, [parsedRows, validateRow])

  const handleClose = useCallback(() => {
    if (isImporting) return
    onOpenChange(false)
    setTimeout(() => {
      setFile(null)
      setCsvText('')
      setParsedRows([])
      setHeaders([])
      setResults([])
      setProgress(0)
    }, 200)
  }, [isImporting, onOpenChange])

  const successCount = results.filter(r => r.status === 'success').length
  const errorCount = results.filter(r => r.status === 'error').length

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import Attendance from CSV</DialogTitle>
          <DialogDescription>
            Upload a CSV file or paste CSV data to import time records in bulk. Required fields: {requiredFields.join(', ')}.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Upload CSV File</Label>
            <div className="flex items-center gap-2">
              <Input
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                disabled={isImporting}
                className="cursor-pointer"
              />
              {file && (
                <Button variant="ghost" size="icon" onClick={() => { setFile(null); setCsvText(''); setParsedRows([]); setHeaders([]); }}>
                  <XCircle className="h-4 w-4" />
                </Button>
              )}
            </div>
            {file && <p className="text-sm text-muted-foreground">Selected: {file.name}</p>}
          </div>

          <div className="space-y-2">
            <Label>Or paste CSV data</Label>
            <Textarea
              value={csvText}
              onChange={handleTextareaChange}
              placeholder="employee_code,login_date,logout_date,shift_code&#10;EMP001,2026-08-04T08:00:00Z,2026-08-04T17:00:00Z,DAY"
              rows={6}
              disabled={isImporting}
            />
          </div>

          {parsedRows.length > 0 && (
            <div className="space-y-2">
              <Label>Preview ({parsedRows.length} rows)</Label>
              <div className="max-h-48 overflow-y-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      {headers.map(h => (
                        <th key={h} className="p-2 text-left font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {parsedRows.slice(0, 10).map((row, i) => (
                      <tr key={i} className="border-t">
                        {headers.map(h => (
                          <td key={h} className="p-2">{row[h] ?? '—'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {parsedRows.length > 10 && (
                  <p className="p-2 text-xs text-muted-foreground">Showing first 10 of {parsedRows.length} rows</p>
                )}
              </div>
            </div>
          )}

          {isImporting && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Importing...</span>
                <span>{progress}%</span>
              </div>
              <Progress value={progress} />
            </div>
          )}

          {results.length > 0 && !isImporting && (
            <div className="space-y-2">
              <div className="flex items-center gap-4 text-sm">
                <span className="flex items-center gap-1 text-green-600">
                  <CheckCircle2 className="h-4 w-4" /> {successCount} succeeded
                </span>
                {errorCount > 0 && (
                  <span className="flex items-center gap-1 text-destructive">
                    <XCircle className="h-4 w-4" /> {errorCount} failed
                  </span>
                )}
              </div>
              <div className="max-h-48 overflow-y-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="p-2 text-left">Row</th>
                      <th className="p-2 text-left">Status</th>
                      <th className="p-2 text-left">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((result, i) => (
                      <tr key={i} className="border-t">
                        <td className="p-2">{result.row}</td>
                        <td className="p-2">
                          {result.status === 'success' ? (
                            <span className="flex items-center gap-1 text-green-600"><CheckCircle2 className="h-4 w-4" /> Success</span>
                          ) : (
                            <span className="flex items-center gap-1 text-destructive"><XCircle className="h-4 w-4" /> Failed</span>
                          )}
                        </td>
                        <td className="p-2 text-destructive">{result.error || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isImporting}>
            Close
          </Button>
          <Button onClick={handleImport} disabled={isImporting || parsedRows.length === 0}>
            <Upload className="mr-2 h-4 w-4" />
            {isImporting ? 'Importing...' : `Import ${parsedRows.length} Records`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
