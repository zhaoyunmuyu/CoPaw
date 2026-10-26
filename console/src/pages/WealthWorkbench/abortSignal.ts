/** 兼容不支持 AbortSignal.throwIfAborted / reason 的旧内核。 */
export function throwIfRequestAborted(signal?: AbortSignal | null): void {
  if (signal?.aborted) {
    throw signal.reason ?? new DOMException("请求已取消", "AbortError");
  }
}
