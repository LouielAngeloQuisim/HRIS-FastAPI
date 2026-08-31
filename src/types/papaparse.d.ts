declare module 'papaparse' {
  interface ParseResult<T> {
    data: T[];
    errors: Array<{ message: string; code?: string }>;
    meta: { fields?: string[] };
  }
  interface ParseConfig<T> {
    header?: boolean;
    skipEmptyLines?: boolean;
    dynamicTyping?: boolean;
  }
  export interface Parse {
    <T>(data: string, config?: ParseConfig<T>): ParseResult<T>;
  }
  export const parse: Parse;
  const _default: { parse: Parse };
  export default _default;
}
