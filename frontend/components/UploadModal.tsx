'use client';

import { useState } from 'react';
import FileUpload from './FileUpload';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadComplete: (prospectusId: string) => void;
}

export default function UploadModal({ isOpen, onClose, onUploadComplete }: UploadModalProps) {
  if (!isOpen) return null;

  const handleUploadComplete = (prospectusId: string) => {
    onUploadComplete(prospectusId);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4">
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Upload Prospectus</h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
            >
              &times;
            </button>
          </div>

          <FileUpload onUploadComplete={handleUploadComplete} />
        </div>
      </div>
    </div>
  );
}