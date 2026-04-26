'use client';

interface ParsingResumeDialogProps {
  isOpen: boolean;
  prospectusName: string;
  parsingMessage: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ParsingResumeDialog({
  isOpen,
  prospectusName,
  parsingMessage,
  onConfirm,
  onCancel,
}: ParsingResumeDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Resume Parsing</h3>
        <p className="text-sm text-gray-600 mb-1">
          <span className="font-medium">{prospectusName}</span>
        </p>
        <p className="text-sm text-gray-700 mb-6">{parsingMessage}</p>
        <p className="text-sm text-gray-500 mb-6">
          Would you like to resume parsing? This may take 5–10 minutes depending on document size.
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Resume Parsing
          </button>
        </div>
      </div>
    </div>
  );
}
