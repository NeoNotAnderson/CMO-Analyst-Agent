/**
 * FileUpload Component
 *
 * Drag-and-drop file upload for prospectus PDFs
 */

'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadProspectus, getProspectusStatus } from '@/lib/api';
import { validatePdfFile, getStatusText, getStatusColor } from '@/lib/utils';
import type { UploadResponse } from '@/types';

interface FileUploadProps {
  onUploadComplete?: (prospectusId: string) => void;
}

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [showOverwriteDialog, setShowOverwriteDialog] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [duplicateMessage, setDuplicateMessage] = useState<string>('');

  const handleUpload = async (file: File, useExisting: boolean = false) => {
    // Reset error and start upload
    setError('');
    setIsUploading(true);
    setUploadStatus('uploading');

    try {
      // Upload file to backend
      const response = await uploadProspectus(file, useExisting);

      // Check if duplicate was found
      if (response.duplicate) {
        setIsUploading(false);
        setShowOverwriteDialog(true);
        setPendingFile(file);
        setDuplicateMessage(response.message);
        return;
      }

      const prospectusId = response.prospectus_id!;

      // Start polling for parsing status
      setUploadStatus('parsing');

      const pollInterval = setInterval(async () => {
        try {
          const { status } = await getProspectusStatus(prospectusId);
          setUploadStatus(status);

          if (status === 'completed') {
            clearInterval(pollInterval);
            setIsUploading(false);
            onUploadComplete?.(prospectusId);
          } else if (status === 'failed') {
            clearInterval(pollInterval);
            setIsUploading(false);
            setError('Parsing failed. Please try again.');
          }
        } catch (err) {
          clearInterval(pollInterval);
          setIsUploading(false);
          setError('Failed to check parsing status');
        }
      }, 2000); // Poll every 2 seconds

    } catch (err) {
      setIsUploading(false);
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
    }
  };

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    // Get the first file
    if (acceptedFiles.length === 0) {
      setError('No file selected');
      return;
    }

    const file = acceptedFiles[0];

    // Validate PDF file
    const validationError = validatePdfFile(file);
    if (validationError.error) {
      setError(validationError.error);
      return;
    }

    // Initiate upload
    await handleUpload(file, false);
  }, []);

  const handleUseExisting = async () => {
    if (pendingFile) {
      setShowOverwriteDialog(false);
      await handleUpload(pendingFile, true);
      setPendingFile(null);
    }
  };

  const handleCancel = () => {
    setShowOverwriteDialog(false);
    setPendingFile(null);
    setDuplicateMessage('');
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    disabled: isUploading,
  });

  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
          ${isUploading ? 'cursor-not-allowed opacity-50' : ''}
        `}
      >
        <input {...getInputProps()} />

        {isUploading ? (
          <div className="space-y-2">
            <div className="text-lg font-semibold">Uploading and parsing...</div>
            <div className={`text-sm ${getStatusColor(uploadStatus)}`}>
              {getStatusText(uploadStatus)}
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <div className="text-lg font-semibold">
              {isDragActive ? 'Drop the PDF here' : 'Drop a PDF here, or click to select'}
            </div>
            <p className="text-sm text-gray-500">CMO Prospectus PDF (Max 50MB)</p>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Use Existing Confirmation Dialog */}
      {showOverwriteDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-2">Duplicate File Detected</h3>
            <p className="text-gray-600 mb-6">{duplicateMessage}</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleCancel}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUseExisting}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Use Existing
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
