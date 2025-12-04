/**
 * Safe localStorage utilities with error handling
 */

const HISTORY_KEY = "cextract_history";
const MAX_HISTORY_ITEMS = 50;

export interface HistoryItem {
  document_name: string;
  pack_id: string;
  report_markdown: string;
  timestamp?: number;
}

/**
 * Get document history from localStorage
 */
export function getHistory(): HistoryItem[] {
  try {
    const stored = localStorage.getItem(HISTORY_KEY);
    if (!stored) return [];

    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) {
      console.warn("History is not an array, resetting");
      return [];
    }

    return parsed;
  } catch (e) {
    console.error("Failed to read history from localStorage:", e);
    return [];
  }
}

/**
 * Add a new item to document history
 */
export function addToHistory(item: HistoryItem): boolean {
  try {
    const history = getHistory();

    // Add timestamp if not present
    const itemWithTimestamp = {
      ...item,
      timestamp: item.timestamp || Date.now(),
    };

    // Add to beginning of array
    history.unshift(itemWithTimestamp);

    // Keep only the last MAX_HISTORY_ITEMS
    const limitedHistory = history.slice(0, MAX_HISTORY_ITEMS);

    localStorage.setItem(HISTORY_KEY, JSON.stringify(limitedHistory));
    return true;
  } catch (e) {
    console.error("Failed to add to history:", e);

    // Try to recover by starting fresh with just this item
    try {
      localStorage.setItem(
        HISTORY_KEY,
        JSON.stringify([{ ...item, timestamp: Date.now() }])
      );
      return true;
    } catch (e2) {
      console.error("Failed to recover history:", e2);
      return false;
    }
  }
}

/**
 * Clear all document history
 */
export function clearHistory(): boolean {
  try {
    localStorage.removeItem(HISTORY_KEY);
    return true;
  } catch (e) {
    console.error("Failed to clear history:", e);
    return false;
  }
}

/**
 * Get history statistics
 */
export function getHistoryStats() {
  const history = getHistory();

  const passCount = history.filter((item) =>
    item.report_markdown && /\*\*Overall:\*\*.*PASS/.test(item.report_markdown)
  ).length;

  const failCount = history.length - passCount;

  return {
    total: history.length,
    pass: passCount,
    fail: failCount,
  };
}
