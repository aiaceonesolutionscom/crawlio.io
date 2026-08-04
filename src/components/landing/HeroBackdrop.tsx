import React from 'react';
import { motion } from 'framer-motion';

const NODES = [
{ x: 8, y: 22, r: 2.4, delay: 0 },
{ x: 22, y: 62, r: 1.8, delay: 0.4 },
{ x: 36, y: 30, r: 3, delay: 0.8 },
{ x: 51, y: 74, r: 2, delay: 1.2 },
{ x: 64, y: 40, r: 2.6, delay: 0.2 },
{ x: 79, y: 66, r: 1.9, delay: 1.6 },
{ x: 91, y: 28, r: 2.8, delay: 1 }];


const EDGES = [
[0, 2],
[1, 2],
[2, 4],
[3, 4],
[4, 6],
[5, 6],
[1, 3]];


/** Animated crawl-graph backdrop. Acts as the "animated background / video" slot in the hero. */
export function HeroBackdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="grid-backdrop absolute inset-0 opacity-70" />

      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        {EDGES.map(([a, b], i) =>
        <motion.line
          key={i}
          x1={NODES[a].x}
          y1={NODES[a].y}
          x2={NODES[b].x}
          y2={NODES[b].y}
          stroke="#CBFF4D"
          strokeWidth="0.12"
          strokeOpacity="0.35"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: [0, 1, 1, 0] }}
          transition={{ duration: 7, delay: i * 0.5, repeat: Infinity, ease: 'easeInOut' }} />

        )}
        {NODES.map((n, i) =>
        <motion.circle
          key={i}
          cx={n.x}
          cy={n.y}
          r={n.r / 6}
          fill="#CBFF4D"
          initial={{ opacity: 0.25 }}
          animate={{ opacity: [0.2, 0.85, 0.2] }}
          transition={{ duration: 4.5, delay: n.delay, repeat: Infinity, ease: 'easeInOut' }} />

        )}
      </svg>

      <motion.div
        className="absolute -left-24 top-[-10%] h-[380px] w-[380px] rounded-full bg-signal/[0.07] blur-[110px]"
        animate={{ x: [0, 60, 0], y: [0, 40, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: 'easeInOut' }} />
      
      <motion.div
        className="absolute right-[-6%] top-[35%] h-[320px] w-[320px] rounded-full bg-sky-soft/[0.06] blur-[110px]"
        animate={{ x: [0, -50, 0], y: [0, -30, 0] }}
        transition={{ duration: 22, repeat: Infinity, ease: 'easeInOut' }} />
      

      {/* Legibility overlay for anything layered on top of the animation */}
      <div className="absolute inset-0 bg-gradient-to-b from-ink-950/70 via-ink-950/60 to-ink-950" />
    </div>);

}