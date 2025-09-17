import Cookies from 'js-cookie';

export const downloadFile = async (url: string, filename?: string): Promise<void> => {
  try {
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // Get the filename from the response headers if not provided
    const contentDisposition = response.headers.get('Content-Disposition');
    let defaultFilename = filename || 'download';

    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
      if (filenameMatch && filenameMatch[1]) {
        defaultFilename = filenameMatch[1].replace(/['"]/g, '');
      }
    }

    // Get the blob from the response
    const blob = await response.blob();

    // Create a temporary URL for the blob
    const blobUrl = window.URL.createObjectURL(blob);

    // Create a temporary link element
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = defaultFilename;

    // Append the link to the body
    document.body.appendChild(link);

    // Trigger the download
    link.click();

    // Clean up
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  } catch (error) {
    console.error('Error downloading file:', error);
    throw error;
  }
};

export const downloadFileFromData = (
  data: Blob | string,
  filename: string,
  mimeType?: string
): void => {
  try {
    let blob: Blob;

    if (typeof data === 'string') {
      blob = new Blob([data], { type: mimeType || 'text/plain' });
    } else {
      blob = data;
    }

    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;

    document.body.appendChild(link);
    link.click();

    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  } catch (error) {
    console.error('Error downloading file from data:', error);
    throw error;
  }
};

export const uploadFile = async (
  file: File,
  url: string,
  onProgress?: (progress: number) => void,
  additionalData?: Record<string, any>
): Promise<any> => {
  try {
    const formData = new FormData();
    formData.append('file', file);

    // Add additional form data if provided
    if (additionalData) {
      Object.entries(additionalData).forEach(([key, value]) => {
        formData.append(key, value);
      });
    }

    const xhr = new XMLHttpRequest();

    return new Promise((resolve, reject) => {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          const progress = (event.loaded / event.total) * 100;
          onProgress(progress);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response);
          } catch (error) {
            resolve(xhr.responseText);
          }
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      };

      xhr.onerror = () => {
        reject(new Error('Network error during upload'));
      };

      // Get authentication token from cookies
      const token = Cookies.get('access_token');

      xhr.open('POST', url, true);

      // Set the authorization header if token exists
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }

      xhr.send(formData);
    });
  } catch (error) {
    console.error('Error uploading file:', error);
    throw error;
  }
};