type HeaderMeta = {
  headerMeta: {
    timestamp: number;
  };
};

type TimestampSource = {
  timestamp?: unknown;
};

type ResponseWithTimestamps = {
  created_at?: number;
  output?: unknown[];
};

function normalizeEpochMs(value: number): number {
  return value < 1_000_000_000_000 ? value * 1000 : value;
}

function toTimestamp(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return normalizeEpochMs(value);
  }

  if (typeof value !== "string") return null;

  const trimmed = value.trim();
  if (!trimmed) return null;

  const numeric = Number(trimmed);
  if (Number.isFinite(numeric)) {
    return normalizeEpochMs(numeric);
  }

  const parsed = Date.parse(trimmed);
  return Number.isNaN(parsed) ? null : parsed;
}

function resolveLatestOutputTimestamp(messages?: unknown[]): number | null {
  if (!messages?.length) return null;

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index] as TimestampSource | undefined;
    const resolved = toTimestamp(message?.timestamp);
    if (resolved !== null) return resolved;
  }

  return null;
}

export function withRequestHeaderMeta<T extends object>(
  data: T,
  timestamp = Date.now(),
): T & HeaderMeta {
  return {
    ...data,
    headerMeta: {
      timestamp,
    },
  };
}

export function resolveResponseHeaderTimestamp(
  response?: ResponseWithTimestamps,
  currentTimestamp?: number,
): number {
  const outputTimestamp = resolveLatestOutputTimestamp(response?.output);
  if (outputTimestamp !== null) {
    return outputTimestamp;
  }

  if (typeof currentTimestamp === "number" && Number.isFinite(currentTimestamp)) {
    return currentTimestamp;
  }

  const createdAt = toTimestamp(response?.created_at);
  if (createdAt !== null) {
    return createdAt;
  }

  return Date.now();
}

export function withResponseHeaderMeta<T extends ResponseWithTimestamps>(
  data: T,
  currentTimestamp?: number,
): T & HeaderMeta {
  return {
    ...data,
    headerMeta: {
      timestamp: resolveResponseHeaderTimestamp(data, currentTimestamp),
    },
  };
}
