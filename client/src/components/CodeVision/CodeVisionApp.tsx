"use client";

import React, { useState, useEffect, useRef } from "react";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { CodeEditor } from "./CodeEditor";
import { PlaybackControls } from "./PlaybackControls";
import { VariablesView } from "./VariablesView";
import { CodeHighlighter } from "./CodeHighlighter";
import { TraceEvent, VisualizeResponse } from "@/types/engine";

const DEFAULT_CODE = `def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

result = fibonacci(4)
print(f"Result: {result}")
`;

export function CodeVisionApp() {
  const [code, setCode] = useState(DEFAULT_CODE);
  const [trace, setTrace] = useState<VisualizeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const playInterval = useRef<NodeJS.Timeout | null>(null);

  const handleVisualize = async () => {
    setLoading(true);
    setError(null);
    setTrace(null);
    setCurrentIndex(0);
    setIsPlaying(false);

    try {
      // In development, assume FastAPI runs on port 8000
      const response = await fetch("http://localhost:8000/api/v1/visualize", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ code }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to visualize code");
      }

      const data: VisualizeResponse = await response.json();
      setTrace(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Playback Logic
  useEffect(() => {
    if (isPlaying && trace && trace.events.length > 0) {
      playInterval.current = setInterval(() => {
        setCurrentIndex((prev) => {
          if (prev >= trace.events.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 800); // 800ms per step
    } else {
      if (playInterval.current) {
        clearInterval(playInterval.current);
      }
    }

    return () => {
      if (playInterval.current) {
        clearInterval(playInterval.current);
      }
    };
  }, [isPlaying, trace]);

  const currentEvent = trace?.events[currentIndex] || null;
  // Get wrapper generated code if available, but for now we just show the user code
  const displayCode = code;

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-50">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-950">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center">
            <span className="text-white font-bold text-lg">CV</span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight">Code Vision</h1>
        </div>
        <div>
          <button 
            onClick={handleVisualize}
            disabled={loading}
            className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium transition-colors disabled:opacity-50"
          >
            {loading ? "Analyzing..." : "Visualize Execution"}
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="flex-1 overflow-hidden">
        <ResizablePanelGroup direction="horizontal">
          {/* Left: Editor */}
          <ResizablePanel defaultSize={30} minSize={20}>
            <div className="h-full flex flex-col border-r border-zinc-800">
              <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-900/50 text-sm font-medium text-zinc-400">
                Source Code
              </div>
              <div className="flex-1">
                <CodeEditor code={code} onChange={setCode} />
              </div>
            </div>
          </ResizablePanel>

          <ResizableHandle className="bg-zinc-800" />

          {/* Center: Highlighter */}
          <ResizablePanel defaultSize={45} minSize={30}>
            <div className="h-full flex flex-col border-r border-zinc-800">
              <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-900/50 text-sm font-medium text-zinc-400">
                Execution Flow
              </div>
              <div className="flex-1 overflow-hidden">
                {error ? (
                  <div className="p-6 text-red-400 bg-red-950/20 h-full">
                    <h3 className="font-semibold mb-2">Error</h3>
                    <pre className="text-sm whitespace-pre-wrap font-mono">{error}</pre>
                  </div>
                ) : trace ? (
                  <CodeHighlighter 
                    code={displayCode} 
                    currentLine={currentEvent?.line || 0} 
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-zinc-500">
                    Click "Visualize Execution" to begin.
                  </div>
                )}
              </div>
            </div>
          </ResizablePanel>

          <ResizableHandle className="bg-zinc-800" />

          {/* Right: Variables Panel */}
          <ResizablePanel defaultSize={25} minSize={20}>
            <VariablesView 
              event={currentEvent} 
              traceError={trace?.error} 
              output={trace?.output} 
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      </main>

      {/* Bottom: Playback Controls */}
      <footer className="h-24 border-t border-zinc-800 bg-zinc-900 flex flex-col">
        {trace && (
          <PlaybackControls 
            currentIndex={currentIndex}
            totalEvents={trace.events.length}
            isPlaying={isPlaying}
            onPlayPause={() => setIsPlaying(!isPlaying)}
            onNext={() => setCurrentIndex(Math.min(currentIndex + 1, trace.events.length - 1))}
            onPrev={() => setCurrentIndex(Math.max(currentIndex - 1, 0))}
            onReset={() => {
              setIsPlaying(false);
              setCurrentIndex(0);
            }}
            onChange={(idx) => {
              setIsPlaying(false);
              setCurrentIndex(idx);
            }}
          />
        )}
      </footer>
    </div>
  );
}
