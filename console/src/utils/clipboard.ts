/**
 * Copy text to clipboard with fallback for non-secure contexts or blocked permissions.
 * Returns true if successful, false if failed.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return false;

  // Try Clipboard API first
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Clipboard API blocked (permissions policy) or failed, fallback to execCommand
    }
  }

  // Fallback using execCommand (works in iframe, non-secure contexts)
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "-9999px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);

  let copied = false;
  try {
    textarea.focus();
    textarea.select();
    copied = document.execCommand("copy");
  } finally {
    document.body.removeChild(textarea);
  }

  return copied;
}