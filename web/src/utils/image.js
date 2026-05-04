export function imageFileToPayload(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.onload = () => {
      const dataUrl = String(reader.result);
      resolve({
        name: file.name,
        mimeType: file.type,
        size: file.size,
        previewUrl: dataUrl,
        base64: dataUrl.split(",")[1]
      });
    };
    reader.readAsDataURL(file);
  });
}
