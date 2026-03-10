const EXAMPLES = [
  'Total policies purchased today',
  'Group today purchased Policies by insurance company',
  "List the total count of last week's purchased policies and the sum of PolicyAmount, PolicyAmountAfterSpecialDiscount",
  'How many new leasing contract this month',
];

interface ExampleSuggestionsProps {
  onSelect: (example: string) => void;
}

export function ExampleSuggestions({ onSelect }: ExampleSuggestionsProps) {
  return (
    <div className="text-center py-12">
      <div className="text-6xl mb-4">🗃️</div>
      <h2 className="text-xl text-gray-300 mb-2">Welcome to AskDB</h2>
      <p className="text-gray-500 max-w-md mx-auto">
        Ask questions about your database in natural language. For example:
      </p>
      <div className="mt-4 space-y-2">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            onClick={() => onSelect(example)}
            className="block mx-auto text-sm text-blue-400 hover:text-blue-300 transition-colors"
          >
            "{example}"
          </button>
        ))}
      </div>
    </div>
  );
}
