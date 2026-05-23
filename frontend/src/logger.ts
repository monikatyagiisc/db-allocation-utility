const PREFIX = '[FE]';

function formatArgs(args: unknown[]): unknown[] {
  return [PREFIX, ...args];
}

export const log = {
  info: (...args: unknown[]) => console.info(...formatArgs(args)),
  warn: (...args: unknown[]) => console.warn(...formatArgs(args)),
  error: (...args: unknown[]) => console.error(...formatArgs(args)),
  debug: (...args: unknown[]) => console.debug(...formatArgs(args)),
};
