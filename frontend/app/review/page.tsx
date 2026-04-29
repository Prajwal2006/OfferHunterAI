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
    sent: "border-blue-500/30 bg-blue-500/5",
  };

  const statusBadge = {
    pending: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    approved: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    rejected: "bg-red-500/20 text-red-300 border-red-500/30",
    sent: "bg-blue-500/20 text-blue-300 border-blue-500/30",
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
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <Mail className="w-6 h-6 text-blue-400" />
              Email Review
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Review and approve AI-drafted emails before sending
            </p>
          </div>

          {/* HITL Notice */}
          <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-500/10 border border-purple-500/30">
            <Shield className="w-4 h-4 text-purple-400 flex-shrink-0" />
            <span className="text-xs text-purple-300 font-medium">
              Human-in-the-Loop Required
            </span>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mt-6">
          {[
            { label: "Pending", count: pending.length, color: "text-amber-400" },
            { label: "Approved", count: approved.length, color: "text-emerald-400" },
            { label: "Sent", count: sent.length, color: "text-blue-400" },
            { label: "Rejected", count: rejected.length, color: "text-red-400" },
          ].map((s) => (
            <div
              key={s.label}
              className="glass border border-[var(--border-color)] rounded-xl p-3 text-center"
            >
              <div className={`text-2xl font-bold ${s.color}`}>{s.count}</div>
              <div className="text-xs text-slate-500">{s.label}</div>
            </div>
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
                className={`glass border rounded-xl overflow-hidden ${statusColor[email.localStatus]}`}
              >
                {/* Header row */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : email.id)}
                  className="w-full flex items-center gap-4 p-4 text-left hover:bg-white/5 transition-colors"
                >
                  <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-lg font-bold text-slate-300 flex-shrink-0">
                    {email.company_name[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-200">
                        {email.company_name}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium border ${statusBadge[email.localStatus]}`}
                      >
                        {email.localStatus.charAt(0).toUpperCase() + email.localStatus.slice(1)}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5 truncate">
                      {email.editedSubject ?? email.subject}
                    </div>
                    {email.recipient_email && (
                      <div className="text-xs text-slate-600 mt-0.5">
                        To: {email.recipient_email}
                      </div>
                    )}
                  </div>
                  <div className="text-slate-600 flex-shrink-0">
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
                      <div className="px-4 pb-4 border-t border-white/5">
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
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Subject</div>
        <div className="text-sm text-slate-200 font-medium">{displaySubject}</div>
      </div>

      {/* Body */}
      <div>
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Email Body</div>
        <div className="bg-black/30 rounded-lg p-4 text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed border border-white/5">
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
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-sm font-medium hover:bg-emerald-500/30 transition-colors"
          >
            <CheckCircle className="w-4 h-4" />
            Approve
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onEdit}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-300 text-sm font-medium hover:bg-blue-500/30 transition-colors"
          >
            <Edit3 className="w-4 h-4" />
            Edit
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onReject}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/20 border border-red-500/40 text-red-300 text-sm font-medium hover:bg-red-500/30 transition-colors"
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
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 text-white text-sm font-semibold shadow-lg shadow-blue-500/20 hover:from-blue-500 hover:to-purple-500 transition-all"
          >
            <Send className="w-4 h-4" />
            Send via Gmail
          </motion.button>
          <span className="text-xs text-emerald-400">
            ✓ Approved — ready to send
          </span>
        </div>
      )}

      {email.localStatus === "sent" && (
        <div className="flex items-center gap-2 pt-2 text-sm text-blue-400">
          <Send className="w-4 h-4" />
          Sent{email.sent_at ? ` at ${new Date(email.sent_at).toLocaleString()}` : ""}
        </div>
      )}

      {email.localStatus === "rejected" && (
        <div className="flex items-center gap-2 pt-2 text-sm text-red-400">
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
        <label className="block text-xs text-slate-500 uppercase tracking-wider mb-1">
          Subject
        </label>
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="w-full bg-black/40 border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500/50 transition-colors"
        />
      </div>
      <div>
        <label className="block text-xs text-slate-500 uppercase tracking-wider mb-1">
          Body
        </label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={12}
          className="w-full bg-black/40 border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm text-slate-300 font-mono leading-relaxed focus:outline-none focus:border-blue-500/50 transition-colors resize-none"
        />
      </div>
      <div className="flex items-center gap-3">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onSave(subject, body)}
          className="px-4 py-2 rounded-lg bg-blue-500/20 border border-blue-500/40 text-blue-300 text-sm font-medium hover:bg-blue-500/30 transition-colors"
        >
          Save Changes
        </motion.button>
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg text-slate-500 text-sm hover:text-slate-300 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
