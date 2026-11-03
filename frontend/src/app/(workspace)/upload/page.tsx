import { DropZone } from '@/components/contracts/drop-zone';
import { Disclaimer } from '@/components/layout/disclaimer';

export default function UploadPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">Upload a contract</h1>
      <DropZone />
      <Disclaimer />
    </div>
  );
}
