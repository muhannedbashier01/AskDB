import { useState, useRef, useEffect } from 'react';
import { useQuery } from '../hooks/useQuery';
import { MessageBubble } from './MessageBubble';

export function ChatInterface() {
  const [input, setInput] = useState('');
  const { messages, isLoading, sendQuery, clearMessages } = useQuery();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const query = input.trim();
    setInput('');
    await sendQuery(query);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
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

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-5xl mx-auto space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">🗃️</div>
              <h2 className="text-xl text-gray-300 mb-2">
                Welcome to AskDB
              </h2>
              <p className="text-gray-500 max-w-md mx-auto">
                Ask questions about your database in natural language. For example:
              </p>
              <div className="mt-4 space-y-2">
                {[
                  'Total policies purchased today',
                  'Group today purchased Policies by insurance company',
                  "List the total count of last week's purchased policies and the sum of PolicyAmount, PolicyAmountAfterSpecialDiscount",
                  'How many new leasing contract this month',
                ].map((example) => (
                  <button
                    key={example}
                    onClick={() => setInput(example)}
                    className="block mx-auto text-sm text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    "{example}"
                  </button>
                ))}
              </div>
            </div>
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

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-gray-700 bg-gray-800 px-4 py-4">
        <form onSubmit={handleSubmit} className="max-w-5xl mx-auto">
          <div className="flex gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your database..."
              rows={1}
              className="flex-1 bg-gray-900 text-white border border-gray-700 rounded-lg px-4 py-3 resize-none focus:outline-none focus:border-blue-500 transition-colors"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors"
            >
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2 text-center">
            Press Enter to send, Shift+Enter for new line
          </p>
        </form>
      </div>
    </div>
  );
}
