import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import sql from 'react-syntax-highlighter/dist/esm/languages/hljs/sql';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';

SyntaxHighlighter.registerLanguage('sql', sql);

interface SqlPreviewProps {
  sql: string;
  attempts?: number;
}

export function SqlPreview({ sql, attempts }: SqlPreviewProps) {
  return (
    <div className="rounded-lg overflow-hidden border border-gray-700">
      <div className="bg-gray-800 px-3 py-1.5 text-xs text-gray-400 flex justify-between items-center">
        <span>Generated SQL</span>
        {attempts && attempts > 1 && (
          <span className="text-yellow-400">Attempt {attempts}</span>
        )}
      </div>
      <SyntaxHighlighter
        language="sql"
        style={atomOneDark}
        customStyle={{
          margin: 0,
          padding: '12px',
          fontSize: '13px',
          background: '#1a1a2e',
        }}
      >
        {sql}
      </SyntaxHighlighter>
    </div>
  );
}
