export interface QueryResponse {
  success: boolean;
  sql_query: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  attempts: number;
  error: string | null;
  message: string | null;
  summary?: string | null;
  session_id?: string | null;
}

interface BaseMessage {
  id: string;
  timestamp: Date;
}

export interface UserMessage extends BaseMessage {
  type: 'user';
  content: string;
}

export interface AssistantMessage extends BaseMessage {
  type: 'assistant';
  content: string;
  response?: QueryResponse;
}

export type Message = UserMessage | AssistantMessage;

export interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
}

export interface TableInfo {
  name: string;
  columns: ColumnInfo[];
  foreign_keys: {
    columns: string[];
    references_table: string;
    references_columns: string[];
  }[];
}

export interface SchemaResponse {
  tables: TableInfo[];
}

export interface HealthResponse {
  status: string;
  database: string;
  llm_endpoint: string;
}
