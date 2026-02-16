import { useState, useCallback, useMemo } from 'react';
import { VegaLite } from 'react-vega';
import type { VisualizationSpec } from 'react-vega';
import type { Visualization } from '../types';

interface ChartPreviewProps {
  visualizations: Visualization[];
  rows: Record<string, unknown>[];
}

export function ChartPreview({ visualizations, rows }: ChartPreviewProps) {
  if (!visualizations || visualizations.length === 0) return null;

  return (
    <div className="space-y-4">
      {visualizations.map((viz, index) => (
        <ChartCard key={index} visualization={viz} rows={rows} />
      ))}
    </div>
  );
}

interface ChartCardProps {
  visualization: Visualization;
  rows: Record<string, unknown>[];
}

const DARK_THEME = {
  background: '#1a1a2e',
  axis: {
    labelColor: '#9ca3af',
    titleColor: '#d1d5db',
    gridColor: '#374151',
    domainColor: '#4b5563',
  },
  legend: {
    labelColor: '#9ca3af',
    titleColor: '#d1d5db',
  },
  view: {
    stroke: 'transparent',
  },
  title: {
    color: '#d1d5db',
  },
};

function ChartCard({ visualization, rows }: ChartCardProps) {
  const [error, setError] = useState<string | null>(null);

  const handleError = useCallback((err: unknown) => {
    const message = err instanceof Error ? err.message : 'Failed to render chart';
    console.error('Chart render error:', err);
    setError(message);
  }, []);

  const spec = useMemo<VisualizationSpec>(() => {
    const { $schema: _schema, data: _data, ...restSpec } = visualization.spec as Record<string, unknown>;
    return {
      ...restSpec,
      data: { name: 'table' },
      autosize: { type: 'fit', contains: 'padding' },
      width: 600,
      height: 300,
      config: DARK_THEME,
    } as VisualizationSpec;
  }, [visualization.spec]);

  const data = useMemo(() => ({ table: rows }), [rows]);

  if (error) {
    return (
      <div className="rounded-lg overflow-hidden border border-gray-700">
        <div className="bg-gray-800 px-3 py-1.5 text-xs text-gray-400">
          {visualization.title}
        </div>
        <div className="px-3 py-3 bg-[#1a1a2e]">
          <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-3">
            <p className="text-yellow-400 text-sm">
              Failed to render chart: {error}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg overflow-hidden border border-gray-700">
      <div className="bg-gray-800 px-3 py-1.5 text-xs text-gray-400">
        {visualization.title}
      </div>
      <div className="px-3 py-3 bg-[#1a1a2e]">
        {visualization.description && (
          <p className="text-sm text-gray-400 mb-3">{visualization.description}</p>
        )}
        <div className="w-full">
          <VegaLite
            spec={spec}
            data={data}
            actions={false}
            onError={handleError}
          />
        </div>
      </div>
    </div>
  );
}
