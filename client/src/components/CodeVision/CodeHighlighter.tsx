"use client";

import React, { useMemo } from "react";
import { motion } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

interface CodeHighlighterProps {
  code: string;
  currentLine: number;
}

export function CodeHighlighter({ code, currentLine }: CodeHighlighterProps) {
  const lines = useMemo(() => code.split("\n"), [code]);

  return (
    <ScrollArea className="h-full w-full bg-[#1e1e1e]">
      <div className="p-4 font-mono text-sm leading-relaxed tracking-tight select-none">
        {lines.map((lineContent, index) => {
          const lineNumber = index + 1;
          const isActive = currentLine === lineNumber;

          return (
            <div
              key={lineNumber}
              className={cn(
                "relative flex items-center group px-2 rounded-md transition-colors",
                isActive ? "text-indigo-100" : "text-zinc-400 hover:bg-zinc-800/30"
              )}
            >
              {/* Highlight Background */}
              {isActive && (
                <motion.div
                  layoutId="highlight"
                  className="absolute inset-0 bg-indigo-500/20 border-l-2 border-indigo-500 rounded-r-md pointer-events-none"
                  initial={false}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
              
              {/* Line Number */}
              <div className="w-8 flex-shrink-0 text-right pr-4 text-zinc-600 select-none z-10">
                {lineNumber}
              </div>
              
              {/* Line Content */}
              <div className="flex-1 whitespace-pre z-10">
                {lineContent || " "}
              </div>
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}
