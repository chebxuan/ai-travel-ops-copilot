"use client";
import { useEffect, useRef } from "react";
import { animate } from "animejs";
export default function Reveal({ children, className }) {
  const root = useRef(null);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const animations = [];
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) if (entry.isIntersecting) {
        animations.push(animate(entry.target, { opacity: { from: 0, to: 1 }, translateY: { from: 18, to: 0 }, duration: 750, ease: "out(3)" }));
        observer.unobserve(entry.target);
      }
    }, { threshold: .08 });
    root.current.querySelectorAll("[data-reveal]").forEach((node) => observer.observe(node));
    return () => { observer.disconnect(); animations.forEach((animation) => animation.revert()); };
  }, []);
  return <div ref={root} className={className}>{children}</div>;
}
