import React, { useState } from "react";
import type { CSVPreviewResponse } from "../../lib/types";
import { cn } from "@/lib/utils";
import { FileSpreadsheet, X } from "lucide-react";
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from "@/components/ui/table";

interface CSVPickerProps {
  onFileSelected?: (path: string, preview: CSVPreviewResponse) => void;
  onClear?: () => void;
  sidecarUrl?: string | null;
  configPath?: string;
}

export function CSVPicker({
  onFileSelected,
  onClear,
  sidecarUrl,
  configPath,
}: CSVPickerProps): React.ReactElement {
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [preview, setPreview] = useState<CSVPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelectFile = async (): Promise<void> => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({
        multiple: false,
        filters: [{ name: "CSV Files", extensions: ["csv"] }],
      });

      if (!selected || typeof selected !== "string") return;

      setSelectedPath(selected);
      setError(null);

      if (sidecarUrl && configPath) {
        setLoading(true);
        try {
          const resp = await fetch(`${sidecarUrl}/api/csv/preview`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ csv_path: selected, config_path: configPath }),
          });
          if (resp.ok) {
            const data: CSVPreviewResponse = await resp.json();
            setPreview(data);
            onFileSelected?.(selected, data);
          } else {
            setError("Failed to load CSV preview");
          }
        } catch {
          setError("Could not connect to sidecar");
        } finally {
          setLoading(false);
        }
      } else {
        onFileSelected?.(selected, { rows: 0, products: 0, estimated_versions: 0, preview: [], errors: [] });
      }
    } catch {
      setError("Failed to open file dialog");
    }
  };

  const handleClear = (): void => {
    setSelectedPath(null);
    setPreview(null);
    setError(null);
    onClear?.();
  };

  return (
    <div data-testid="csv-picker" className="flex flex-col gap-2">
      {selectedPath ? (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-default)]">
          <FileSpreadsheet className="size-4 text-[var(--success)] shrink-0" />
          <span
            data-testid="selected-file-name"
            className="text-sm text-[var(--text-primary)] flex-1 overflow-hidden text-ellipsis whitespace-nowrap"
          >
            {selectedPath.split("/").pop() || selectedPath}
          </span>
          <button
            data-testid="clear-csv-button"
            onClick={handleClear}
            aria-label="Clear selected file"
            className="p-0.5 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors cursor-pointer bg-transparent border-none"
          >
            <X className="size-3.5" />
          </button>
        </div>
      ) : (
        <button
          data-testid="select-csv-button"
          onClick={handleSelectFile}
          disabled={loading}
          className={cn(
            "inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer bg-transparent border-none p-0",
            loading && "opacity-50 cursor-wait"
          )}
        >
          <FileSpreadsheet className="size-4" />
          <span className="underline underline-offset-2 decoration-[var(--border-active)]">
            {loading ? "Loading..." : "Select CSV file"}
          </span>
        </button>
      )}

      {error && (
        <p data-testid="csv-error" className="text-xs text-[var(--error)]">
          {error}
        </p>
      )}

      {preview && (
        <div data-testid="csv-preview">
          <p
            data-testid="csv-summary"
            className="text-xs text-[var(--text-secondary)] mb-2"
          >
            {preview.rows} rows · {preview.products} products · ~{preview.estimated_versions} versions
          </p>

          {preview.preview.length > 0 && (
            <Table data-testid="csv-preview-table" className="border border-[var(--border-default)] rounded-md">
              <TableHeader className="bg-[var(--bg-elevated)]">
                <TableRow>
                  {["No.", "Product", "Script", "Audio Code"].map((h) => (
                    <TableHead key={h} className="text-[var(--text-muted)]">
                      {h}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {preview.preview.map((row, i) => (
                  <TableRow
                    key={i}
                    className={cn(i % 2 !== 0 && "bg-[var(--bg-surface)]")}
                  >
                    <TableCell className="text-[var(--text-secondary)]">{row.no}</TableCell>
                    <TableCell className="text-[var(--text-primary)]">{row.product_name}</TableCell>
                    <TableCell className="text-[var(--text-secondary)] max-w-[200px] overflow-hidden text-ellipsis whitespace-nowrap">
                      {row.script}
                    </TableCell>
                    <TableCell className="text-[var(--text-muted)]">{row.audio_code}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      )}
    </div>
  );
}
