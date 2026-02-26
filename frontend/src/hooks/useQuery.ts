import { useState, useCallback, useRef } from 'react';
import type { Message } from '../types';
import { submitQuery, clearSession } from '../services/api';

export function useQuery() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef<string>(crypto.randomUUID());

  const sendQuery = useCallback(async (query: string) => {
    setIsLoading(true);
    setError(null);

    // Add user message
    const userMessage: Message = {
      id: crypto.randomUUID(),
      type: 'user',
      content: query,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);

    try {
      const response = await submitQuery(query, sessionIdRef.current);

      // Add assistant message with response
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        type: 'assistant',
        content: response.success
          ? `Found ${response.row_count} rows`
          : response.error || 'Query failed',
        timestamp: new Date(),
        response,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      return response;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);

      // Add error message
      const errorAssistantMessage: Message = {
        id: crypto.randomUUID(),
        type: 'assistant',
        content: `Error: ${errorMessage}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorAssistantMessage]);

      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearMessages = useCallback(() => {
    // Clear session on backend
    clearSession(sessionIdRef.current).catch(() => {});
    // Generate new session for fresh conversation
    sessionIdRef.current = crypto.randomUUID();
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendQuery,
    clearMessages,
  };
}
