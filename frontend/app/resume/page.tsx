"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { FileText, Upload, Star, Trash2 } from "lucide-react";
import { RequireAuth } from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import { activateResume, deleteResume, fetchResumes, uploadResume } from "@/lib/api";
import { ResumeVersion } from "@/lib/types";

export default function ResumePage() {
  const { session } = useAuth();
  const [resumes, setResumes] = useState<ResumeVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const userId = session?.user?.id;

  const loadResumes = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchResumes(userId);
      setResumes(result.resumes ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load resumes");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadResumes();
  }, [loadResumes]);

  const onUpload = async (file: File | null) => {
    if (!file || !userId) return;

    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("user_id", userId);
      await uploadResume(formData);
      await loadResumes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onActivate = async (resumeId: string) => {
    if (!userId) return;
    await activateResume(resumeId, userId);
    await loadResumes();
  };

  const onDelete = async (resumeId: string) => {
    if (!userId) return;
    await deleteResume(resumeId, userId);
    await loadResumes();
  };

  return (
    <RequireAuth>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-linear-to-br from-primary to-secondary flex items-center justify-center">
              <FileText className="w-5 h-5 text-primary-foreground" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">Resume Manager</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Upload resume versions, extract skills automatically, and set one active version for AI drafting.
          </p>
        </motion.div>

        <div className="glass border border-border rounded-2xl p-5 mb-6">
          <label className="text-xs uppercase tracking-wider text-muted-foreground block mb-2">
            Upload Resume (pdf, docx, txt)
          </label>
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md"
            onChange={(e) => onUpload(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-foreground file:mr-4 file:rounded-lg file:border-0 file:px-4 file:py-2 file:bg-primary/15 file:text-primary"
          />
          {uploading && (
            <p className="mt-2 text-xs text-muted-foreground flex items-center gap-2">
              <Upload className="w-3.5 h-3.5" />
              Uploading and extracting text...
            </p>
          )}
          {error && <p className="mt-2 text-xs text-red-500">{error}</p>}
        </div>

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading resume versions...</p>
        ) : resumes.length === 0 ? (
          <div className="glass border border-border rounded-2xl p-6 text-sm text-muted-foreground">
            No resume versions yet.
          </div>
        ) : (
          <div className="space-y-4">
            {resumes.map((resume) => (
              <div key={resume.id} className="glass border border-border rounded-2xl p-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-foreground">{resume.version_label}</h3>
                      {resume.is_active && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] border border-emerald-500/40 bg-emerald-500/15 text-emerald-500">
                          Active
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{resume.file_name}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {new Date(resume.created_at).toLocaleString()}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {!resume.is_active && (
                      <button
                        onClick={() => onActivate(resume.id)}
                        className="px-3 py-2 rounded-xl border border-primary/30 text-primary text-xs hover:bg-primary/10 flex items-center gap-1"
                      >
                        <Star className="w-3.5 h-3.5" />
                        Set Active
                      </button>
                    )}
                    <button
                      onClick={() => onDelete(resume.id)}
                      className="px-3 py-2 rounded-xl border border-red-500/30 text-red-500 text-xs hover:bg-red-500/10 flex items-center gap-1"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete
                    </button>
                  </div>
                </div>

                <div className="mt-3">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                    Extracted skills
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {resume.extracted_skills.length === 0 ? (
                      <span className="text-xs text-muted-foreground">No skills detected</span>
                    ) : (
                      resume.extracted_skills.map((skill) => (
                        <span
                          key={skill}
                          className="text-xs px-2 py-1 rounded-md bg-primary/10 border border-primary/20 text-primary"
                        >
                          {skill}
                        </span>
                      ))
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </RequireAuth>
  );
}
