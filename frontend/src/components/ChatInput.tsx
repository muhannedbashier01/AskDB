interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
}

export function ChatInput({ value, onChange, onSubmit, isLoading }: ChatInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e);
    }
  };

  return (
    <div className="border-t border-gray-700 bg-gray-800 px-4 py-4">
      <form onSubmit={onSubmit} className="max-w-5xl mx-auto">
        <div className="flex gap-3">
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your database..."
            rows={1}
            className="flex-1 bg-gray-900 text-white border border-gray-700 rounded-lg px-4 py-3 resize-none focus:outline-none focus:border-blue-500 transition-colors"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!value.trim() || isLoading}
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
  );
}
