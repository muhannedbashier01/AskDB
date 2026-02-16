import type { Message } from '../types';
import { SummaryPreview } from './SummaryPreview';
import { SqlPreview } from './SqlPreview';
import { ResultsTable } from './ResultsTable';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.type === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] ${
          isUser
            ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2'
            : 'bg-gray-800 text-gray-100 rounded-2xl rounded-tl-sm'
        }`}
      >
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <div className="space-y-4 p-4">
            {message.response ? (
              <>
                {message.response.success ? (
                  <>
                    <SummaryPreview summary={message.response.summary} />
                    <SqlPreview
                      sql={message.response.sql_query}
                      attempts={message.response.attempts}
                    />
                    {message.response.columns.length > 0 ? (
                      <ResultsTable
                        columns={message.response.columns}
                        rows={message.response.rows}
                        rowCount={message.response.row_count}
                      />
                    ) : (
                      <p className="text-green-400">
                        {message.response.message || 'Query executed successfully'}
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    <SqlPreview
                      sql={message.response.sql_query}
                      attempts={message.response.attempts}
                    />
                    <div className="bg-red-900/30 border border-red-700 rounded-lg p-3">
                      <p className="text-red-400 text-sm">
                        {message.response.error || 'Query failed'}
                      </p>
                      <p className="text-gray-400 text-xs mt-1">
                        Failed after {message.response.attempts} attempt(s)
                      </p>
                    </div>
                  </>
                )}
              </>
            ) : (
              <p className="text-red-400">{message.content}</p>
            )}
          </div>
        )}

        <div
          className={`text-xs mt-1 ${
            isUser ? 'text-blue-200' : 'text-gray-500 px-4 pb-2'
          }`}
        >
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
