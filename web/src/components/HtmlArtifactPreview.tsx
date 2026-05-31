import { Button } from "@nous-research/ui/ui/components/button";
import { Card } from "@nous-research/ui/ui/components/card";
import { api, type HtmlArtifactInfo } from "@/lib/api";
import { Copy, ExternalLink, FileCode2, RefreshCw, X } from "lucide-react";
import { useMemo, useState } from "react";
import { createPortal } from "react-dom";

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function formatModified(timestamp: number): string {
  if (!Number.isFinite(timestamp) || timestamp <= 0) return "—";
  return new Date(timestamp * 1000).toLocaleString();
}

function shortenDirectory(path: string): string {
  const parts = path.split("/").filter(Boolean);
  if (parts.length <= 3) return path;
  return `…/${parts.slice(-3).join("/")}`;
}

export function HtmlArtifactPreview({
  artifact,
  onRemove,
}: {
  artifact: HtmlArtifactInfo;
  onRemove?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [frameKey, setFrameKey] = useState(0);
  const [copied, setCopied] = useState(false);
  const previewUrl = useMemo(
    () => api.getHtmlArtifactViewUrl(artifact.preview_url),
    [artifact.preview_url],
  );
  const portalRoot = typeof document !== "undefined" ? document.body : null;

  const copyPath = () => {
    void navigator.clipboard.writeText(artifact.path).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    });
  };

  const openWindow = () => {
    window.open(previewUrl, "_blank", "noopener,noreferrer");
  };

  return (
    <>
      <Card className="flex flex-col gap-2 px-3 py-2 text-xs">
        <div className="flex items-start gap-2">
          <FileCode2 className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-text-primary" title={artifact.name}>
              {artifact.name}
            </div>
            <div className="truncate text-text-tertiary" title={artifact.directory}>
              {shortenDirectory(artifact.directory)}
            </div>
          </div>
          {onRemove && (
            <Button ghost size="icon" className="h-6 w-6 shrink-0" onClick={onRemove} aria-label="Remove artifact">
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 text-text-secondary">
          <span>{formatBytes(artifact.size)}</span>
          <span className="truncate" title={formatModified(artifact.modified_at)}>
            {formatModified(artifact.modified_at)}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-1.5">
          <Button size="sm" outlined onClick={() => setOpen(true)}>
            预览
          </Button>
          <Button size="sm" outlined onClick={openWindow} prefix={<ExternalLink className="h-3 w-3" />}>
            打开
          </Button>
          <Button size="sm" outlined onClick={copyPath} prefix={<Copy className="h-3 w-3" />}>
            {copied ? "已复制" : "路径"}
          </Button>
        </div>
      </Card>

      {open && portalRoot &&
        createPortal(
          <div className="fixed inset-0 z-[100] flex flex-col bg-background/95 backdrop-blur-sm">
            <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-border px-4">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-text-primary">{artifact.name}</div>
                <div className="truncate text-xs text-text-secondary">{artifact.path}</div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button size="sm" outlined onClick={() => setFrameKey((v) => v + 1)} prefix={<RefreshCw className="h-3 w-3" />}>
                  刷新
                </Button>
                <Button size="sm" outlined onClick={openWindow} prefix={<ExternalLink className="h-3 w-3" />}>
                  新窗口
                </Button>
                <Button ghost size="icon" onClick={() => setOpen(false)} aria-label="Close preview">
                  <X />
                </Button>
              </div>
            </div>
            <iframe
              key={frameKey}
              title={artifact.name}
              src={previewUrl}
              sandbox="allow-scripts allow-same-origin"
              referrerPolicy="no-referrer"
              className="min-h-0 flex-1 border-0 bg-white"
            />
          </div>,
          portalRoot,
        )}
    </>
  );
}