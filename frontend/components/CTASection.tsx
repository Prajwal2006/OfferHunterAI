"use client";

import { motion, useInView } from "framer-motion";
import { useRef } from "react";
import Link from "next/link";
import { ArrowRight, Zap, Sparkles, Bot, Mail } from "lucide-react";

export function CTASection() {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <section ref={ref} className="relative py-24 lg:py-32 overflow-hidden">
      {/* Background elements */}
      <div className="absolute inset-0 pointer-events-none">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 50, repeat: Infinity, ease: "linear" }}
          className="absolute top-1/4 -left-20 w-96 h-96 border border-primary/10 rounded-full"
        />
        <motion.div
          animate={{ rotate: -360 }}
          transition={{ duration: 40, repeat: Infinity, ease: "linear" }}
          className="absolute bottom-1/4 -right-20 w-80 h-80 border border-secondary/10 rounded-full"
        />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
          className="relative"
        >
          {/* Main card */}
          <div className="relative rounded-3xl overflow-hidden">
            {/* Animated gradient border */}
            <div className="absolute inset-0 bg-gradient-to-r from-primary via-secondary to-accent rounded-3xl animate-pulse opacity-20" />
            <div className="absolute inset-[1px] bg-card rounded-3xl" />

            <div className="relative p-8 lg:p-16 text-center">
              {/* Floating icons */}
              <div className="absolute inset-0 pointer-events-none overflow-hidden">
                <motion.div
                  animate={{ y: [-20, 20, -20], x: [-10, 10, -10] }}
                  transition={{ duration: 6, repeat: Infinity }}
                  className="absolute top-10 left-10 lg:top-20 lg:left-20"
                >
                  <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
                    <Bot className="w-6 h-6 text-primary" />
                  </div>
                </motion.div>
                <motion.div
                  animate={{ y: [20, -20, 20], x: [10, -10, 10] }}
                  transition={{ duration: 7, repeat: Infinity }}
                  className="absolute top-10 right-10 lg:top-20 lg:right-20"
                >
                  <div className="w-12 h-12 rounded-xl bg-secondary/10 border border-secondary/20 flex items-center justify-center">
                    <Sparkles className="w-6 h-6 text-secondary" />
                  </div>
                </motion.div>
                <motion.div
                  animate={{ y: [-15, 15, -15], x: [-15, 5, -15] }}
                  transition={{ duration: 5, repeat: Infinity }}
                  className="absolute bottom-10 left-10 lg:bottom-20 lg:left-32"
                >
                  <div className="w-12 h-12 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center">
                    <Mail className="w-6 h-6 text-accent" />
                  </div>
                </motion.div>
                <motion.div
                  animate={{ y: [15, -15, 15], x: [15, -5, 15] }}
                  transition={{ duration: 8, repeat: Infinity }}
                  className="absolute bottom-10 right-10 lg:bottom-20 lg:right-32"
                >
                  <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
                    <Zap className="w-6 h-6 text-primary" />
                  </div>
                </motion.div>
              </div>

              {/* Content */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: 0.3 }}
              >
                <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-6 text-balance">
                  <span className="text-foreground">Ready to Transform</span>
                  <br />
                  <span className="text-gradient">Your Job Search?</span>
                </h2>

                <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-10 text-pretty">
                  Join thousands of professionals who have accelerated their career journey 
                  with intelligent automation and personalized outreach.
                </p>

                <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                  <Link href="/agents">
                    <motion.button
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      className="btn-futuristic group flex items-center gap-3 px-8 py-4 rounded-2xl font-semibold text-lg bg-gradient-to-r from-primary to-secondary text-primary-foreground shadow-xl shadow-primary/25"
                    >
                      <Zap className="w-5 h-5" />
                      <span>Get Started Now</span>
                      <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                    </motion.button>
                  </Link>

                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="flex -space-x-2">
                      {[1, 2, 3].map((i) => (
                        <div
                          key={i}
                          className="w-8 h-8 rounded-full bg-gradient-to-br from-primary/30 to-secondary/30 border-2 border-background"
                        />
                      ))}
                    </div>
                    <span>Join 2,000+ active users</span>
                  </div>
                </div>
              </motion.div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
