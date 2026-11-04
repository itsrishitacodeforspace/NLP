'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { FileText, Loader2, UploadCloud, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/layout/toast';
import { contractsApi } from '@/lib/api';
import { errorMessage } from '@/lib/api/errors';
import { ACCEPTED_EXTENSIONS, CONTRACT_TYPES, PARTY_SIDES, fileExtensionLabel, hasAcceptedExtension } from '@/lib/constants';
import { cn } from '@/lib/utils';
import type { ContractType, PartySide } from '@/types';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DropZone() {
  const router = useRouter();
  const { push } = useToast();
  const inputRef = React.useRef<HTMLInputElement>(null);

  const [file, setFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const [rejectReason, setRejectReason] = React.useState<string | null>(null);
  const [contractType, setContractType] = React.useState<ContractType>('Other');
  const [userRole, setUserRole] = React.useState<PartySide>('Customer');

  const accept = (f: File) => {
    setFile(null);
    setRejectReason(null);
    if (!hasAcceptedExtension(f.name)) {
      setRejectReason(
        `Unsupported file type${fileExtensionLabel(f.name) ? ` (${fileExtensionLabel(f.name)})` : ''}. Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}.`
      );
      return;
    }
    if (f.size === 0) {
      setRejectReason('The file is empty.');
      return;
    }
    // Pre-check against the backend cap (default 25 MB, max_upload_mb) to fail
    // early with a clear message instead of a 413 mid-upload.
    if (f.size > 25 * 1024 * 1024) {
      setRejectReason(`File is ${formatBytes(f.size)} — the backend limit is 25 MB.`);
      return;
    }
    setFile(f);
  };

  const upload = useMutation({
    mutationFn: () => contractsApi.upload({ file: file as File, contractType, userRole }),
    onSuccess: (job) => {
      push('success', 'Upload accepted — analysis started.');
      router.push(`/jobs/${job.job_id}`);
    },
    onError: (e: unknown) => {
      push('error', errorMessage(e));
    },
  });

  const canSubmit = file !== null && !upload.isPending;

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) accept(dropped);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload a contract</CardTitle>
        <CardDescription>
          PDF, DOCX, TXT or Markdown. Parsed, segmented and risk-scored in the background —
          you are taken to a live progress view the moment it is accepted.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div
          role="button"
          tabIndex={0}
          aria-label="Choose a contract file"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center gap-2 border border-dashed px-6 py-10 text-center transition-colors',
            dragOver ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/40',
            rejectReason && 'border-destructive/50'
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(',')}
            className="hidden"
            onChange={(e) => {
              const picked = e.target.files?.[0];
              if (picked) accept(picked);
              e.target.value = '';
            }}
          />
          <UploadCloud className="h-8 w-8 text-muted-foreground" aria-hidden />
          {file ? (
            <div className="flex items-center gap-2 text-sm">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              <span className="max-w-[280px] truncate font-medium">{file.name}</span>
              <span className="text-muted-foreground">· {formatBytes(file.size)}</span>
              <button
                type="button"
                aria-label="Remove file"
                className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  setRejectReason(null);
                }}
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>
          ) : (
            <>
              <p className="text-sm font-medium">Drop a file here, or click to browse</p>
              <p className="text-xs text-muted-foreground">
                Accepted: {ACCEPTED_EXTENSIONS.join(', ')}
              </p>
            </>
          )}
        </div>

        {rejectReason ? (
          <p className="text-sm text-destructive">{rejectReason}</p>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="contract-type">Contract type</Label>
            <select
              id="contract-type"
              value={contractType}
              onChange={(e) => setContractType(e.target.value as ContractType)}
              className="flex h-9 w-full border border-input bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {CONTRACT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="user-role">Your side</Label>
            <select
              id="user-role"
              value={userRole}
              onChange={(e) => setUserRole(e.target.value as PartySide)}
              className="flex h-9 w-full border border-input bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {PARTY_SIDES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={() => {
              if (canSubmit) upload.mutate();
            }}
            disabled={!canSubmit}
          >
            {upload.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
            {upload.isPending ? 'Uploading…' : 'Analyze'}
          </Button>
          {upload.isPending ? (
            <span className="text-sm text-muted-foreground">Uploading…</span>
          ) : null}
        </div>

        {upload.isError ? <p className="text-sm text-destructive">{errorMessage(upload.error)}</p> : null}
      </CardContent>
    </Card>
  );
}
