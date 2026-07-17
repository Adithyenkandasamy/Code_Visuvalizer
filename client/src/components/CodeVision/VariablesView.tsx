"use client";

import React from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { TraceEvent } from "@/types/engine";

interface VariablesViewProps {
  event: TraceEvent | null;
  traceError: string | null | undefined;
  output: string | null | undefined;
}

export function VariablesView({ event, traceError, output }: VariablesViewProps) {
  return (
    <div className="h-full flex flex-col bg-zinc-950">
      <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-900/50 text-sm font-medium text-zinc-400">
        State & Variables
      </div>
      
      <ScrollArea className="flex-1 p-4">
        {event ? (
          <div className="space-y-6">
            {/* Event Info */}
            <div className="bg-zinc-900/50 rounded-lg p-3 border border-zinc-800">
              <div className="text-xs text-zinc-500 mb-1">Current Action</div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-xs font-mono bg-zinc-800 text-zinc-300 capitalize">
                  {event.event}
                </span>
                <span className="text-sm font-mono text-zinc-200">
                  {event.function}()
                </span>
              </div>
              {event.return_value && (
                <div className="mt-2 text-sm">
                  <span className="text-zinc-500">returns: </span>
                  <span className="font-mono text-emerald-400">{event.return_value}</span>
                </div>
              )}
            </div>

            {/* Locals */}
            <div>
              <h3 className="text-sm font-medium text-zinc-400 mb-3 flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-500" />
                Local Variables
              </h3>
              {Object.keys(event.locals).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(event.locals).map(([key, value]) => (
                    <div key={key} className="flex flex-col bg-zinc-900 rounded p-2 border border-zinc-800/50">
                      <span className="text-xs font-mono text-blue-400">{key}</span>
                      <span className="text-sm font-mono text-zinc-300 break-all">{value}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-zinc-600 italic">No local variables</div>
              )}
            </div>

            {/* Error output */}
            {traceError && (
              <div>
                <h3 className="text-sm font-medium text-red-400 mb-2">Exception</h3>
                <div className="bg-red-950/20 text-red-400 p-2 rounded border border-red-900/50 text-xs font-mono whitespace-pre-wrap">
                  {traceError}
                </div>
              </div>
            )}

            {/* Stdout */}
            {output && (
              <div>
                <h3 className="text-sm font-medium text-zinc-400 mb-2">Stdout (Print)</h3>
                <div className="bg-black text-zinc-300 p-2 rounded border border-zinc-800 text-xs font-mono whitespace-pre-wrap">
                  {output}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-40 text-zinc-500 space-y-2">
            <div className="w-10 h-10 border border-zinc-800 rounded-full flex items-center justify-center text-zinc-700">
              {'{ }'}
            </div>
            <span className="text-sm">No state available</span>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
