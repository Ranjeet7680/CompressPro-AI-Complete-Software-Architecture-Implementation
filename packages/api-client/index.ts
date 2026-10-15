/**
 * CompressPro AI - TypeScript Client SDK & Type Definitions
 * Auto-aligned with FastAPI schemas and Master Architecture Blueprint Section 8.
 */

export type JobState =
  | 'created'
  | 'validating'
  | 'queued'
  | 'running'
  | 'finalizing'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'rejected'
  | 'expired';

export type JobOperation =
  | 'image.compress'
  | 'image.resize'
  | 'image.convert'
  | 'image.crop'
  | 'image.rotate'
  | 'image.metadata'
  | 'image.to_pdf'
  | 'pdf.compress'
  | 'pdf.merge'
  | 'pdf.split'
  | 'pdf.rotate'
  | 'pdf.reorder'
  | 'pdf.extract'
  | 'pdf.to_images'
  | 'video.compress'
  | 'video.convert'
  | 'video.trim'
  | 'video.resize'
  | 'video.audio'
  | 'video.probe';

export interface JobProgress {
  stage: string;
  percent: number;
  message?: string;
}

export interface JobError {
  code: string;
  message: string;
  request_id?: string;
  retryable: boolean;
}

export interface ArtifactMetadata {
  id: string;
  job_id: string;
  object_key: string;
  filename: string;
  mime: string;
  bytes: number;
  checksum_sha256: string;
  width?: number;
  height?: number;
  duration_seconds?: number;
  page_count?: number;
  compression_ratio?: number;
  savings_percent?: number;
}

export interface JobResponse {
  job_id: string;
  operation: JobOperation;
  status: JobState;
  progress: JobProgress;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error?: JobError;
  artifacts: ArtifactMetadata[];
}

export class CompressProClient {
  constructor(private baseUrl: string = 'http://127.0.0.1:8000') {}

  async uploadFile(file: File): Promise<{ file_id: string; filename: string; bytes: number }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${this.baseUrl}/api/v1/uploads`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async createJob(params: {
    inputFileIds: string[];
    operation: JobOperation;
    settings?: Record<string, any>;
    idempotencyKey?: string;
  }): Promise<JobResponse> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (params.idempotencyKey) {
      headers['Idempotency-Key'] = params.idempotencyKey;
    }
    const res = await fetch(`${this.baseUrl}/api/v1/jobs`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        input_file_ids: params.inputFileIds,
        operation: params.operation,
        settings: params.settings || {},
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async getJob(jobId: string): Promise<JobResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/jobs/${jobId}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async cancelJob(jobId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/api/v1/jobs/${jobId}/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
  }

  getDownloadUrl(artifactId: string): string {
    return `${this.baseUrl}/api/v1/artifacts/${artifactId}/download`;
  }
}
