import { useState } from 'react';
import { useQuery } from '../hooks/useQuery';
import { useAutoScroll } from '../hooks/useAutoScroll';
import { ChatInput } from './ChatInput';
import { ExampleSuggestions } from './ExampleSuggestions';
import { MessageBubble } from './MessageBubble';

export function ChatInterface() {
  const [input, setInput] = useState('');
  const { messages, isLoading, error, sendQuery, clearMessages } = useQuery();
  const bottomRef = useAutoScroll([messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    const query = input.trim();
    setInput('');
    await sendQuery(query);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex justify-between items-center max-w-5xl mx-auto">
          <div>
            <h1 className="text-xl font-semibold text-white">AskDB</h1>
            <p className="text-sm text-gray-400">
              Ask questions about your database in plain English
            </p>
          </div>
          <button
            onClick={clearMessages}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            Clear chat
          </button>
        </div>
      </header>

      {/* Error banner — surfaces network/unexpected errors to the user */}
      {error && (
        <div className="bg-red-900/50 border-b border-red-700 px-6 py-2">
          <p className="text-sm text-red-300 max-w-5xl mx-auto">{error}</p>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-5xl mx-auto space-y-4">
          {messages.length === 0 ? (
            <ExampleSuggestions onSelect={setInput} />
          ) : (
            messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))
          )}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex items-center gap-2 text-gray-400">
                  <div className="animate-pulse flex gap-1">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                  <span className="text-sm">Generating SQL...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      <ChatInput
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
        isLoading={isLoading}
      />
    </div>
  );
}
