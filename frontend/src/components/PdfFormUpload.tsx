"use client";

import { FormEvent, useState } from "react";

import { PdfFormUploadResponse, uploadPdfForm, UserRole } from "@/lib/api";

const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024;

type PdfFormUploadProps = {
  role: UserRole;
  onUploaded: () => void;
};

type UploadFormState = {
  title: string;
  description: string;
  category: string;
  department: string;
  sourceUrl: string;
};

const EMPTY_FORM: UploadFormState = {
  title: "",
  description: "",
  category: "",
  department: "",
  sourceUrl: "",
};

export function PdfFormUpload({ role, onUploaded }: PdfFormUploadProps) {
  const [form, setForm] = useState<UploadFormState>(EMPTY_FORM);
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [success, setSuccess] = useState<PdfFormUploadResponse | null>(null);
  const isAdmin = role === "admin";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setSuccess(null);

    const validationError = validateUpload(form, file, isAdmin);
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }
    if (!file) {
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await uploadPdfForm({
        file,
        title: form.title,
        description: form.description,
        category: form.category,
        department: form.department,
        source_url: form.sourceUrl,
      });
      setSuccess(response);
      setForm(EMPTY_FORM);
      setFile(null);
      onUploaded();
    } catch (error) {
      setErrorMessage(uploadErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5">
      <div>
        <h2 className="text-lg font-semibold text-zinc-950">Upload PDF form</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Uploaded PDFs enter pending review before publication.
        </p>
      </div>

      {!isAdmin ? (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Switch to Admin mode to upload forms.
        </div>
      ) : null}

      <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
        <div>
          <label className="text-sm font-medium text-zinc-700" htmlFor="pdf-file">
            PDF file
          </label>
          <input
            accept="application/pdf,.pdf"
            className="mt-2 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 file:mr-3 file:rounded-md file:border-0 file:bg-zinc-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-zinc-700"
            disabled={!isAdmin || isSubmitting}
            id="pdf-file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            type="file"
          />
          <p className="mt-1 text-xs text-zinc-500">PDF only. Max 10 MB.</p>
        </div>

        <TextField
          disabled={!isAdmin || isSubmitting}
          label="Title"
          onChange={(value) => setForm((current) => ({ ...current, title: value }))}
          required
          value={form.title}
        />
        <TextArea
          disabled={!isAdmin || isSubmitting}
          label="Description"
          onChange={(value) =>
            setForm((current) => ({ ...current, description: value }))
          }
          value={form.description}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            disabled={!isAdmin || isSubmitting}
            label="Category"
            onChange={(value) =>
              setForm((current) => ({ ...current, category: value }))
            }
            value={form.category}
          />
          <TextField
            disabled={!isAdmin || isSubmitting}
            label="Department"
            onChange={(value) =>
              setForm((current) => ({ ...current, department: value }))
            }
            value={form.department}
          />
        </div>
        <TextField
          disabled={!isAdmin || isSubmitting}
          label="Source URL"
          onChange={(value) =>
            setForm((current) => ({ ...current, sourceUrl: value }))
          }
          type="url"
          value={form.sourceUrl}
        />

        {errorMessage ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {errorMessage}
          </div>
        ) : null}

        {success ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
            Uploaded {success.title}. Form ID:{" "}
            <span className="font-mono">{success.form_id}</span>. Status:{" "}
            {success.status}.
          </div>
        ) : null}

        <button
          className="h-10 rounded-lg bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          disabled={!isAdmin || isSubmitting}
          type="submit"
        >
          {isSubmitting ? "Uploading..." : "Upload PDF"}
        </button>
      </form>
    </section>
  );
}

function TextField({
  disabled,
  label,
  onChange,
  required = false,
  type = "text",
  value,
}: {
  disabled: boolean;
  label: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  value: string;
}) {
  const inputId = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label className="text-sm font-medium text-zinc-700" htmlFor={inputId}>
        {label}
      </label>
      <input
        className="mt-2 block h-10 w-full rounded-lg border border-zinc-300 px-3 text-sm text-zinc-950 outline-none transition placeholder:text-zinc-400 focus:border-teal-500 focus:ring-2 focus:ring-teal-100 disabled:bg-zinc-100"
        disabled={disabled}
        id={inputId}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        type={type}
        value={value}
      />
    </div>
  );
}

function TextArea({
  disabled,
  label,
  onChange,
  value,
}: {
  disabled: boolean;
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  const inputId = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label className="text-sm font-medium text-zinc-700" htmlFor={inputId}>
        {label}
      </label>
      <textarea
        className="mt-2 block min-h-20 w-full resize-y rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-950 outline-none transition placeholder:text-zinc-400 focus:border-teal-500 focus:ring-2 focus:ring-teal-100 disabled:bg-zinc-100"
        disabled={disabled}
        id={inputId}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </div>
  );
}

function validateUpload(
  form: UploadFormState,
  file: File | null,
  isAdmin: boolean,
): string {
  if (!isAdmin) {
    return "Admin mode is required to upload forms.";
  }
  if (!file) {
    return "Choose a PDF file to upload.";
  }
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    return "Only PDF files are supported.";
  }
  if (file.size === 0) {
    return "The selected PDF is empty.";
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return "The selected PDF is larger than 10 MB.";
  }
  if (!form.title.trim()) {
    return "Title is required.";
  }
  if (form.sourceUrl.trim()) {
    try {
      const sourceUrl = new URL(form.sourceUrl.trim());
      if (sourceUrl.protocol !== "http:" && sourceUrl.protocol !== "https:") {
        return "Source URL must start with http or https.";
      }
    } catch {
      return "Source URL must be a valid URL.";
    }
  }
  return "";
}

function uploadErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message === "ADMIN_UNAUTHORIZED") {
    return "You are not authorized to upload forms.";
  }
  if (error instanceof Error && error.message === "UPLOAD_FAILED") {
    return "Upload failed. Confirm the file is a valid PDF and try again.";
  }
  return "The backend is unavailable. Check that FastAPI is running.";
}
