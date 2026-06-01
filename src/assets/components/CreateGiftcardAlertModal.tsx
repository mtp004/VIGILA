import { useState } from "react";
import { createAlert, updateAlert, type AlertFormData, type GiftCardAlert } from "../APIs/GiftcardFirestore";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CreateAlertModalProps {
  onAddSuccess: () => void;
  onClose: () => void;
  editingAlert?: GiftCardAlert | null;
}

interface FormData {
  brand: string;
  minCardValue: number;
  maxCardValue: number;
  minDiscountPercent: number;
  platforms: { gcx: boolean; cardcash: boolean; carddepot: boolean };
  urls: { gcx: string; cardcash: string; carddepot: string };
}

const DEFAULT_FORM: FormData = {
  brand: "",
  minCardValue: 20,
  maxCardValue: 100,
  minDiscountPercent: 8.5,
  platforms: { gcx: true, cardcash: true, carddepot: true },
  urls: { gcx: "", cardcash: "", carddepot: "" },
};

const PLATFORM_META = [
  {
    id: "gcx" as const,
    label: "GCX",
    placeholder: "https://gcx.app/buy-nike-gift-cards",
  },
  {
    id: "cardcash" as const,
    label: "CardCash",
    placeholder: "https://www.cardcash.com/buy-gift-cards/discount-nike-cards/",
  },
  {
    id: "carddepot" as const,
    label: "CardDepot",
    placeholder: "https://carddepot.com/brands/discount-nike-gift-cards",
  },
];

// ─── Step Indicator ───────────────────────────────────────────────────────────

const StepIndicator = ({ current, total }: { current: number; total: number }) => (
  <div className="d-flex align-items-center gap-2 mb-3">
    {Array.from({ length: total }).map((_, i) => (
      <div
        key={i}
        style={{
          height: 4,
          borderRadius: 2,
          background: i <= current ? "#0d6efd" : "#dee2e6",
          flex: i === current ? 2 : 1,
          transition: "flex 0.3s, background 0.2s",
        }}
      />
    ))}
  </div>
);

// ─── Step 1: Brand ────────────────────────────────────────────────────────────

interface Step1Props {
  brand: string;
  onChange: (brand: string) => void;
}

const Step1Brand = ({ brand, onChange }: Step1Props) => (
  <div>
    <p className="text-muted mb-3" style={{ fontSize: 14 }}>
      Enter the brand name you want to monitor for discounted gift cards.
    </p>
    <div className="mb-3">
      <label className="form-label" style={{ fontSize: 13, fontWeight: 500 }}>
        Brand name
      </label>
      <input
        type="text"
        className="form-control"
        placeholder="e.g. Nike, Amazon, Starbucks…"
        value={brand}
        autoFocus
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  </div>
);

// ─── Step 2: Criteria ─────────────────────────────────────────────────────────

interface Step2Props {
  minCardValue: number;
  maxCardValue: number;
  minDiscountPercent: number;
  onChange: (field: string, value: number) => void;
}

const Step2Criteria = ({
  minCardValue,
  maxCardValue,
  minDiscountPercent,
  onChange,
}: Step2Props) => (
  <div>
    <p className="text-muted mb-3" style={{ fontSize: 14 }}>
      Set the card value range and minimum discount you want to be alerted on.
    </p>

    {/* Card value range */}
    <div className="mb-3">
      <label className="form-label" style={{ fontSize: 13, fontWeight: 500 }}>
        Card face value range
      </label>
      <div className="d-flex align-items-center gap-2">
        <div className="input-group" style={{ width: 130 }}>
          <span className="input-group-text" style={{ fontSize: 13 }}>$</span>
          <input
            type="number"
            className="form-control"
            min={0}
            value={minCardValue}
            onChange={(e) => onChange("minCardValue", Number(e.target.value))}
          />
        </div>
        <span style={{ color: "#adb5bd", fontSize: 14 }}>to</span>
        <div className="input-group" style={{ width: 130 }}>
          <span className="input-group-text" style={{ fontSize: 13 }}>$</span>
          <input
            type="number"
            className="form-control"
            min={0}
            value={maxCardValue}
            onChange={(e) => onChange("maxCardValue", Number(e.target.value))}
          />
        </div>
      </div>
      {minCardValue >= maxCardValue && (
        <div className="text-danger mt-1" style={{ fontSize: 12 }}>
          Min value must be less than max value.
        </div>
      )}
    </div>

    {/* Min discount */}
    <div className="mb-3">
      <label className="form-label" style={{ fontSize: 13, fontWeight: 500 }}>
        Minimum discount
      </label>
      <div className="d-flex align-items-center gap-2">
        <div className="input-group" style={{ width: 140 }}>
          <input
            type="number"
            className="form-control"
            min={0.5}
            max={99}
            step={0.5}
            value={minDiscountPercent}
            onChange={(e) =>
              onChange("minDiscountPercent", Number(e.target.value))
            }
          />
          <span className="input-group-text" style={{ fontSize: 13 }}>%</span>
        </div>
        <span style={{ fontSize: 13, color: "#6c757d" }}>off or more</span>
      </div>
    </div>

    {/* Preview */}
    <div
      style={{
        background: "#f8f9fa",
        border: "1px solid #e9ecef",
        borderRadius: 8,
        padding: "10px 14px",
        fontSize: 13,
        color: "#495057",
      }}
    >
      Alert me when a card worth{" "}
      <strong>
        ${minCardValue}–${maxCardValue}
      </strong>{" "}
      is available at <strong>{minDiscountPercent}% off</strong> or more.
    </div>
  </div>
);

// ─── Step 3: Platforms & URLs ─────────────────────────────────────────────────

interface Step3Props {
  platforms: FormData["platforms"];
  urls: FormData["urls"];
  onTogglePlatform: (id: keyof FormData["platforms"]) => void;
  onUrlChange: (id: keyof FormData["urls"], value: string) => void;
}

const Step3Platforms = ({
  platforms,
  urls,
  onTogglePlatform,
  onUrlChange,
}: Step3Props) => (
  <div>
    <p className="text-muted mb-3" style={{ fontSize: 14 }}>
      Choose which sites to monitor and paste the exact listing URL for this
      brand on each site.
    </p>

    <div className="d-flex flex-column gap-3">
      {PLATFORM_META.map((p) => {
        const isSelected = platforms[p.id];
        return (
          <div
            key={p.id}
            style={{
              border: isSelected ? "1px solid #b6d4fe" : "1px solid #dee2e6",
              borderRadius: 10,
              padding: "12px 14px",
              background: isSelected ? "#f0f6ff" : "#fff",
              transition: "all 0.15s",
            }}
          >
            {/* Toggle row */}
            <div className="d-flex justify-content-between align-items-center">
              <span style={{ fontSize: 14, fontWeight: 500 }}>{p.label}</span>
              <div className="form-check form-switch mb-0">
                <input
                  className="form-check-input"
                  type="checkbox"
                  role="switch"
                  checked={isSelected}
                  onChange={() => onTogglePlatform(p.id)}
                  style={{ cursor: "pointer" }}
                />
              </div>
            </div>

            {/* URL input — shown only when platform is selected */}
            {isSelected && (
              <div className="mt-2">
                <input
                  type="url"
                  className="form-control form-control-sm"
                  placeholder={p.placeholder}
                  value={urls[p.id]}
                  onChange={(e) => onUrlChange(p.id, e.target.value)}
                  style={{ fontSize: 12, color: "#495057" }}
                />
                {urls[p.id] && !urls[p.id].startsWith("http") && (
                  <div className="text-danger mt-1" style={{ fontSize: 11 }}>
                    URL must start with http:// or https://
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>

    {!Object.values(platforms).some(Boolean) && (
      <div className="text-danger mt-2" style={{ fontSize: 12 }}>
        Select at least one platform.
      </div>
    )}
  </div>
);

// ─── Main Modal ───────────────────────────────────────────────────────────────

const CreateGiftcardAlertModal = ({ onAddSuccess, onClose, editingAlert }: CreateAlertModalProps) => {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormData>(
    editingAlert
      ? {
          brand: editingAlert.brand,
          minCardValue: editingAlert.minCardValue,
          maxCardValue: editingAlert.maxCardValue,
          minDiscountPercent: editingAlert.minDiscountPercent,
          platforms: {
            gcx: editingAlert.platforms.gcx.active,
            cardcash: editingAlert.platforms.cardcash.active,
            carddepot: editingAlert.platforms.carddepot.active,
          },
          urls: editingAlert.urls,
        }
      : DEFAULT_FORM
  );
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const STEP_TITLES = ["Brand", "Criteria", "Platforms & URLs"];

  // ── Validation ──────────────────────────────────────────────────────────────

  const isStep0Valid = form.brand.trim().length > 0;

  const isStep1Valid =
    form.minCardValue >= 0 &&
    form.maxCardValue > form.minCardValue &&
    form.minDiscountPercent > 0;

  const isStep2Valid =
    Object.values(form.platforms).some(Boolean) &&
    Object.entries(form.platforms)
      .filter(([, isEnabled]) => isEnabled)
      .every(
        ([id]) =>
          form.urls[id as keyof typeof form.urls]?.trim().length > 0 &&
          form.urls[id as keyof typeof form.urls].startsWith("http")
      );

  const canProceed = [isStep0Valid, isStep1Valid, isStep2Valid][step];

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleCriteriaChange = (field: string, value: number) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleTogglePlatform = (id: keyof FormData["platforms"]) => {
    setForm((prev) => ({
      ...prev,
      platforms: { ...prev.platforms, [id]: !prev.platforms[id] },
    }));
  };

  const handleUrlChange = (id: keyof FormData["urls"], value: string) => {
    setForm((prev) => ({
      ...prev,
      urls: { ...prev.urls, [id]: value },
    }));
  };

  const handleNext = () => {
    if (step < 2) {
      setStep((s) => s + 1);
    }
  };

  const handleBack = () => {
    setSaveError(null);
    setStep((s) => s - 1);
  };

  const handleSubmit = async () => {
  setIsSaving(true);
  setSaveError(null);
  try {
    const payload: AlertFormData = {
      brand: form.brand.trim().toLowerCase(),
      minCardValue: form.minCardValue,
      maxCardValue: form.maxCardValue,
      minDiscountPercent: form.minDiscountPercent,
      platforms: form.platforms,
      urls: form.urls,
    };
    if (editingAlert) {
      await updateAlert(editingAlert.id, payload);
    } else {
      await createAlert(payload);
    }
    onAddSuccess();
    onClose();
  } catch (err: any) {
    setSaveError(err.message || "Failed to save alert. Please try again.");
  } finally {
    setIsSaving(false);
  }
};

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Backdrop */}
      <div className="modal-backdrop show" onClick={onClose} />

      {/* Modal */}
      <div className="modal d-block" tabIndex={-1}>
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content" style={{ borderRadius: 12, border: "1px solid #e9ecef" }}>

            {/* Header */}
            <div className="modal-header" style={{ borderBottom: "1px solid #f1f3f5", padding: "1rem 1.25rem" }}>
              <div>
                <h5 className="modal-title mb-0" style={{ fontSize: 16, fontWeight: 600 }}>
                  {editingAlert ? "Edit gift card alert" : "New gift card alert"}
                </h5>
                <small className="text-muted">
                  Step {step + 1} of 3 — {STEP_TITLES[step]}
                </small>
              </div>
              <button
                type="button"
                className="btn-close"
                onClick={onClose}
                disabled={isSaving}
              />
            </div>

            {/* Body */}
            <div className="modal-body" style={{ padding: "1.25rem" }}>
              <StepIndicator current={step} total={3} />

              {step === 0 && (
                <Step1Brand
                  brand={form.brand}
                  onChange={(val) => setForm((prev) => ({ ...prev, brand: val }))}
                />
              )}
              {step === 1 && (
                <Step2Criteria
                  minCardValue={form.minCardValue}
                  maxCardValue={form.maxCardValue}
                  minDiscountPercent={form.minDiscountPercent}
                  onChange={handleCriteriaChange}
                />
              )}
              {step === 2 && (
                <Step3Platforms
                  platforms={form.platforms}
                  urls={form.urls}
                  onTogglePlatform={handleTogglePlatform}
                  onUrlChange={handleUrlChange}
                />
              )}

              {saveError && (
                <div className="alert alert-danger mt-3 mb-0 py-2" role="alert">
                  <small>{saveError}</small>
                </div>
              )}
            </div>

            {/* Footer */}
            <div
              className="modal-footer"
              style={{ borderTop: "1px solid #f1f3f5", padding: "0.875rem 1.25rem", gap: 8 }}
            >
              {step > 0 && (
                <button
                  type="button"
                  className="btn btn-light btn-sm"
                  onClick={handleBack}
                  disabled={isSaving}
                  style={{ border: "1px solid #dee2e6" }}
                >
                  Back
                </button>
              )}
              <button
                type="button"
                className="btn btn-primary btn-sm ms-auto"
                onClick={step === 2 ? handleSubmit : handleNext}
                disabled={!canProceed || isSaving}
              >
                {isSaving && (
                  <span
                    className="spinner-border spinner-border-sm me-2"
                    role="status"
                  />
                )}
                {step === 2 ? (editingAlert ? "Save changes" : "Create alert") : "Next →"}
              </button>
            </div>

          </div>
        </div>
      </div>
    </>
  );
};

export default CreateGiftcardAlertModal;