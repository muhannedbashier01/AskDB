export interface QueryResponse {
  success: boolean;
  sql_query: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  attempts: number;
  error: string | null;
  message: string | null;
}

export interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  response?: QueryResponse;
}

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
