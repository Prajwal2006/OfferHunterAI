"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, CheckCircle, XCircle, Edit3, Send, Shield, ChevronDown, ChevronUp } from "lucide-react";
import { Email } from "@/lib/types";
import { MOCK_EMAILS } from "@/lib/mockData";

type ReviewStatus = "pending" | "approved" | "rejected" | "sent";

interface EmailWithLocalStatus extends Email {
  localStatus: ReviewStatus;
  editedSubject?: string;
  editedBody?: string;
}

export default function ReviewPage() {
  const [emails, setEmails] = useState<EmailWithLocalStatus[]>(
    MOCK_EMAILS.map((e) => ({
      ...e,
      localStatus:
        e.status === "pending_approval"
          ? "pending"
          : e.status === "sent"
          ? "sent"
          : "pending",
    }))
  );
  const [expandedId, setExpandedId] = useState<string | null>(emails[0]?.id ?? null);
  const [editingId, setEditingId] = useState<string | null>(null);

  const pending = emails.filter((e) => e.localStatus === "pending");
  const approved = emails.filter((e) => e.localStatus === "approved");
  const sent = emails.filter((e) => e.localStatus === "sent");
  const rejected = emails.filter((e) => e.localStatus === "rejected");

  function approve(id: string) {
    setEmails((prev) =>
      prev.map((e) => (e.id === id ? { ...e, localStatus: "approved" } : e))
    );
  }

  function reject(id: string) {
    setEmails((prev) =>
      prev.map((e) => (e.id === id ? { ...e, localStatus: "rejected" } : e))
    );
  }

  function markSent(id: string) {
    setEmails((prev) =>
      prev.map((e) =>
        e.id === id
          ? { ...e, localStatus: "sent", sent_at: new Date().toISOString() }
          : e
      )
    );
  }

  function startEdit(id: string) {
    setEditingId(id);
    setExpandedId(id);
  }

  function saveEdit(id: string, subject: string, body: string) {
    setEmails((prev) =>
      prev.map((e) =>
        e.id === id ? { ...e, editedSubject: subject, editedBody: body } : e
      )
    );
    setEditingId(null);
  }

  const statusColor = {
    pending: "border-amber-500/30 bg-amber-500/5",
    approved: "border-emerald-500/30 bg-emerald-500/5",
    rejected: "border-red-500/30 bg-red-500/5",
    sent: "border-primary/30 bg-primary/5",
  };

  const statusBadge = {
    pending: "bg-amber-500/20 text-amber-500 border-amber-500/30",
    approved: "bg-emerald-500/20 text-emerald-500 border-emerald-500/30",
    rejected: "bg-red-500/20 text-red-500 border-red-500/30",
    sent: "bg-primary/20 text-primary border-primary/30",
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                <Mail className="w-5 h-5 text-primary-foreground" />
              </div>
              <h1 className="text-2xl font-bold text-foreground">
                Email Review
              </h1>
            </div>
            <p className="text-sm text-muted-foreground">
              Review and approve AI-drafted emails before sending
            </p>
          </div>

          {/* HITL Notice */}
          <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-secondary/10 border border-secondary/30">
            <Shield className="w-4 h-4 text-secondary flex-shrink-0" />
            <span className="text-xs text-secondary font-medium">
              Human-in-the-Loop Required
            </span>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mt-6">
          {[
            { label: "Pending", count: pending.length, color: "text-amber-500", gradient: "from-amber-500/20 to-amber-500/5" },
            { label: "Approved", count: approved.length, color: "text-emerald-500", gradient: "from-emerald-500/20 to-emerald-500/5" },
            { label: "Sent", count: sent.length, color: "text-primary", gradient: "from-primary/20 to-primary/5" },
            { label: "Rejected", count: rejected.length, color: "text-red-500", gradient: "from-red-500/20 to-red-500/5" },
          ].map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ scale: 1.02, y: -2 }}
              className="glass border border-border rounded-xl p-4 text-center relative overflow-hidden group"
            >
              <div className={`absolute inset-0 bg-gradient-to-br ${s.gradient} opacity-0 group-hover:opacity-100 transition-opacity`} />
              <div className={`relative z-10 text-2xl font-bold ${s.color}`}>{s.count}</div>
              <div className="relative z-10 text-xs text-muted-foreground">{s.label}</div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Email List */}
      <div className="space-y-4">
        <AnimatePresence>
          {emails.map((email, index) => {
            const isExpanded = expandedId === email.id;
            const isEditing = editingId === email.id;

            return (
              <motion.div
                key={email.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className={`glass border rounded-2xl overflow-hidden ${statusColor[email.localStatus]}`}
              >
                {/* Header row */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : email.id)}
                  className="w-full flex items-center gap-4 p-4 text-left hover:bg-muted/30 transition-colors"
                >
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 border border-border flex items-center justify-center text-lg font-bold text-foreground flex-shrink-0">
                    {email.company_name[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-foreground">
                        {email.company_name}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium border ${statusBadge[email.localStatus]}`}
                      >
                        {email.localStatus.charAt(0).toUpperCase() + email.localStatus.slice(1)}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5 truncate">
                      {email.editedSubject ?? email.subject}
                    </div>
                    {email.recipient_email && (
                      <div className="text-xs text-muted-foreground/70 mt-0.5">
                        To: {email.recipient_email}
                      </div>
                    )}
                  </div>
                  <div className="text-muted-foreground flex-shrink-0">
                    {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </div>
                </button>

                {/* Expanded content */}
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="px-4 pb-4 border-t border-border/50">
                        {isEditing ? (
                          <EmailEditor
                            email={email}
                            onSave={(subject, body) => saveEdit(email.id, subject, body)}
                            onCancel={() => setEditingId(null)}
                          />
                        ) : (
                          <EmailViewer
                            email={email}
                            onApprove={() => approve(email.id)}
                            onReject={() => reject(email.id)}
                            onEdit={() => startEdit(email.id)}
                            onSend={() => markSent(email.id)}
                          />
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}

function EmailViewer({
  email,
  onApprove,
  onReject,
  onEdit,
  onSend,
}: {
  email: EmailWithLocalStatus;
  onApprove: () => void;
  onReject: () => void;
  onEdit: () => void;
  onSend: () => void;
}) {
  const displaySubject = email.editedSubject ?? email.subject;
  const displayBody = email.editedBody ?? email.body;

  return (
    <div className="mt-4 space-y-4">
      {/* Subject */}
      <div>
        <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Subject</div>
        <div className="text-sm text-foreground font-medium">{displaySubject}</div>
      </div>

      {/* Body */}
      <div>
        <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Email Body</div>
        <div className="bg-muted/30 rounded-xl p-4 text-sm text-foreground/90 whitespace-pre-wrap font-mono leading-relaxed border border-border">
          {displayBody}
        </div>
      </div>

      {/* Action buttons */}
      {email.localStatus === "pending" && (
        <div className="flex items-center gap-3 pt-2">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onApprove}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-500 text-sm font-medium hover:bg-emerald-500/30 transition-colors"
          >
            <CheckCircle className="w-4 h-4" />
            Approve
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onEdit}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary/20 border border-primary/30 text-primary text-sm font-medium hover:bg-primary/30 transition-colors"
          >
            <Edit3 className="w-4 h-4" />
            Edit
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onReject}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/20 border border-red-500/30 text-red-500 text-sm font-medium hover:bg-red-500/30 transition-colors"
          >
            <XCircle className="w-4 h-4" />
            Reject
          </motion.button>
        </div>
      )}

      {email.localStatus === "approved" && (
        <div className="flex items-center gap-3 pt-2">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onSend}
            className="btn-futuristic flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-primary to-secondary text-primary-foreground text-sm font-semibold shadow-lg shadow-primary/20"
          >
            <Send className="w-4 h-4" />
            Send via Gmail
          </motion.button>
          <span className="text-xs text-emerald-500 font-medium">
            Approved — ready to send
          </span>
        </div>
      )}

      {email.localStatus === "sent" && (
        <div className="flex items-center gap-2 pt-2 text-sm text-primary">
          <Send className="w-4 h-4" />
          Sent{email.sent_at ? ` at ${new Date(email.sent_at).toLocaleString()}` : ""}
        </div>
      )}

      {email.localStatus === "rejected" && (
        <div className="flex items-center gap-2 pt-2 text-sm text-red-500">
          <XCircle className="w-4 h-4" />
          Rejected — email will not be sent
        </div>
      )}
    </div>
  );
}

function EmailEditor({
  email,
  onSave,
  onCancel,
}: {
  email: EmailWithLocalStatus;
  onSave: (subject: string, body: string) => void;
  onCancel: () => void;
}) {
  const [subject, setSubject] = useState(email.editedSubject ?? email.subject);
  const [body, setBody] = useState(email.editedBody ?? email.body);

  return (
    <div className="mt-4 space-y-4">
      <div>
        <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-1">
          Subject
        </label>
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="w-full bg-muted/30 border border-border rounded-xl px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
        />
      </div>
      <div>
        <label className="block text-xs text-muted-foreground uppercase tracking-wider mb-1">
          Body
        </label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={12}
          className="w-full bg-muted/30 border border-border rounded-xl px-4 py-3 text-sm text-foreground font-mono leading-relaxed focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all resize-none"
        />
      </div>
      <div className="flex items-center gap-3">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onSave(subject, body)}
          className="px-4 py-2 rounded-xl bg-primary/20 border border-primary/30 text-primary text-sm font-medium hover:bg-primary/30 transition-colors"
        >
          Save Changes
        </motion.button>
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-xl text-muted-foreground text-sm hover:text-foreground transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
