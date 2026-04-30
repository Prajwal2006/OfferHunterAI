"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Settings,
  User,
  Mail,
  Key,
  Bell,
  Palette,
  Save,
  ExternalLink,
  CheckCircle,
  Shield,
  Zap,
} from "lucide-react";

interface SettingsSection {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const sections: SettingsSection[] = [
  { id: "profile", label: "Profile", icon: <User className="w-4 h-4" /> },
  { id: "integrations", label: "Integrations", icon: <Key className="w-4 h-4" /> },
  { id: "notifications", label: "Notifications", icon: <Bell className="w-4 h-4" /> },
  { id: "preferences", label: "Preferences", icon: <Palette className="w-4 h-4" /> },
];

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState("profile");
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Mock form state
  const [profile, setProfile] = useState({
    name: "Alex Chen",
    email: "alex@example.com",
    role: "Software Engineer",
    bio: "Passionate about AI and automation. Looking for ML/AI roles at innovative companies.",
  });

  const [integrations, setIntegrations] = useState({
    gmail: true,
    linkedin: false,
    openai: true,
    anthropic: false,
  });

  const [notifications, setNotifications] = useState({
    emailSent: true,
    newCompany: true,
    followUpReminder: true,
    weeklyDigest: false,
  });

  const handleSave = async () => {
    setIsSaving(true);
    // Simulate API call
    await new Promise((r) => setTimeout(r, 1000));
    setIsSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
            <Settings className="w-5 h-5 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Manage your profile, integrations, and preferences
        </p>
      </motion.div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Sidebar Navigation */}
        <motion.div
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className="lg:w-56 flex-shrink-0"
        >
          <nav className="glass border border-border rounded-2xl p-2 space-y-1">
            {sections.map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                  activeSection === section.id
                    ? "bg-primary/20 text-primary border border-primary/30"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {section.icon}
                {section.label}
              </button>
            ))}
          </nav>
        </motion.div>

        {/* Content */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex-1"
        >
          <div className="glass border border-border rounded-2xl p-6">
            {/* Profile Section */}
            {activeSection === "profile" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-foreground">Profile Settings</h2>
                  <div className="flex items-center gap-2 text-xs text-emerald-500">
                    <Shield className="w-3.5 h-3.5" />
                    <span>Data encrypted</span>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-3xl font-bold text-primary-foreground">
                    {profile.name[0]}
                  </div>
                  <div>
                    <button className="px-4 py-2 rounded-xl text-sm font-medium bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 transition-colors">
                      Change Avatar
                    </button>
                    <p className="text-xs text-muted-foreground mt-2">JPG, PNG or GIF. Max 2MB</p>
                  </div>
                </div>

                <div className="grid gap-4">
                  <div>
                    <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Full Name
                    </label>
                    <input
                      type="text"
                      value={profile.name}
                      onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                      className="w-full bg-muted/30 border border-border rounded-xl px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Email Address
                    </label>
                    <input
                      type="email"
                      value={profile.email}
                      onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                      className="w-full bg-muted/30 border border-border rounded-xl px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Current Role
                    </label>
                    <input
                      type="text"
                      value={profile.role}
                      onChange={(e) => setProfile({ ...profile, role: e.target.value })}
                      className="w-full bg-muted/30 border border-border rounded-xl px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Bio / Career Summary
                    </label>
                    <textarea
                      value={profile.bio}
                      onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
                      rows={4}
                      className="w-full bg-muted/30 border border-border rounded-xl px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all resize-none"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      This will be used to personalize your outreach emails
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Integrations Section */}
            {activeSection === "integrations" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-foreground">Connected Services</h2>
                  <div className="flex items-center gap-2 text-xs text-primary">
                    <Zap className="w-3.5 h-3.5" />
                    <span>2 active</span>
                  </div>
                </div>

                <div className="space-y-4">
                  {[
                    { id: "gmail", name: "Gmail API", desc: "Send emails on your behalf", icon: <Mail className="w-5 h-5" /> },
                    { id: "linkedin", name: "LinkedIn", desc: "Scrape job postings and company data", icon: <ExternalLink className="w-5 h-5" /> },
                    { id: "openai", name: "OpenAI", desc: "GPT-4 for email generation", icon: <Zap className="w-5 h-5" /> },
                    { id: "anthropic", name: "Anthropic", desc: "Claude for personalization", icon: <Zap className="w-5 h-5" /> },
                  ].map((integration) => {
                    const isConnected = integrations[integration.id as keyof typeof integrations];
                    return (
                      <motion.div
                        key={integration.id}
                        whileHover={{ scale: 1.01 }}
                        className={`flex items-center justify-between p-4 rounded-xl border transition-all ${
                          isConnected
                            ? "bg-emerald-500/10 border-emerald-500/30"
                            : "bg-muted/30 border-border hover:border-primary/30"
                        }`}
                      >
                        <div className="flex items-center gap-4">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                            isConnected ? "bg-emerald-500/20 text-emerald-500" : "bg-muted text-muted-foreground"
                          }`}>
                            {integration.icon}
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-foreground">{integration.name}</div>
                            <div className="text-xs text-muted-foreground">{integration.desc}</div>
                          </div>
                        </div>
                        <button
                          onClick={() => setIntegrations({ ...integrations, [integration.id]: !isConnected })}
                          className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                            isConnected
                              ? "bg-emerald-500/20 text-emerald-500 border border-emerald-500/30"
                              : "bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30"
                          }`}
                        >
                          {isConnected ? "Connected" : "Connect"}
                        </button>
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Notifications Section */}
            {activeSection === "notifications" && (
              <div className="space-y-6">
                <h2 className="text-lg font-semibold text-foreground">Notification Preferences</h2>

                <div className="space-y-4">
                  {[
                    { id: "emailSent", label: "Email Sent", desc: "Get notified when an email is sent" },
                    { id: "newCompany", label: "New Company Found", desc: "Alert when agents discover a matching company" },
                    { id: "followUpReminder", label: "Follow-up Reminders", desc: "Remind me to follow up on unanswered emails" },
                    { id: "weeklyDigest", label: "Weekly Digest", desc: "Summary of your job search progress" },
                  ].map((notif) => {
                    const isEnabled = notifications[notif.id as keyof typeof notifications];
                    return (
                      <div
                        key={notif.id}
                        className="flex items-center justify-between p-4 rounded-xl bg-muted/30 border border-border"
                      >
                        <div>
                          <div className="text-sm font-semibold text-foreground">{notif.label}</div>
                          <div className="text-xs text-muted-foreground">{notif.desc}</div>
                        </div>
                        <button
                          onClick={() => setNotifications({ ...notifications, [notif.id]: !isEnabled })}
                          className={`relative w-12 h-6 rounded-full transition-colors ${
                            isEnabled ? "bg-primary" : "bg-muted"
                          }`}
                        >
                          <motion.div
                            layout
                            className="absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm"
                            style={{ left: isEnabled ? "calc(100% - 20px)" : "4px" }}
                          />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Preferences Section */}
            {activeSection === "preferences" && (
              <div className="space-y-6">
                <h2 className="text-lg font-semibold text-foreground">App Preferences</h2>

                <div className="space-y-4">
                  <div>
                    <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Default Email Tone
                    </label>
                    <select className="w-full bg-muted/30 border border-border rounded-xl px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all">
                      <option>Professional & Confident</option>
                      <option>Friendly & Casual</option>
                      <option>Formal & Traditional</option>
                      <option>Concise & Direct</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Target Industries
                    </label>
                    <input
                      type="text"
                      defaultValue="AI/ML, SaaS, Fintech, Healthcare Tech"
                      className="w-full bg-muted/30 border border-border rounded-xl px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Comma-separated list of industries to prioritize
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Company Size Preference
                    </label>
                    <select className="w-full bg-muted/30 border border-border rounded-xl px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all">
                      <option>All Sizes</option>
                      <option>Startup (1-50)</option>
                      <option>Small (51-200)</option>
                      <option>Medium (201-1000)</option>
                      <option>Enterprise (1000+)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-2">
                      Follow-up Delay (days)
                    </label>
                    <input
                      type="number"
                      defaultValue={5}
                      min={1}
                      max={14}
                      className="w-32 bg-muted/30 border border-border rounded-xl px-4 py-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Save Button */}
            <div className="mt-8 pt-6 border-t border-border flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                Changes are saved automatically
              </p>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleSave}
                disabled={isSaving}
                className="btn-futuristic flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-primary to-secondary text-primary-foreground font-semibold text-sm shadow-lg shadow-primary/20 disabled:opacity-50 transition-all"
              >
                {saved ? (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Saved!
                  </>
                ) : isSaving ? (
                  <>
                    <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4" />
                    Save Changes
                  </>
                )}
              </motion.button>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
