export interface TraceEvent {
  sequence: number;
  event: 'call' | 'line' | 'return' | 'exception';
  line: number;
  function: string;
  filename: string;
  call_depth: number;
  locals: Record<string, string>;
  globals: Record<string, string> | null;
  timestamp_ns: number | null;
  return_value: string | null;
  exception_info: string | null;
}

export interface TraceFrame {
  function_name: string;
  call_depth: number;
  events: TraceEvent[];
}

export interface VisualizeResponse {
  events: TraceEvent[];
  frames: TraceFrame[];
  output: string;
  error: string | null;
  total_events: number;
  max_depth: number;
  success: boolean;
}
