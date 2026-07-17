"use client";

import React from "react";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Play, Pause, SkipForward, SkipBack, RotateCcw } from "lucide-react";

interface PlaybackControlsProps {
  currentIndex: number;
  totalEvents: number;
  isPlaying: boolean;
  onPlayPause: () => void;
  onNext: () => void;
  onPrev: () => void;
  onReset: () => void;
  onChange: (index: number) => void;
}

export function PlaybackControls({
  currentIndex,
  totalEvents,
  isPlaying,
  onPlayPause,
  onNext,
  onPrev,
  onReset,
  onChange,
}: PlaybackControlsProps) {
  return (
    <div className="flex flex-col justify-center h-full px-6 py-2 gap-4">
      {/* Slider */}
      <div className="flex items-center gap-4">
        <span className="text-xs font-mono text-zinc-500 w-12 text-right">
          {currentIndex + 1}
        </span>
        <Slider
          value={[currentIndex]}
          max={totalEvents > 0 ? totalEvents - 1 : 0}
          step={1}
          onValueChange={(vals) => onChange(vals[0])}
          className="flex-1"
        />
        <span className="text-xs font-mono text-zinc-500 w-12">
          {totalEvents}
        </span>
      </div>

      {/* Buttons */}
      <div className="flex items-center justify-center gap-2">
        <Button variant="ghost" size="icon" onClick={onReset} className="text-zinc-400 hover:text-white">
          <RotateCcw className="w-4 h-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={onPrev} disabled={currentIndex === 0} className="text-zinc-400 hover:text-white">
          <SkipBack className="w-4 h-4" />
        </Button>
        <Button 
          variant="secondary" 
          size="icon" 
          onClick={onPlayPause}
          className="bg-indigo-600 text-white hover:bg-indigo-500 rounded-full w-10 h-10 shadow-lg shadow-indigo-900/20"
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
        </Button>
        <Button variant="ghost" size="icon" onClick={onNext} disabled={currentIndex >= totalEvents - 1} className="text-zinc-400 hover:text-white">
          <SkipForward className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
