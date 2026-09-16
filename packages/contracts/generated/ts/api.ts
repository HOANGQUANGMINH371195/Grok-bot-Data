/**
 * Generated from packages/contracts/openapi/v1.yaml,
 * packages/contracts/events/v1.json and packages/contracts/protocol/v1.json.
 * Do not add business logic or permissions here; the server remains the authority.
 */

export type BotTemplate = 'DataAssistant' | 'DataSteward' | 'DataAnalyst' | 'ReportWriter';
export type Role = 'viewer' | 'editor' | 'owner' | 'moderator' | 'member';
export type RunState =
  | 'queued'
  | 'leased'
  | 'running'
  | 'waiting'
  | 'completed'
  | 'handed_off'
  | 'failed'
  | 'cancelled';
export type WaitReason = 'input' | 'approval' | 'children' | 'tool' | 'peer';
export type ResultStatus =
  | 'ok'
  | 'queued'
  | 'needs_approval'
  | 'needs_input'
  | 'denied'
  | 'failed';
export type EventType =
  | 'message.created'
  | 'message.edited'
  | 'message.deleted'
  | 'run.updated'
  | 'tool.executed'
  | 'artifact.ready'
  | 'report.published'
  | 'observatory.journaled';

export interface CreateConversationRequest {
  conversation_id: string;
  member_ids: string[];
  bot_templates?: Record<string, BotTemplate>;
}

export interface ConversationCreated {
  conversation_id: string;
  workspace_id: string;
}

export interface CreateDatasetRequest {
  dataset_id: string;
}

export interface DatasetCreated {
  dataset_id: string;
  workspace_id: string;
}

export interface ArtifactCreated {
  artifact_id: string;
  dataset_id: string;
  workspace_id: string;
  source_sha256: string;
  object_version_id: string;
  size_bytes: number;
  format: 'csv' | 'parquet';
  headers: string[];
  row_count: number;
  status: 'ready';
}

export interface ProfileDatasetRequest {
  artifact_id: string;
}

export interface ProfileEvidence {
  evidence_id: string;
  source_version: string;
  method_version: string;
  cell_refs: string[];
  limitations: string[];
  approved: false;
}

export interface ProfileColumn {
  name: string;
  physical_type: 'numeric' | 'numeric_nonfinite' | 'timestamp' | 'string' | 'unknown';
  non_null_count: number;
  null_count: number;
  null_rate: string | null;
  distinct_non_null_count: number;
  pii_signal_counts: Record<string, number>;
}

export interface ProfileCreated {
  profile_id: string;
  dataset_id: string;
  workspace_id: string;
  artifact_id: string;
  source_sha256: string;
  row_count: number;
  column_count: number;
  method_version: string;
  status: 'completed';
  evidence: ProfileEvidence;
  columns: ProfileColumn[];
}

export interface SendMessageRequest {
  client_message_id: string;
  body: string;
}

export interface MessageAck {
  message_id: string;
  sequence: number;
  bot_dispatch: Record<string, string>;
  event_id: string;
}

export interface Message {
  message_id: string;
  sender_id: string;
  sequence: number;
  body: string;
}

export interface MessageList {
  messages: Message[];
}

export interface EventEnvelope {
  event_id: string;
  event_sequence: number;
  event_type: EventType;
  payload: Record<string, unknown>;
}

export interface EventReplay {
  high_watermark: number;
  events: EventEnvelope[];
}

export interface BotTurnRequest {
  bot_id: string;
  turn_id: string;
}

export interface BotTurnResponse {
  status: ResultStatus;
  provider: string;
  model: string;
  error_code: string | null;
  message_id: string | null;
  sequence: number | null;
  text: string;
}

export interface ApiErrorBody {
  detail: string;
  code?: string;
  correlation_id?: string;
  retryable?: boolean;
}

export class VdaApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail);
    this.name = 'VdaApiError';
    this.status = status;
    this.body = body;
  }
}

export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class VdaApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: FetchLike;

  constructor(baseUrl: string, fetcher: FetchLike = fetch) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.fetcher = fetcher;
  }

  createConversation(
    workspaceId: string,
    principalId: string,
    request: CreateConversationRequest,
  ): Promise<ConversationCreated> {
    return this.request<ConversationCreated>(
      `/v1/local/workspaces/${encodeURIComponent(workspaceId)}/conversations`,
      principalId,
      { method: 'POST', body: JSON.stringify(request) },
    );
  }

  createDataset(
    workspaceId: string,
    principalId: string,
    request: CreateDatasetRequest,
  ): Promise<DatasetCreated> {
    return this.request<DatasetCreated>(
      `/v1/local/workspaces/${encodeURIComponent(workspaceId)}/datasets`,
      principalId,
      { method: 'POST', body: JSON.stringify(request) },
    );
  }

  uploadDataset(
    workspaceId: string,
    datasetId: string,
    uploadId: string,
    principalId: string,
    filename: string,
    payload: Blob,
    expectedSha256?: string,
  ): Promise<ArtifactCreated> {
    const headers = new Headers({
      'Content-Type': payload.type || 'application/octet-stream',
      'X-File-Name': filename,
    });
    if (expectedSha256) headers.set('X-Content-SHA256', expectedSha256);
    return this.request<ArtifactCreated>(
      `/v1/local/workspaces/${encodeURIComponent(workspaceId)}/datasets/${encodeURIComponent(datasetId)}/uploads/${encodeURIComponent(uploadId)}`,
      principalId,
      { method: 'POST', body: payload, headers },
    );
  }

  profileDataset(
    workspaceId: string,
    datasetId: string,
    principalId: string,
    request: ProfileDatasetRequest,
  ): Promise<ProfileCreated> {
    return this.request<ProfileCreated>(
      `/v1/local/workspaces/${encodeURIComponent(workspaceId)}/datasets/${encodeURIComponent(datasetId)}/profiles`,
      principalId,
      { method: 'POST', body: JSON.stringify(request) },
    );
  }

  sendMessage(
    conversationId: string,
    principalId: string,
    request: SendMessageRequest,
  ): Promise<MessageAck> {
    return this.request<MessageAck>(
      `/v1/local/conversations/${encodeURIComponent(conversationId)}/messages`,
      principalId,
      { method: 'POST', body: JSON.stringify(request) },
    );
  }

  readMessages(conversationId: string, principalId: string): Promise<MessageList> {
    return this.request<MessageList>(
      `/v1/local/conversations/${encodeURIComponent(conversationId)}/messages`,
      principalId,
    );
  }

  readEvents(
    conversationId: string,
    principalId: string,
    afterSeq = 0,
  ): Promise<EventReplay> {
    return this.request<EventReplay>(
      `/v1/local/conversations/${encodeURIComponent(conversationId)}/events?after_seq=${afterSeq}`,
      principalId,
    );
  }

  runBotTurn(
    conversationId: string,
    principalId: string,
    request: BotTurnRequest,
  ): Promise<BotTurnResponse> {
    return this.request<BotTurnResponse>(
      `/v1/local/conversations/${encodeURIComponent(conversationId)}/bot-turn`,
      principalId,
      { method: 'POST', body: JSON.stringify(request) },
    );
  }

  private async request<T>(path: string, principalId: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    headers.set('X-Principal-Id', principalId);
    if (typeof init.body === 'string' && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });
    const body: unknown = await response.json();
    if (!response.ok) {
      const errorBody = isApiErrorBody(body) ? body : { detail: 'request failed' };
      throw new VdaApiError(response.status, errorBody);
    }
    return body as T;
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    'detail' in value &&
    typeof value.detail === 'string'
  );
}
