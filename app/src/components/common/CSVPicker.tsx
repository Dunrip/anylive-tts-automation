import React, { useState } from "react";
import type { CSVPreviewResponse } from "../../lib/types";

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
    <div data-testid="csv-picker" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <button
          data-testid="select-csv-button"
          onClick={handleSelectFile}
          disabled={loading}
          style={{
            padding: "6px 14px",
            backgroundColor: "var(--accent)",
            color: "white",
            border: "none",
            borderRadius: "6px",
            fontSize: "13px",
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? "Loading..." : "Select CSV"}
        </button>

        {selectedPath && (
          <>
            <span
              data-testid="selected-file-name"
              style={{
                fontSize: "13px",
                color: "var(--text-secondary)",
                flex: 1,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {selectedPath.split("/").pop() || selectedPath}
            </span>
            <button
              data-testid="clear-csv-button"
              onClick={handleClear}
              style={{
                padding: "4px 8px",
                backgroundColor: "transparent",
                color: "var(--text-muted)",
                border: "1px solid var(--border-default)",
                borderRadius: "4px",
                fontSize: "12px",
                cursor: "pointer",
              }}
            >
              Clear
            </button>
          </>
        )}
      </div>

      {error && (
        <p data-testid="csv-error" style={{ fontSize: "12px", color: "var(--error)", margin: 0 }}>
          {error}
        </p>
      )}

      {preview && (
        <div data-testid="csv-preview">
          <p
            data-testid="csv-summary"
            style={{ fontSize: "12px", color: "var(--text-secondary)", margin: "0 0 8px" }}
          >
            {preview.rows} rows · {preview.products} products · ~{preview.estimated_versions} versions
          </p>

          {preview.preview.length > 0 && (
            <div
              style={{
                overflowX: "auto",
                border: "1px solid var(--border-default)",
                borderRadius: "6px",
              }}
            >
              <table
                data-testid="csv-preview-table"
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "12px",
                }}
              >
                <thead>
                  <tr style={{ backgroundColor: "var(--bg-elevated)" }}>
                    {["No.", "Product", "Script", "Audio Code"].map((h) => (
                      <th
                        key={h}
                        style={{
                          padding: "6px 10px",
                          textAlign: "left",
                          color: "var(--text-muted)",
                          fontWeight: 500,
                          borderBottom: "1px solid var(--border-default)",
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview.map((row, i) => (
                    <tr
                      key={i}
                      style={{
                        backgroundColor: i % 2 === 0 ? "transparent" : "var(--bg-surface)",
                      }}
                    >
                      <td style={{ padding: "5px 10px", color: "var(--text-secondary)" }}>{row.no}</td>
                      <td style={{ padding: "5px 10px", color: "var(--text-primary)" }}>{row.product_name}</td>
                      <td
                        style={{
                          padding: "5px 10px",
                          color: "var(--text-secondary)",
                          maxWidth: "200px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {row.script}
                      </td>
                      <td style={{ padding: "5px 10px", color: "var(--text-muted)" }}>{row.audio_code}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
