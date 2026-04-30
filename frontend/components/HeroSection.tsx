"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Play, Sparkles, Zap, Target, Mail } from "lucide-react";

export function HeroSection() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });

  const y = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.5], [1, 0.9]);

  const features = [
    { icon: Target, label: "Smart Discovery" },
    { icon: Sparkles, label: "AI Personalization" },
    { icon: Mail, label: "Auto Outreach" },
    { icon: Zap, label: "Lightning Fast" },
  ];

  return (
    <section ref={ref} className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Parallax background elements */}
      <motion.div style={{ y, opacity }} className="absolute inset-0 pointer-events-none">
        <div className="absolute top-20 left-10 w-3 h-3 rounded-full bg-primary/50 particle" />
        <div className="absolute top-40 right-20 w-2 h-2 rounded-full bg-secondary/50 particle" style={{ animationDelay: "0.5s" }} />
        <div className="absolute bottom-40 left-1/4 w-4 h-4 rounded-full bg-accent/40 particle" style={{ animationDelay: "1s" }} />
        <div className="absolute top-1/3 right-1/3 w-2 h-2 rounded-full bg-primary/40 particle" style={{ animationDelay: "1.5s" }} />
        <div className="absolute bottom-1/3 right-10 w-3 h-3 rounded-full bg-secondary/30 particle" style={{ animationDelay: "2s" }} />
      </motion.div>

      <motion.div
        style={{ scale, opacity }}
        className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-32"
      >
        <div className="text-center">
          {/* Animated logo */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="flex justify-center mb-8"
          >
            <motion.div
              whileHover={{ scale: 1.05, rotate: 3 }}
              transition={{ type: "spring", stiffness: 300 }}
              className="relative"
            >
              <Image
                src="/logo.png"
                alt="OfferHunter AI"
                width={180}
                height={180}
                className="logo-animate"
                priority
              />
              {/* Orbiting particles */}
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                className="absolute inset-0"
              >
                <div className="absolute -top-2 left-1/2 w-2 h-2 rounded-full bg-primary shadow-lg shadow-primary/50" />
              </motion.div>
              <motion.div
                animate={{ rotate: -360 }}
                transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                className="absolute inset-0"
              >
                <div className="absolute top-1/2 -right-2 w-2 h-2 rounded-full bg-secondary shadow-lg shadow-secondary/50" />
              </motion.div>
            </motion.div>
          </motion.div>

          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-primary/30 mb-8"
          >
            <Sparkles className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-foreground/80">
              AI-Powered Job Hunting Revolution
            </span>
          </motion.div>

          {/* Main heading */}
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.8 }}
            className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6 text-balance"
          >
            <span className="text-foreground">Land Your Dream Job</span>
            <br />
            <span className="text-gradient neon-text">10x Faster with AI</span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.8 }}
            className="text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 text-pretty"
          >
            Our intelligent agents discover opportunities, craft personalized outreach, 
            and automate your job hunt while you focus on what matters most.
          </motion.p>

          {/* CTA Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16"
          >
            <Link href="/agents">
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className="btn-futuristic relative group flex items-center gap-2 px-8 py-4 rounded-2xl font-semibold text-lg bg-gradient-to-r from-primary to-secondary text-primary-foreground shadow-xl shadow-primary/25"
              >
                <Zap className="w-5 h-5" />
                <span>Start Hunting</span>
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </motion.button>
            </Link>

            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="flex items-center gap-2 px-8 py-4 rounded-2xl font-semibold text-lg glass border border-border hover:border-primary/50 transition-colors"
            >
              <Play className="w-5 h-5 text-primary" />
              <span>Watch Demo</span>
            </motion.button>
          </motion.div>

          {/* Feature pills */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.9 }}
            className="flex flex-wrap items-center justify-center gap-3"
          >
            {features.map((feature, i) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={feature.label}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 1 + i * 0.1 }}
                  whileHover={{ scale: 1.05, y: -2 }}
                  className="flex items-center gap-2 px-4 py-2 rounded-full bg-muted/50 border border-border hover:border-primary/30 transition-all cursor-default"
                >
                  <Icon className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-foreground/80">{feature.label}</span>
                </motion.div>
              );
            })}
          </motion.div>
        </div>

        {/* Scroll indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
        >
          <motion.div
            animate={{ y: [0, 10, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="flex flex-col items-center gap-2"
          >
            <span className="text-xs text-muted-foreground">Scroll to explore</span>
            <div className="w-6 h-10 rounded-full border-2 border-muted-foreground/30 flex justify-center pt-2">
              <motion.div
                animate={{ y: [0, 12, 0] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className="w-1.5 h-3 rounded-full bg-primary"
              />
            </div>
          </motion.div>
        </motion.div>
      </motion.div>
    </section>
  );
}
