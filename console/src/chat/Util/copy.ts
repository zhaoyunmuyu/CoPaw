export async function copy(text: string): Promise<void> {
  // Try modern Clipboard API first
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Clipboard API blocked by permissions policy, fall back to execCommand
    }
  }

  // Fallback to execCommand for restricted contexts
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    const success = document.execCommand('copy');
    if (!success) {
      throw new Error('execCommand copy failed');
    }
  } finally {
    document.body.removeChild(textarea);
  }
}
