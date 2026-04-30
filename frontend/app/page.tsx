"use client";

import { HeroSection } from "@/components/HeroSection";
import { FeaturesSection } from "@/components/FeaturesSection";
import { HowItWorksSection } from "@/components/HowItWorksSection";
import { StatsSection } from "@/components/StatsSection";
import { CTASection } from "@/components/CTASection";

export default function HomePage() {
  return (
    <div className="relative">
      <HeroSection />
      <FeaturesSection />
      <StatsSection />
      <HowItWorksSection />
      <CTASection />
    </div>
  );
}
