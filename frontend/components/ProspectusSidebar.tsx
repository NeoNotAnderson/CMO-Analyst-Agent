'use client';

import type { Prospectus } from '@/types';

interface ProspectusSidebarProps {
  prospectuses: Prospectus[];
  activeProspectusId: string | null;
  onSelectProspectus: (prospectusId: string) => void;
}

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'completed':
      return 'bg-green-100 text-green-800';
    case 'parsing_index':
    case 'parsing_sections':
    case 'failed':
      return 'bg-red-100 text-red-800';
    case 'pending':
    default:
      return 'bg-gray-100 text-gray-800';
  }
};

const getStatusLabel = (status: string): string => {
  switch (status) {
    case 'pending':
      return 'Pending';
    case 'parsing_index':
      return 'Parsing Index';
    case 'parsing_sections':
      return 'Parsing Sections';
    case 'completed':
      return 'Completed';
    case 'failed':
      return 'Failed';
    default:
      return status;
  }
};

const isProcessingStatus = (status: string): boolean => {
  return ['pending', 'parsing_index', 'parsing_sections'].includes(status);
};

export default function ProspectusSidebar({
  prospectuses,
  activeProspectusId,
  onSelectProspectus
}: ProspectusSidebarProps) {
  return (
    <div className="w-64 bg-gray-50 border-r border-gray-200 h-full overflow-y-auto">
      <div className="p-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Prospectuses</h2>

        {prospectuses.length === 0 ? (
          <p className="text-sm text-gray-500">No prospectuses uploaded yet.</p>
        ) : (
          <div className="space-y-2">
            {prospectuses.map((prospectus) => {
              const isActive = prospectus.prospectus_id === activeProspectusId;

              return (
                <button
                  key={prospectus.prospectus_id}
                  onClick={() => onSelectProspectus(prospectus.prospectus_id)}
                  className={`w-full text-left p-3 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-blue-100 border-2 border-blue-500'
                      : 'bg-white border border-gray-200 hover:bg-gray-100'
                  }`}
                >
                  <div className="font-medium text-sm text-gray-900 truncate mb-2">
                    {prospectus.prospectus_name}
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-block px-2 py-1 text-xs font-medium rounded ${getStatusColor(
                        prospectus.parse_status
                      )}`}
                    >
                      {getStatusLabel(prospectus.parse_status)}
                    </span>

                    {/* Loading spinner for processing states */}
                    {isProcessingStatus(prospectus.parse_status) && (
                      <svg
                        className="animate-spin h-4 w-4 text-yellow-600"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                    )}
                  </div>

                  <div className="text-xs text-gray-500 mt-2">
                    {new Date(prospectus.upload_date).toLocaleDateString()}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}