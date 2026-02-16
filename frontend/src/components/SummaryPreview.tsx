interface SummaryPreviewProps {
  summary?: string | null;
}

export function SummaryPreview({ summary }: SummaryPreviewProps) {
  if (!summary) return null;

  return (
    <div className="rounded-lg overflow-hidden border border-gray-700">
      <div className="bg-gray-800 px-3 py-1.5 text-xs text-gray-400">
        Summary
      </div>
      <div className="px-3 py-3 bg-[#1a1a2e]">
        <p className="text-sm text-gray-300 leading-relaxed">{summary}</p>
      </div>
    </div>
  );
}
